from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from naukri_automation.config import (
    AppConfig,
    ConfigurationError,
    NotificationConfig,
    ScheduleConfig,
    load_config,
    write_config,
)


class ConfigTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            resume = root / "resume.pdf"
            resume.write_bytes(b"%PDF-test")
            path = root / "config.toml"
            expected = AppConfig(
                resume_path=resume,
                headless=False,
                notification=NotificationConfig(
                    enabled=True,
                    base_url="https://notify.example.test",
                    topic="resume_status",
                ),
                schedule=ScheduleConfig(
                    frequency="weekly",
                    time="08:15",
                    days=("MON", "FRI"),
                ),
            )

            write_config(expected, path)

            self.assertEqual(expected, load_config(path))

    def test_relative_resume_is_rejected(self) -> None:
        config = AppConfig(resume_path=Path("resume.pdf"))

        with self.assertRaisesRegex(ConfigurationError, "must be absolute"):
            config.validate(require_resume=False)

    def test_insecure_notification_url_is_rejected(self) -> None:
        config = AppConfig(
            resume_path=Path("/tmp/resume.pdf"),
            notification=NotificationConfig(
                enabled=True,
                base_url="http://notify.example.test",
                topic="status",
            ),
        )

        with self.assertRaisesRegex(ConfigurationError, "must use https"):
            config.validate(require_resume=False)

    def test_weekly_schedule_requires_days(self) -> None:
        config = AppConfig(
            resume_path=Path("/tmp/resume.pdf"),
            schedule=ScheduleConfig(frequency="weekly", time="09:00"),
        )

        with self.assertRaisesRegex(ConfigurationError, "requires at least one day"):
            config.validate(require_resume=False)


if __name__ == "__main__":
    unittest.main()
