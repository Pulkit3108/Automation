from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from naukri_automation.cli import build_parser
from naukri_automation.config import ConfigurationError
from naukri_automation.credentials import SERVICE_NAME, CredentialStore
from naukri_automation.paths import AppPaths
from naukri_automation.profile_cli import handle_management_command
from naukri_automation.profile_store import (
    create_profile,
    import_resume,
    list_profiles,
    list_resumes,
    load_profile,
    remove_resume,
    resolve_profile_name,
    select_resume,
    set_default_profile,
)


class FakeKeyring:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def set_password(self, service: str, username: str, password: str) -> None:
        self.values[(service, username)] = password

    def get_password(self, service: str, username: str) -> str | None:
        return self.values.get((service, username))

    def delete_password(self, service: str, username: str) -> None:
        del self.values[(service, username)]


class ProfileTests(unittest.TestCase):
    def test_profile_create_command_uses_hidden_keyring_password(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "data")
            resume = root / "resume.pdf"
            resume.write_bytes(b"%PDF-test")
            backend = FakeKeyring()
            store = CredentialStore(backend)
            args = build_parser().parse_args(
                [
                    "profile",
                    "create",
                    "Personal",
                    "--username",
                    "person@example.test",
                    "--resume",
                    str(resume),
                ]
            )

            with (
                patch("naukri_automation.profile_cli.getpass.getpass", return_value="secret"),
                patch("naukri_automation.profile_cli.CredentialStore", return_value=store),
            ):
                result = handle_management_command(args, paths)

            self.assertEqual(0, result)
            self.assertTrue(store.has("personal"))
            self.assertEqual("personal", resolve_profile_name(paths, None))

    def test_profile_owns_managed_resumes_and_default_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "data")
            first = root / "first.pdf"
            second = root / "second.pdf"
            first.write_bytes(b"%PDF-first")
            second.write_bytes(b"%PDF-second")

            config, profile_paths = create_profile(
                paths,
                name="Personal",
                username="person@example.test",
                resume_source=first,
            )
            set_default_profile(paths, "personal")
            managed_second = import_resume(profile_paths, second)
            selected = select_resume(config, profile_paths, managed_second.name)

            self.assertEqual(["personal"], list_profiles(paths))
            self.assertEqual("personal", resolve_profile_name(paths, None))
            self.assertEqual(profile_paths.resumes / "first.pdf", config.resume_path)
            self.assertEqual("second.pdf", selected.resume_path.name)
            self.assertEqual(2, len(list_resumes(profile_paths)))
            remove_resume(selected, profile_paths, "first.pdf")
            self.assertEqual(["second.pdf"], [path.name for path in list_resumes(profile_paths)])
            self.assertEqual(selected, load_profile(paths, "personal"))

    def test_active_resume_cannot_be_removed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "data")
            resume = root / "resume.pdf"
            resume.write_bytes(b"%PDF-test")
            config, profile_paths = create_profile(
                paths,
                name="personal",
                username="person@example.test",
                resume_source=resume,
            )

            with self.assertRaisesRegex(ConfigurationError, "active resume"):
                remove_resume(config, profile_paths, "resume.pdf")

    def test_credentials_use_profile_key_without_exposing_password(self) -> None:
        backend = FakeKeyring()
        store = CredentialStore(backend)

        store.set("personal", "secret-value")

        self.assertTrue(store.has("personal"))
        self.assertEqual("secret-value", backend.values[(SERVICE_NAME, "personal")])
        self.assertTrue(store.remove("personal"))
        self.assertFalse(store.has("personal"))


if __name__ == "__main__":
    unittest.main()
