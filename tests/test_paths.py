from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from resume_automation.paths import get_app_paths


class PathTests(unittest.TestCase):
    def test_windows_paths_use_generic_application_namespace(self) -> None:
        environment = {
            "APPDATA": r"C:\Users\person\AppData\Roaming",
            "LOCALAPPDATA": r"C:\Users\person\AppData\Local",
        }
        with (
            patch("resume_automation.paths.sys.platform", "win32"),
            patch.dict(os.environ, environment, clear=True),
        ):
            paths = get_app_paths()

        self.assertEqual(Path(environment["APPDATA"]) / "ResumeAutomation", paths.config_dir)
        self.assertEqual(
            Path(environment["LOCALAPPDATA"]) / "ResumeAutomation",
            paths.data_dir,
        )

    def test_explicit_path_overrides_are_supported(self) -> None:
        with patch.dict(
            os.environ,
            {
                "RESUME_AUTO_CONFIG_DIR": "/tmp/resume-config",
                "RESUME_AUTO_DATA_DIR": "/tmp/resume-data",
            },
            clear=True,
        ):
            paths = get_app_paths()

        self.assertEqual(Path("/tmp/resume-config"), paths.config_dir)
        self.assertEqual(Path("/tmp/resume-data"), paths.data_dir)


if __name__ == "__main__":
    unittest.main()
