from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from resume_automation import __version__


class PackagingTests(unittest.TestCase):
    def test_distribution_version_and_cli_entry_point_are_consistent(self) -> None:
        document = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
        project = document["project"]
        setuptools = document["tool"]["setuptools"]

        self.assertEqual("resume-automation", project["name"])
        self.assertEqual("0.2.1", __version__)
        self.assertIn("version", project["dynamic"])
        self.assertEqual(
            "resume_automation.__version__",
            setuptools["dynamic"]["version"]["attr"],
        )
        self.assertEqual("resume_automation.cli:main", project["scripts"]["resume-auto"])
        self.assertNotIn("naukri-auto", project["scripts"])
        self.assertEqual(
            "https://github.com/Pulkit3108/resume-automation",
            project["urls"]["Source"],
        )


if __name__ == "__main__":
    unittest.main()
