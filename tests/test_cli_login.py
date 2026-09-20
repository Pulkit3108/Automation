from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from naukri_automation.cli import _login
from naukri_automation.config import AppConfig, write_config
from naukri_automation.naukri_site import AuthState
from naukri_automation.paths import ProfilePaths


class _FakeBrowserSession:
    def __init__(self, *, closed: bool = True) -> None:
        self.page = MagicMock()
        self.page.is_closed.return_value = closed

    def __enter__(self) -> _FakeBrowserSession:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class LoginCommandTests(unittest.TestCase):
    def test_existing_authenticated_session_returns_without_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._profile_fixture(Path(directory))
            session = _FakeBrowserSession(closed=False)
            site = MagicMock()
            site.wait_for_auth_state.return_value = AuthState.AUTHENTICATED

            with (
                patch("naukri_automation.cli.sys.stdin.isatty", return_value=True),
                patch("naukri_automation.cli.BrowserSession", return_value=session),
                patch("naukri_automation.cli.NaukriSite", return_value=site),
                patch("naukri_automation.cli.CredentialStore.get") as get_password,
                patch("builtins.input") as prompt,
            ):
                result = _login(paths.config_file, paths, "personal")

            self.assertEqual(0, result)
            get_password.assert_not_called()
            prompt.assert_not_called()

    def test_closed_browser_returns_clean_login_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self._profile_fixture(Path(directory))
            session = _FakeBrowserSession()
            site = MagicMock()
            site.wait_for_auth_state.return_value = AuthState.LOGIN_REQUIRED

            with (
                patch("naukri_automation.cli.sys.stdin.isatty", return_value=True),
                patch("naukri_automation.cli.BrowserSession", return_value=session),
                patch("naukri_automation.cli.NaukriSite", return_value=site),
                patch("naukri_automation.cli.CredentialStore.get", return_value=None),
                patch("builtins.input", return_value=""),
            ):
                result = _login(paths.config_file, paths, "personal")

            self.assertEqual(3, result)

    @staticmethod
    def _profile_fixture(root: Path) -> ProfilePaths:
        paths = ProfilePaths(
            name="personal",
            config_dir=root / "config",
            data_dir=root / "data",
        )
        resume = paths.data_dir / "resumes" / "resume.pdf"
        resume.parent.mkdir(parents=True)
        resume.write_bytes(b"%PDF-test")
        config = AppConfig(
            resume_path=resume,
            profile_name="personal",
            username="person@example.test",
        )
        write_config(config, paths.config_file)
        return paths


if __name__ == "__main__":
    unittest.main()
