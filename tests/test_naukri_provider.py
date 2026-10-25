from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from resume_automation.providers.base import AuthState, UploadVerificationError
from resume_automation.providers.naukri import (
    AUTHENTICATED_SELECTOR,
    CHALLENGE_SELECTOR,
    LOGIN_BUTTON_SELECTOR,
    LOGIN_ERROR_SELECTOR,
    LOGIN_URL,
    PASSWORD_SELECTOR,
    PROFILE_URL,
    RESUME_SELECTOR,
    UPDATE_EVIDENCE_SELECTOR,
    USERNAME_SELECTOR,
    NaukriProvider,
)


class NaukriProviderTests(unittest.TestCase):
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
        site = NaukriProvider(page, timeout_seconds=10)

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
        site = NaukriProvider(page, timeout_seconds=10)

        filled = site.fill_login("person@example.test", "secret")

        self.assertTrue(filled)
        username.wait_for.assert_called_once_with(state="visible", timeout=10_000)
        password.wait_for.assert_called_once_with(state="visible", timeout=10_000)
        username.fill.assert_called_once_with("person@example.test")
        password.fill.assert_called_once_with("secret")

    def test_login_submission_clicks_visible_button(self) -> None:
        page = MagicMock()
        button = _locator()
        page.locator.return_value = button
        site = NaukriProvider(page, timeout_seconds=10)

        self.assertTrue(site.submit_login())

        page.locator.assert_called_once_with(LOGIN_BUTTON_SELECTOR)
        button.wait_for.assert_called_once_with(state="visible", timeout=10_000)
        button.click.assert_called_once_with()

    def test_open_login_uses_visible_login_link_when_form_is_absent(self) -> None:
        page = MagicMock()
        form = _locator()
        form.wait_for.side_effect = RuntimeError("form not visible")
        button = _locator(count=0)
        link = _locator()
        link.is_visible.return_value = True
        page.locator.return_value = form
        page.get_by_role.side_effect = lambda role, **kwargs: (
            button if role == "button" else link
        )
        site = NaukriProvider(page, timeout_seconds=10)

        site.open_login()

        page.goto.assert_called_once_with(LOGIN_URL, wait_until="domcontentloaded")
        link.click.assert_called_once_with()

    def test_invalid_credentials_are_classified(self) -> None:
        page = MagicMock()
        page.url = LOGIN_URL
        authenticated = _locator(count=0)
        errors = _locator()
        errors.inner_text.return_value = (
            "Invalid details. Please check the Email ID - Password combination."
        )
        challenge = _locator(count=0)
        username = _locator(count=1)
        page.locator.side_effect = lambda selector: {
            AUTHENTICATED_SELECTOR: authenticated,
            LOGIN_ERROR_SELECTOR: errors,
            CHALLENGE_SELECTOR: challenge,
            USERNAME_SELECTOR: username,
        }[selector]
        site = NaukriProvider(page, timeout_seconds=10)

        self.assertEqual(AuthState.INVALID_CREDENTIALS, site.auth_state())

    def test_hidden_captcha_does_not_skip_login_form(self) -> None:
        page = MagicMock()
        page.url = LOGIN_URL
        authenticated = _locator(count=0)
        errors = _locator(count=0)
        body = _locator()
        body.inner_text.return_value = "Login"
        challenge = _locator()
        challenge.is_visible.return_value = False
        username = _locator(count=1)
        page.locator.side_effect = lambda selector: {
            AUTHENTICATED_SELECTOR: authenticated,
            LOGIN_ERROR_SELECTOR: errors,
            "body": body,
            CHALLENGE_SELECTOR: challenge,
            USERNAME_SELECTOR: username,
        }[selector]
        site = NaukriProvider(page, timeout_seconds=10)

        self.assertEqual(AuthState.LOGIN_REQUIRED, site.auth_state())

    def test_wait_for_login_result_is_bounded(self) -> None:
        page = MagicMock()
        page.url = PROFILE_URL
        authenticated = _locator(count=1)
        page.locator.return_value = authenticated
        site = NaukriProvider(page, timeout_seconds=10)

        state = site.wait_for_login_result()

        self.assertEqual(AuthState.AUTHENTICATED, state)
        page.wait_for_function.assert_called_once()

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
        site = NaukriProvider(page, timeout_seconds=10)

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
        page.wait_for_function.side_effect = RuntimeError("no post-upload change")
        site = NaukriProvider(page, timeout_seconds=10)

        with (
            patch.object(site, "inspect_resume_section"),
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
        site = NaukriProvider(page, timeout_seconds=10)

        with patch.object(site, "inspect_resume_section"):
            evidence = site.upload_resume(Path("resume.pdf"))

        self.assertEqual("Resume uploaded successfully", evidence)
        resume.set_input_files.assert_called_once_with("resume.pdf")
        page.wait_for_function.assert_called_once()

    def test_changed_update_text_proves_upload_without_sequential_waits(self) -> None:
        page = MagicMock()
        resume = _locator()
        filename = _locator()
        filename.is_visible.return_value = True
        filename.inner_text.return_value = "resume.pdf"
        confirmation = _locator(count=0)
        update = _locator()
        update.is_visible.return_value = True
        update.inner_text.side_effect = ["Updated yesterday", "Updated just now"]
        page.locator.side_effect = lambda selector: {
            RESUME_SELECTOR: resume,
            UPDATE_EVIDENCE_SELECTOR: update,
        }[selector]
        page.get_by_text.side_effect = lambda value, **kwargs: (
            filename if value == "resume.pdf" else confirmation
        )
        site = NaukriProvider(page, timeout_seconds=10)

        with patch.object(site, "inspect_resume_section"):
            evidence = site.upload_resume(Path("resume.pdf"))

        self.assertEqual("Updated just now", evidence)
        page.wait_for_function.assert_called_once()


def _locator(*, count: int = 1) -> MagicMock:
    locator = MagicMock()
    locator.first = locator
    locator.count.return_value = count
    locator.nth.return_value = locator
    locator.is_visible.return_value = count > 0
    return locator


if __name__ == "__main__":
    unittest.main()
