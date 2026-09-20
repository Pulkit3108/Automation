from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from naukri_automation.config import AppConfig
from naukri_automation.paths import AppPaths
from naukri_automation.result import Outcome
from naukri_automation.workflow import execute


class FakeBrowser:
    def __init__(self, profile_dir: Path, **kwargs: Any) -> None:
        self.page = object()
        self.captured = False

    def __enter__(self) -> FakeBrowser:
        return self

    def __exit__(self, *args: Any) -> None:
        return None

    def capture_failure(self, artifact_dir: Path) -> None:
        self.captured = True


class FakeSite:
    upload_called = False

    def __init__(self, page: object, **kwargs: Any) -> None:
        pass

    def open_profile(self) -> None:
        pass

    def inspect_resume_section(self) -> str:
        return "resume section available"

    def upload_resume(self, resume_path: Path) -> str:
        type(self).upload_called = True
        return resume_path.name


class WorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSite.upload_called = False

    def test_dry_run_cannot_upload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, paths = self._fixture(Path(directory))

            result = execute(
                config,
                paths,
                dry_run=True,
                browser_factory=FakeBrowser,
                site_factory=FakeSite,
            )

            self.assertEqual(Outcome.DRY_RUN_SUCCESS, result.outcome)
            self.assertFalse(FakeSite.upload_called)

    def test_normal_run_uploads_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config, paths = self._fixture(Path(directory))

            result = execute(
                config,
                paths,
                browser_factory=FakeBrowser,
                site_factory=FakeSite,
            )

            self.assertEqual(Outcome.SUCCESS, result.outcome)
            self.assertTrue(FakeSite.upload_called)
            self.assertTrue(paths.last_result.is_file())

    @staticmethod
    def _fixture(root: Path) -> tuple[AppConfig, AppPaths]:
        resume = root / "resume.pdf"
        resume.write_bytes(b"%PDF-test")
        config = AppConfig(resume_path=resume)
        paths = AppPaths(config_dir=root / "config", data_dir=root / "data")
        return config, paths


if __name__ == "__main__":
    unittest.main()
