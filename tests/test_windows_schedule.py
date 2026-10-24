from __future__ import annotations

import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from subprocess import CalledProcessError, CompletedProcess
from unittest.mock import patch

from naukri_automation.config import ScheduleConfig
from naukri_automation.scheduling.windows import (
    TASK_NAMESPACE,
    SchedulerError,
    WindowsScheduler,
    build_task_xml,
)

NS = {"task": TASK_NAMESPACE}


class WindowsScheduleTests(unittest.TestCase):
    def test_daily_task_uses_current_user_and_safety_settings(self) -> None:
        xml = build_task_xml(
            ScheduleConfig(frequency="daily", time="09:30", wake_computer=True),
            python_executable=Path("/opt/python/bin/python"),
            user_id=r"workstation\person",
            config_path=Path("/tmp/config.toml"),
            now=datetime.fromisoformat("2026-09-20T08:00:00+05:30"),
        )
        root = ET.fromstring(xml)
        trigger = root.find(".//task:CalendarTrigger", namespaces=NS)

        self.assertIsNotNone(trigger)
        assert trigger is not None
        self.assertEqual(
            ["Enabled", "StartBoundary", "ScheduleByDay"],
            [child.tag.rsplit("}", 1)[-1] for child in trigger],
        )
        self.assertEqual(
            r"workstation\person",
            root.findtext(".//task:UserId", namespaces=NS),
        )
        self.assertEqual(
            "InteractiveToken",
            root.findtext(".//task:LogonType", namespaces=NS),
        )
        self.assertEqual(
            "LeastPrivilege",
            root.findtext(".//task:RunLevel", namespaces=NS),
        )
        self.assertEqual("true", root.findtext(".//task:WakeToRun", namespaces=NS))
        self.assertEqual(
            "IgnoreNew",
            root.findtext(".//task:MultipleInstancesPolicy", namespaces=NS),
        )
        self.assertIsNotNone(root.find(".//task:ScheduleByDay", namespaces=NS))
        arguments = root.findtext(".//task:Arguments", namespaces=NS)
        self.assertIn("-m naukri_automation", arguments or "")
        self.assertNotIn("SYSTEM", xml.upper())
        self.assertNotIn("RestartOnFailure", xml)

    def test_weekly_task_contains_selected_days(self) -> None:
        xml = build_task_xml(
            ScheduleConfig(
                frequency="weekly",
                time="07:00",
                days=("MON", "FRI"),
            ),
            python_executable=Path("/opt/python/bin/python"),
            user_id=r"workstation\person",
            config_path=Path("/tmp/config.toml"),
            now=datetime.fromisoformat("2026-09-20T08:00:00+05:30"),
        )
        root = ET.fromstring(xml)

        self.assertIsNotNone(root.find(".//task:Monday", namespaces=NS))
        self.assertIsNotNone(root.find(".//task:Friday", namespaces=NS))
        self.assertIsNotNone(root.find(".//task:ScheduleByWeek", namespaces=NS))

    def test_profile_task_invokes_selected_profile(self) -> None:
        xml = build_task_xml(
            ScheduleConfig(frequency="daily", time="09:30"),
            python_executable=Path("/opt/python/bin/python"),
            user_id=r"workstation\person",
            profile_name="personal",
            working_directory=Path("/tmp/profile"),
            now=datetime.fromisoformat("2026-09-20T08:00:00+05:30"),
        )
        root = ET.fromstring(xml)

        arguments = root.findtext(".//task:Arguments", namespaces=NS)
        self.assertEqual(
            '-m naukri_automation run --profile "personal"',
            arguments,
        )

    def test_current_user_id_uses_windows_identity(self) -> None:
        completed = CompletedProcess(
            args=["whoami.exe"],
            returncode=0,
            stdout="workstation\\person\n",
            stderr="",
        )
        with patch("naukri_automation.scheduling.windows.subprocess.run", return_value=completed):
            self.assertEqual(r"workstation\person", WindowsScheduler.current_user_id())

    def test_scheduler_error_includes_native_stderr(self) -> None:
        failure = CalledProcessError(
            1,
            ["schtasks.exe", "/Create"],
            stderr="ERROR: The task XML is invalid.",
        )
        with (
            patch("naukri_automation.scheduling.windows.sys.platform", "win32"),
            patch("naukri_automation.scheduling.windows.subprocess.run", side_effect=failure),
            self.assertRaisesRegex(SchedulerError, "task XML is invalid"),
            tempfile.TemporaryDirectory() as directory,
        ):
            WindowsScheduler().install("<Task />", Path(directory) / "task.xml")


if __name__ == "__main__":
    unittest.main()
