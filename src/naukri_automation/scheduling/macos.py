from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path

from naukri_automation.config import ScheduleConfig
from naukri_automation.scheduling.base import SchedulerError

WEEKDAYS = {"SUN": 1, "MON": 2, "TUE": 3, "WED": 4, "THU": 5, "FRI": 6, "SAT": 7}


class MacOSScheduler:
    def __init__(
        self,
        profile_name: str,
        *,
        home: Path | None = None,
        uid: int | None = None,
    ) -> None:
        self.label = f"com.naukri-resume-automation.{profile_name}"
        self.plist_path = (home or Path.home()) / "Library/LaunchAgents" / f"{self.label}.plist"
        self.domain = f"gui/{os.getuid() if uid is None else uid}"

    def install_schedule(
        self,
        schedule: ScheduleConfig,
        *,
        python_executable: Path,
        working_directory: Path,
        data_directory: Path,
        profile_name: str,
    ) -> str:
        logs = data_directory / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        payload = {
            "Label": self.label,
            "ProgramArguments": [
                str(python_executable.resolve()),
                "-m",
                "naukri_automation",
                "run",
                "--profile",
                profile_name,
            ],
            "WorkingDirectory": str(working_directory.resolve()),
            "StartCalendarInterval": _calendar_intervals(schedule),
            "StandardOutPath": str(logs / "scheduler.stdout.log"),
            "StandardErrorPath": str(logs / "scheduler.stderr.log"),
            "ProcessType": "Background",
        }
        self.plist_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.plist_path.with_suffix(".tmp")
        temporary.write_bytes(plistlib.dumps(payload, sort_keys=False))
        temporary.replace(self.plist_path)
        subprocess.run(
            ["launchctl", "bootout", f"{self.domain}/{self.label}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self._run("bootstrap", self.domain, str(self.plist_path))
        return f"Installed launchd agent {self.label}"

    def show(self, *, verbose: bool = False) -> str:
        if verbose:
            return self._run("print", f"{self.domain}/{self.label}")
        return "\n".join(
            [
                f"Job: {self.label}",
                f"Status: {'loaded' if self.is_installed() else 'not loaded'}",
                f"Definition: {self.plist_path}",
            ]
        )

    def run_now(self) -> str:
        return self._run("kickstart", "-k", f"{self.domain}/{self.label}")

    def remove(self) -> str:
        output = self._run("bootout", f"{self.domain}/{self.label}")
        self.plist_path.unlink(missing_ok=True)
        return output or f"Removed launchd agent {self.label}"

    def is_installed(self) -> bool:
        completed = subprocess.run(
            ["launchctl", "print", f"{self.domain}/{self.label}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return completed.returncode == 0

    @staticmethod
    def _run(*arguments: str) -> str:
        try:
            completed = subprocess.run(
                ["launchctl", *arguments],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            detail = getattr(error, "stderr", "") or str(error)
            raise SchedulerError(f"launchd command failed: {detail.strip()}") from error
        return completed.stdout.strip()


def _calendar_intervals(schedule: ScheduleConfig) -> list[dict[str, int]]:
    intervals: list[dict[str, int]] = []
    for rule in schedule.rules:
        for value in rule.times:
            hour, minute = (int(part) for part in value.split(":"))
            if rule.days:
                intervals.extend(
                    {"Weekday": WEEKDAYS[day], "Hour": hour, "Minute": minute}
                    for day in rule.days
                )
            else:
                intervals.append({"Hour": hour, "Minute": minute})
    return intervals
