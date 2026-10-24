from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from naukri_automation.naukri_site import (
    AUTHENTICATED_SELECTOR,
    LOGIN_URL,
    PASSWORD_SELECTOR,
    PROFILE_URL,
    RESUME_SELECTOR,
    UPDATE_EVIDENCE_SELECTOR,
    USERNAME_SELECTOR,
    AuthState,
    NaukriSite,
    UploadVerificationError,
)


class NaukriSiteTests(unittest.TestCase):
    def test_waits_for_authenticated_marker_before_deciding_state(self) -> None:
        page = MagicMock()
        page.url = LOGIN_URL
        state_marker = _locator()
        username = _locator(count=0)
        authenticated = _locator(count=1)
        page.locator.side_effect = lambda selector: {
            f"{USERNAME_SELECTOR}, {AUTHENTICATED_SELECTOR}": state_marker,
            USERNAME_SELECTOR: username,
            AUTHENTICATED_SELECTOR: authenticated,
        }[selector]
        site = NaukriSite(page, timeout_seconds=10)

        state = site.wait_for_auth_state()

        self.assertEqual(AuthState.AUTHENTICATED, state)
        state_marker.wait_for.assert_called_once_with(state="attached", timeout=10_000)

    def test_login_fill_waits_for_both_fields(self) -> None:
        page = MagicMock()
        username = _locator()
        password = _locator()
        page.locator.side_effect = lambda selector: {
            USERNAME_SELECTOR: username,
            PASSWORD_SELECTOR: password,
        }[selector]
        site = NaukriSite(page, timeout_seconds=10)

        filled = site.fill_login("person@example.test", "secret")

        self.assertTrue(filled)
        username.wait_for.assert_called_once_with(state="visible", timeout=10_000)
        password.wait_for.assert_called_once_with(state="visible", timeout=10_000)
        username.fill.assert_called_once_with("person@example.test")
        password.fill.assert_called_once_with("secret")

    def test_resume_inspection_waits_for_async_control(self) -> None:
        page = MagicMock()
        page.url = PROFILE_URL
        state_marker = _locator()
        username = _locator(count=0)
        authenticated = _locator(count=1)
        resume = _locator()
        evidence = _locator(count=0)
        page.locator.side_effect = lambda selector: {
            f"{USERNAME_SELECTOR}, {AUTHENTICATED_SELECTOR}": state_marker,
            USERNAME_SELECTOR: username,
            AUTHENTICATED_SELECTOR: authenticated,
            RESUME_SELECTOR: resume,
            UPDATE_EVIDENCE_SELECTOR: evidence,
        }[selector]
        site = NaukriSite(page, timeout_seconds=10)

        result = site.inspect_resume_section()

        self.assertEqual("resume upload control is available", result)
        resume.wait_for.assert_called_once_with(state="attached", timeout=10_000)

    def test_preexisting_filename_does_not_prove_upload_success(self) -> None:
        page = MagicMock()
        resume = _locator()
        filename = _locator()
        filename.is_visible.return_value = True
        filename.inner_text.return_value = "resume.pdf"
        confirmation = _locator()
        confirmation.wait_for.side_effect = RuntimeError("no success message")
        update = _locator()
        update.is_visible.return_value = True
        update.inner_text.return_value = "Updated yesterday"
        page.locator.side_effect = lambda selector: {
            RESUME_SELECTOR: resume,
            UPDATE_EVIDENCE_SELECTOR: update,
        }[selector]
        page.get_by_text.side_effect = lambda value, **kwargs: (
            filename if value == "resume.pdf" else confirmation
        )
        site = NaukriSite(page, timeout_seconds=10)
        expectation = MagicMock()
        expectation.not_to_have_text.side_effect = AssertionError("update text did not change")

        with (
            patch.object(site, "inspect_resume_section"),
            patch("playwright.sync_api.expect", return_value=expectation),
            self.assertRaises(UploadVerificationError),
        ):
            site.upload_resume(Path("resume.pdf"))

        resume.set_input_files.assert_called_once_with("resume.pdf")

    def test_success_message_proves_upload_success(self) -> None:
        page = MagicMock()
        resume = _locator()
        filename = _locator()
        filename.is_visible.return_value = True
        filename.inner_text.return_value = "resume.pdf"
        confirmation = _locator()
        confirmation.inner_text.return_value = "Resume uploaded successfully"
        update = _locator(count=0)
        page.locator.side_effect = lambda selector: {
            RESUME_SELECTOR: resume,
            UPDATE_EVIDENCE_SELECTOR: update,
        }[selector]
        page.get_by_text.side_effect = lambda value, **kwargs: (
            filename if value == "resume.pdf" else confirmation
        )
        site = NaukriSite(page, timeout_seconds=10)

        with patch.object(site, "inspect_resume_section"):
            evidence = site.upload_resume(Path("resume.pdf"))

        self.assertEqual("Resume uploaded successfully", evidence)
        resume.set_input_files.assert_called_once_with("resume.pdf")


def _locator(*, count: int = 1) -> MagicMock:
    locator = MagicMock()
    locator.first = locator
    locator.count.return_value = count
    return locator


if __name__ == "__main__":
    unittest.main()
