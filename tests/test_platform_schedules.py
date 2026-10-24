from __future__ import annotations

import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from naukri_automation.config import ScheduleConfig, ScheduleRule
from naukri_automation.scheduling.linux import LinuxScheduler, _calendar_expressions
from naukri_automation.scheduling.macos import MacOSScheduler, _calendar_intervals


class PlatformScheduleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schedule = ScheduleConfig(
            rules=(
                ScheduleRule(times=("09:00", "18:00")),
                ScheduleRule(times=("13:30",), days=("MON", "WED", "FRI")),
                ScheduleRule(times=("10:15",), days=("SUN",)),
            )
        )

    def test_macos_calendar_intervals_cover_every_rule(self) -> None:
        intervals = _calendar_intervals(self.schedule)

        self.assertEqual({"Hour": 9, "Minute": 0}, intervals[0])
        self.assertEqual({"Hour": 18, "Minute": 0}, intervals[1])
        self.assertIn({"Weekday": 2, "Hour": 13, "Minute": 30}, intervals)
        self.assertIn({"Weekday": 1, "Hour": 10, "Minute": 15}, intervals)
        self.assertEqual(6, len(intervals))

    def test_linux_calendar_expressions_cover_every_rule(self) -> None:
        self.assertEqual(
            [
                "*-*-* 09:00:00",
                "*-*-* 18:00:00",
                "Mon,Wed,Fri *-*-* 13:30:00",
                "Sun *-*-* 10:15:00",
            ],
            _calendar_expressions(self.schedule),
        )

    def test_macos_install_writes_persistent_launch_agent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scheduler = MacOSScheduler("personal", home=root, uid=501)
            with (
                patch.object(scheduler, "_run", return_value=""),
                patch("naukri_automation.scheduling.macos.subprocess.run"),
            ):
                scheduler.install_schedule(
                    self.schedule,
                    python_executable=root / "venv/bin/python",
                    working_directory=root / "config",
                    data_directory=root / "data",
                    profile_name="personal",
                )

            payload = plistlib.loads(scheduler.plist_path.read_bytes())
            self.assertEqual("com.naukri-resume-automation.personal", payload["Label"])
            self.assertEqual(6, len(payload["StartCalendarInterval"]))
            self.assertEqual("personal", payload["ProgramArguments"][-1])

    def test_linux_install_writes_enabled_user_units(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scheduler = LinuxScheduler("personal", home=root)
            with patch.object(scheduler, "_run", return_value="") as run:
                scheduler.install_schedule(
                    self.schedule,
                    python_executable=root / "venv/bin/python",
                    working_directory=root / "config",
                    data_directory=root / "data",
                    profile_name="personal",
                )

            service = scheduler.service_path.read_text(encoding="utf-8")
            timer = scheduler.timer_path.read_text(encoding="utf-8")
            self.assertIn("-m naukri_automation run --profile personal", service)
            self.assertIn("OnCalendar=Mon,Wed,Fri *-*-* 13:30:00", timer)
            self.assertIn("Persistent=false", timer)
            run.assert_any_call("enable", "--now", "naukri-resume-automation-personal.timer")


if __name__ == "__main__":
    unittest.main()
