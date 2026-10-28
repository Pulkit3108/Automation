from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Protocol


class AuthState(StrEnum):
    AUTHENTICATED = "AUTHENTICATED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    CHALLENGE_REQUIRED = "CHALLENGE_REQUIRED"
    ACCESS_DENIED = "ACCESS_DENIED"
    UNKNOWN = "UNKNOWN"


class AuthenticationRequired(RuntimeError):
    pass


class SiteContractError(RuntimeError):
    pass


class PortalAccessDenied(RuntimeError):
    pass


class UploadVerificationError(RuntimeError):
    pass


class PortalProvider(Protocol):
    def open_login(self) -> None: ...

    def open_profile(self) -> None: ...

    def fill_login(self, username: str, password: str) -> bool: ...

    def submit_login(self) -> bool: ...

    def wait_for_login_result(self) -> AuthState: ...

    def wait_for_auth_state(self) -> AuthState: ...

    def inspect_resume_section(self) -> str: ...

    def upload_resume(self, resume_path: Path) -> str: ...
