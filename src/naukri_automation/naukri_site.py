from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path
from typing import Any

LOGIN_URL = "https://www.naukri.com/nlogin/login"
PROFILE_URL = "https://www.naukri.com/mnjuser/profile"


class AuthState(StrEnum):
    AUTHENTICATED = "AUTHENTICATED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
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
        username_input = self.page.locator(
            'input#usernameField, input#emailTxt, input[name="username"]'
        ).first
        password_input = self.page.locator(
            'input#passwordField, input#pwd1, input[type="password"]'
        ).first
        if username_input.count() == 0 or password_input.count() == 0:
            return False
        username_input.fill(username)
        password_input.fill(password)
        return True

    def auth_state(self) -> AuthState:
        current_url = self.page.url.lower()
        if "/nlogin/" in current_url or self._count(
            'input#usernameField, input#emailTxt, input[name="username"]'
        ):
            return AuthState.LOGIN_REQUIRED
        if self._count(
            'a[href="/mnjuser/profile"], .view-profile-wrapper, input#attachCV, '
            'input[type="file"][name*="resume" i]'
        ):
            return AuthState.AUTHENTICATED
        return AuthState.UNKNOWN

    def inspect_resume_section(self) -> str:
        state = self.auth_state()
        if state == AuthState.LOGIN_REQUIRED:
            raise AuthenticationRequired("Naukri login is required")
        if state == AuthState.UNKNOWN:
            raise SiteContractError("could not confirm the Naukri profile page")

        resume_input = self._resume_input()
        if resume_input.count() == 0:
            raise SiteContractError("resume upload control was not found")

        evidence = self.page.locator(
            '.updateOn, [class*="updateOn"], [class*="resume"] [class*="date"]'
        ).first
        if evidence.count():
            text = evidence.inner_text().strip()
            if text:
                return text
        return "resume upload control is available"

    def upload_resume(self, resume_path: Path) -> str:
        self.inspect_resume_section()
        resume_input = self._resume_input().first
        resume_input.set_input_files(str(resume_path))

        filename = resume_path.name
        filename_evidence = self.page.get_by_text(filename, exact=False).first
        try:
            filename_evidence.wait_for(state="visible", timeout=self.timeout_ms)
            return filename_evidence.inner_text().strip() or filename
        except Exception:
            confirmation = self.page.get_by_text(
                re.compile(r"resume (uploaded|updated) successfully", re.IGNORECASE)
            ).first
            try:
                confirmation.wait_for(state="visible", timeout=self.timeout_ms)
                text = confirmation.inner_text().strip()
                if text:
                    return text
            except Exception:
                update_evidence = self.page.locator(
                    '[class*="updateOn"], [class*="upload"] [class*="success"]'
                ).first
                try:
                    update_evidence.wait_for(state="visible", timeout=self.timeout_ms)
                    text = update_evidence.inner_text().strip()
                    if text:
                        return text
                except Exception as error:
                    raise UploadVerificationError(
                        "upload was attempted but success could not be verified"
                    ) from error

        raise UploadVerificationError("upload success evidence was empty")

    def _resume_input(self) -> Any:
        return self.page.locator(
            'input#attachCV[type="file"], input[type="file"][name*="resume" i], '
            'input[type="file"][accept*="pdf" i]'
        )

    def _count(self, selector: str) -> int:
        return self.page.locator(selector).count()
