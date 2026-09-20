from __future__ import annotations

from typing import Any

from naukri_automation.config import ConfigurationError

SERVICE_NAME = "naukri-resume-automation"


class CredentialStore:
    def __init__(self, backend: Any | None = None) -> None:
        self._backend = backend

    def _keyring(self) -> Any:
        if self._backend is not None:
            return self._backend
        try:
            import keyring
            from keyring.errors import KeyringError, NoKeyringError
        except ImportError as error:
            raise ConfigurationError(
                "OS credential support is unavailable; install project dependencies"
            ) from error
        self._error_types = (KeyringError, NoKeyringError)
        return keyring

    def set(self, profile_name: str, password: str) -> None:
        if not password:
            raise ConfigurationError("password cannot be empty")
        keyring = self._keyring()
        try:
            keyring.set_password(SERVICE_NAME, profile_name, password)
        except getattr(self, "_error_types", Exception) as error:
            raise ConfigurationError("could not store password in the OS keyring") from error

    def get(self, profile_name: str) -> str | None:
        keyring = self._keyring()
        try:
            return keyring.get_password(SERVICE_NAME, profile_name)
        except getattr(self, "_error_types", Exception) as error:
            raise ConfigurationError("could not read password from the OS keyring") from error

    def remove(self, profile_name: str) -> bool:
        keyring = self._keyring()
        if self.get(profile_name) is None:
            return False
        try:
            keyring.delete_password(SERVICE_NAME, profile_name)
        except getattr(self, "_error_types", Exception) as error:
            raise ConfigurationError("could not remove password from the OS keyring") from error
        return True

    def has(self, profile_name: str) -> bool:
        return self.get(profile_name) is not None
