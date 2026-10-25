from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout

from resume_automation.cli import _print_run_guidance
from resume_automation.result import Outcome


class CliGuidanceTests(unittest.TestCase):
    def test_dry_run_points_to_controlled_upload(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _print_run_guidance(Outcome.DRY_RUN_SUCCESS, "personal")

        self.assertEqual(
            "Next: resume-auto run --profile personal --headed\n",
            output.getvalue(),
        )

    def test_success_points_to_schedule_configuration(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            _print_run_guidance(Outcome.SUCCESS, "personal")

        self.assertEqual(
            "Next: resume-auto schedule set --profile personal --times 09:00,18:00\n",
            output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
