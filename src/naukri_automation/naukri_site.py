from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
USERNAME_SELECTOR = 'input#usernameField, input#emailTxt, input[name="username"]'
PASSWORD_SELECTOR = 'input#passwordField, input#pwd1, input[type="password"]'
LOGIN_BUTTON_SELECTOR = (
    'button[type="submit"]:has-text("Login"), button.btn-primary:has-text("Login")'
)
LOGIN_ERROR_SELECTOR = '.server-err, .error-message, [role="alert"], [class*="error" i]'
CHALLENGE_SELECTOR = (
    'iframe[title*="captcha" i], iframe[src*="captcha" i], '
    '[class*="captcha" i], input[name*="otp" i]'
)
RESUME_SELECTOR = (
    'input#attachCV[type="file"], input[type="file"][name*="resume" i], '
    'input[type="file"][accept*="pdf" i]'
)
AUTHENTICATED_SELECTOR = (
    'button[aria-label="Open profile menu"], a[href="/mnjuser/profile"], '
    ".view-profile-wrapper, input#attachCV, input[type=\"file\"][name*=\"resume\" i]"
)
UPDATE_EVIDENCE_SELECTOR = (
    '.updateOn, [class*="updateOn"], [class*="resume"] [class*="date"]'
)


class AuthState(StrEnum):
    AUTHENTICATED = "AUTHENTICATED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    CHALLENGE_REQUIRED = "CHALLENGE_REQUIRED"
    UNKNOWN = "UNKNOWN"


class AuthenticationRequired(RuntimeError):
    pass


class SiteContractError(RuntimeError):
    pass


class UploadVerificationError(RuntimeError):
    pass


class NaukriSite:
    def __init__(self, page: Any, *, timeout_seconds: int) -> None:
        self.page = page
        self.timeout_ms = timeout_seconds * 1000

    def open_profile(self) -> None:
        self.page.goto(PROFILE_URL, wait_until="domcontentloaded")

    def fill_login(self, username: str, password: str) -> bool:
        username_input = self.page.locator(USERNAME_SELECTOR).first
        password_input = self.page.locator(PASSWORD_SELECTOR).first
        try:
            username_input.wait_for(state="visible", timeout=self.timeout_ms)
            password_input.wait_for(state="visible", timeout=self.timeout_ms)
        except Exception:
            return False
        username_input.fill(username)
        password_input.fill(password)
        return True

    def submit_login(self) -> bool:
        button = self.page.locator(LOGIN_BUTTON_SELECTOR).first
        try:
            button.wait_for(state="visible", timeout=self.timeout_ms)
            button.click()
        except Exception:
            return False
        return True

    def wait_for_login_result(self) -> AuthState:
        try:
            self.page.wait_for_function(
                """([authenticated, challenge]) => {
                    const text = (document.body?.innerText || '').toLowerCase();
                    const rejected =
                        /(invalid|incorrect|wrong).*(email|e-mail|username|password)/.test(text) ||
                        /(email|e-mail|username|password).*(invalid|incorrect|wrong)/.test(text);
                    return location.pathname.includes('/mnjuser/profile') ||
                        document.querySelector(authenticated) ||
                        document.querySelector(challenge) || rejected;
                }""",
                arg=[AUTHENTICATED_SELECTOR, CHALLENGE_SELECTOR],
                timeout=self.timeout_ms,
            )
        except Exception:
            return AuthState.UNKNOWN
        return self.auth_state()

    def wait_for_auth_state(self) -> AuthState:
        state_marker = self.page.locator(
            f"{USERNAME_SELECTOR}, {AUTHENTICATED_SELECTOR}"
        ).first
        try:
            state_marker.wait_for(state="attached", timeout=self.timeout_ms)
        except Exception:
            return AuthState.UNKNOWN
        return self.auth_state()

    def auth_state(self) -> AuthState:
        current_url = self.page.url.lower()
        if self._count(AUTHENTICATED_SELECTOR):
            return AuthState.AUTHENTICATED
        if self._has_invalid_credentials_error():
            return AuthState.INVALID_CREDENTIALS
        if self._count(CHALLENGE_SELECTOR):
            return AuthState.CHALLENGE_REQUIRED
        if "/nlogin/" in current_url or self._count(USERNAME_SELECTOR):
            return AuthState.LOGIN_REQUIRED
        return AuthState.UNKNOWN

    def inspect_resume_section(self) -> str:
        state = self.wait_for_auth_state()
        if state == AuthState.LOGIN_REQUIRED:
            raise AuthenticationRequired("Naukri login is required")
        if state == AuthState.UNKNOWN:
            raise SiteContractError("could not confirm the Naukri profile page")

        resume_input = self._resume_input()
        try:
            resume_input.first.wait_for(state="attached", timeout=self.timeout_ms)
        except Exception as error:
            raise SiteContractError("resume upload control was not found") from error

        evidence = self.page.locator(UPDATE_EVIDENCE_SELECTOR).first
        text = self._visible_text(evidence)
        if text:
            return text
        return "resume upload control is available"

    def upload_resume(self, resume_path: Path) -> str:
        self.inspect_resume_section()
        resume_input = self._resume_input().first
        filename = resume_path.name
        filename_evidence = self.page.get_by_text(filename, exact=False).first
        filename_before = self._visible_text(filename_evidence)
        update_evidence = self.page.locator(UPDATE_EVIDENCE_SELECTOR).first
        update_before = self._visible_text(update_evidence)

        resume_input.set_input_files(str(resume_path))

        confirmation = self.page.get_by_text(
            re.compile(r"resume (uploaded|updated) successfully", re.IGNORECASE)
        ).first
        try:
            confirmation.wait_for(state="visible", timeout=self.timeout_ms)
            text = confirmation.inner_text().strip()
            if text:
                return text
        except Exception:
            pass

        if not filename_before:
            try:
                filename_evidence.wait_for(state="visible", timeout=self.timeout_ms)
                text = filename_evidence.inner_text().strip()
                if text:
                    return text
            except Exception:
                pass

        try:
            if update_before:
                from playwright.sync_api import expect

                expect(update_evidence).not_to_have_text(
                    update_before,
                    timeout=self.timeout_ms,
                )
            else:
                update_evidence.wait_for(state="visible", timeout=self.timeout_ms)
            update_after = self._visible_text(update_evidence)
            if update_after and update_after != update_before:
                return update_after
        except Exception as error:
            raise UploadVerificationError(
                "upload was attempted but success could not be verified"
            ) from error

        raise UploadVerificationError("upload success evidence was empty")

    def _resume_input(self) -> Any:
        return self.page.locator(RESUME_SELECTOR)

    def _count(self, selector: str) -> int:
        return self.page.locator(selector).count()

    def _has_invalid_credentials_error(self) -> bool:
        error_pattern = re.compile(
            r"(?:invalid|incorrect|wrong).*(?:email|e-mail|username|password)"
            r"|(?:email|e-mail|username|password).*(?:invalid|incorrect|wrong)",
            re.IGNORECASE,
        )
        try:
            messages = self.page.locator(LOGIN_ERROR_SELECTOR).all_inner_texts()
        except Exception:
            messages = []
        if any(error_pattern.search(message.strip()) for message in messages):
            return True
        try:
            body_text = self.page.locator("body").inner_text()
        except Exception:
            return False
        return bool(error_pattern.search(body_text))

    @staticmethod
    def _visible_text(locator: Any) -> str:
        try:
            if locator.count() and locator.is_visible():
                return locator.inner_text().strip()
        except Exception:
            pass
        return ""
