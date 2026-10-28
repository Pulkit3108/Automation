from __future__ import annotations

import re
from contextlib import suppress
from pathlib import Path
from typing import Any

from resume_automation.providers.base import (
    AuthenticationRequired,
    AuthState,
    PortalAccessDenied,
    SiteContractError,
    UploadVerificationError,
)

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
USERNAME_SELECTOR = (
    'input#usernameField, input#emailTxt, input[name="username"], '
    'input[autocomplete="username"], input[type="email"], '
    'input[placeholder*="email" i], input[placeholder*="username" i]'
)
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
ACCESS_DENIED_PATTERN = re.compile(
    r"access denied|(?:do not|don't) have permission to access|errors\.edgesuite\.net",
    re.IGNORECASE,
)


class NaukriProvider:
    def __init__(self, page: Any, *, timeout_seconds: int) -> None:
        self.page = page
        self.timeout_ms = timeout_seconds * 1000

    def open_profile(self) -> None:
        self.page.goto(PROFILE_URL, wait_until="domcontentloaded")

    def open_login(self) -> None:
        self.page.goto(LOGIN_URL, wait_until="domcontentloaded")
        form = self.page.locator(f"{USERNAME_SELECTOR}, {PASSWORD_SELECTOR}").first
        try:
            form.wait_for(state="visible", timeout=min(self.timeout_ms, 5_000))
            return
        except Exception:
            pass
        for role in ("button", "link"):
            control = self.page.get_by_role(
                role,
                name=re.compile(r"^\s*log\s*in\s*$", re.IGNORECASE),
            ).first
            try:
                if control.count() and control.is_visible():
                    control.click()
                    return
            except Exception:
                continue

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
                r"""([authenticated, challenge]) => {
                    const text = (document.body?.innerText || '').toLowerCase();
                    const visible = (selector) => [...document.querySelectorAll(selector)].some(
                        (element) => {
                            const style = getComputedStyle(element);
                            const rect = element.getBoundingClientRect();
                            return style.visibility !== 'hidden' && style.display !== 'none' &&
                                rect.width > 0 && rect.height > 0;
                        }
                    );
                    const rejected =
                        /(invalid|incorrect|wrong).*(email|e-mail|username|password)/.test(text) ||
                        /(email|e-mail|username|password).*(invalid|incorrect|wrong)/.test(text);
                    const denied =
                        /access denied/i.test(text) ||
                        /(?:do not|don't) have permission to access/i.test(text) ||
                        /errors\.edgesuite\.net/i.test(text);
                    return location.pathname.includes('/mnjuser/profile') || denied ||
                        visible(authenticated) || visible(challenge) || rejected;
                }""",
                arg=[AUTHENTICATED_SELECTOR, CHALLENGE_SELECTOR],
                timeout=self.timeout_ms,
            )
        except Exception:
            return AuthState.UNKNOWN
        return self.auth_state()

    def wait_for_auth_state(self) -> AuthState:
        state = self.auth_state()
        if state != AuthState.UNKNOWN:
            return state
        state_marker = self.page.locator(
            f"{USERNAME_SELECTOR}, {AUTHENTICATED_SELECTOR}"
        ).first
        with suppress(Exception):
            state_marker.wait_for(state="attached", timeout=self.timeout_ms)
        return self.auth_state()

    def auth_state(self) -> AuthState:
        current_url = self.page.url.lower()
        if self._is_access_denied():
            return AuthState.ACCESS_DENIED
        if self._has_visible(AUTHENTICATED_SELECTOR):
            return AuthState.AUTHENTICATED
        if self._has_invalid_credentials_error():
            return AuthState.INVALID_CREDENTIALS
        if self._has_visible(CHALLENGE_SELECTOR):
            return AuthState.CHALLENGE_REQUIRED
        if "/nlogin/" in current_url or self._count(USERNAME_SELECTOR):
            return AuthState.LOGIN_REQUIRED
        return AuthState.UNKNOWN

    def inspect_resume_section(self) -> str:
        state = self.wait_for_auth_state()
        if state == AuthState.ACCESS_DENIED:
            raise PortalAccessDenied("Naukri denied access to the automated browser session")
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
            self.page.wait_for_function(
                """([filename, filenameBefore, updateSelector, updateBefore]) => {
                    const bodyText = document.body?.innerText || '';
                    if (/resume (uploaded|updated) successfully/i.test(bodyText)) return true;
                    if (!filenameBefore && bodyText.includes(filename)) return true;
                    return [...document.querySelectorAll(updateSelector)].some((element) => {
                        const style = getComputedStyle(element);
                        const rect = element.getBoundingClientRect();
                        const text = (element.innerText || '').trim();
                        return style.visibility !== 'hidden' && style.display !== 'none' &&
                            rect.width > 0 && rect.height > 0 && text && text !== updateBefore;
                    });
                }""",
                arg=[filename, filename_before, UPDATE_EVIDENCE_SELECTOR, update_before],
                timeout=self.timeout_ms,
            )
        except Exception as error:
            raise UploadVerificationError(
                "upload was attempted but success could not be verified"
            ) from error

        confirmation_text = self._visible_text(confirmation)
        if confirmation_text:
            return confirmation_text
        if not filename_before:
            filename_after = self._visible_text(filename_evidence)
            if filename_after:
                return filename_after
        update_after = self._visible_text(update_evidence)
        if update_after and update_after != update_before:
            return update_after

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
        errors = self.page.locator(LOGIN_ERROR_SELECTOR)
        try:
            for index in range(errors.count()):
                error = errors.nth(index)
                if error.is_visible() and error_pattern.search(error.inner_text().strip()):
                    return True
        except Exception:
            pass
        try:
            body_text = self.page.locator("body").inner_text()
        except Exception:
            return False
        return bool(error_pattern.search(body_text))

    def _is_access_denied(self) -> bool:
        try:
            body_text = self.page.locator("body").inner_text()
        except Exception:
            return False
        return isinstance(body_text, str) and bool(ACCESS_DENIED_PATTERN.search(body_text))

    def _has_visible(self, selector: str) -> bool:
        locator = self.page.locator(selector)
        try:
            return any(locator.nth(index).is_visible() for index in range(locator.count()))
        except Exception:
            return False

    @staticmethod
    def _visible_text(locator: Any) -> str:
        try:
            if locator.count() and locator.is_visible():
                return locator.inner_text().strip()
        except Exception:
            pass
        return ""
