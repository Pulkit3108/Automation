from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch

from resume_automation.cli import build_parser
from resume_automation.paths import AppPaths
from resume_automation.profile_store import create_profile, load_profile
from resume_automation.schedule_cli import handle_schedule


class ScheduleCliTests(unittest.TestCase):
    def test_set_and_add_create_independent_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "data")
            resume = root / "resume.pdf"
            resume.write_bytes(b"%PDF-test")
            create_profile(
                paths,
                name="personal",
                username="person@example.test",
                resume_source=resume,
            )
            set_args = build_parser().parse_args(
                [
                    "schedule",
                    "set",
                    "--profile",
                    "personal",
                    "--times",
                    "08:30,17:30",
                    "--days",
                    "MON,FRI",
                ]
            )
            add_args = build_parser().parse_args(
                [
                    "schedule",
                    "add",
                    "--profile",
                    "personal",
                    "--times",
                    "10:15",
                    "--days",
                    "SUN",
                ]
            )
            profile_paths = paths.profile("personal")

            for args in (set_args, add_args):
                self.assertEqual(
                    0,
                    handle_schedule(
                        args,
                        profile_paths.config_file,
                        profile_paths,
                        "personal",
                        python_executable=Path("/opt/python"),
                    ),
                )

            updated = load_profile(paths, "personal")
            self.assertEqual(2, len(updated.schedule.rules))
            self.assertEqual(("08:30", "17:30"), updated.schedule.rules[0].times)
            self.assertEqual(("MON", "FRI"), updated.schedule.rules[0].days)
            self.assertEqual(("10:15",), updated.schedule.rules[1].times)
            self.assertEqual(("SUN",), updated.schedule.rules[1].days)

    def test_show_is_compact_by_default_and_verbose_on_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = AppPaths(root / "config", root / "data")
            resume = root / "resume.pdf"
            resume.write_bytes(b"%PDF-test")
            _, profile_paths = create_profile(
                paths,
                name="personal",
                username="person@example.test",
                resume_source=resume,
            )
            scheduler = MagicMock()
            scheduler.show.side_effect = lambda **options: (
                "native details" if options.get("verbose") else "Task: test\nStatus: Ready"
            )

            with patch(
                "resume_automation.schedule_cli.scheduler_for_profile",
                return_value=scheduler,
            ):
                compact = io.StringIO()
                with redirect_stdout(compact):
                    handle_schedule(
                        build_parser().parse_args(
                            ["schedule", "show", "--profile", "personal"]
                        ),
                        profile_paths.config_file,
                        profile_paths,
                        "personal",
                        python_executable=Path("/opt/python"),
                    )
                verbose = io.StringIO()
                with redirect_stdout(verbose):
                    handle_schedule(
                        build_parser().parse_args(
                            [
                                "schedule",
                                "show",
                                "--profile",
                                "personal",
                                "--verbose",
                            ]
                        ),
                        profile_paths.config_file,
                        profile_paths,
                        "personal",
                        python_executable=Path("/opt/python"),
                    )

            self.assertIn("Profile: personal", compact.getvalue())
            self.assertIn("Schedule: every day at 09:00", compact.getvalue())
            self.assertIn("Status: Ready", compact.getvalue())
            self.assertEqual("native details\n", verbose.getvalue())


if __name__ == "__main__":
    unittest.main()
