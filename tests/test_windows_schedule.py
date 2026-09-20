from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from naukri_automation.config import ScheduleConfig
from naukri_automation.scheduling.windows import TASK_NAMESPACE, build_task_xml

NS = {"task": TASK_NAMESPACE}


class WindowsScheduleTests(unittest.TestCase):
    def test_daily_task_uses_current_user_and_safety_settings(self) -> None:
        xml = build_task_xml(
            ScheduleConfig(frequency="daily", time="09:30", wake_computer=True),
            python_executable=Path("/opt/python/bin/python"),
            config_path=Path("/tmp/config.toml"),
            now=datetime.fromisoformat("2026-09-20T08:00:00+05:30"),
        )
        root = ET.fromstring(xml)

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
            config_path=Path("/tmp/config.toml"),
            now=datetime.fromisoformat("2026-09-20T08:00:00+05:30"),
        )
        root = ET.fromstring(xml)

        self.assertIsNotNone(root.find(".//task:Monday", namespaces=NS))
        self.assertIsNotNone(root.find(".//task:Friday", namespaces=NS))
        self.assertIsNotNone(root.find(".//task:ScheduleByWeek", namespaces=NS))


if __name__ == "__main__":
    unittest.main()
