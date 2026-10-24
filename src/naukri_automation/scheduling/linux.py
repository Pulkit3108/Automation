from __future__ import annotations

import subprocess
from pathlib import Path

from naukri_automation.config import ScheduleConfig
from naukri_automation.scheduling.base import SchedulerError

WEEKDAYS = {
    "MON": "Mon",
    "TUE": "Tue",
    "WED": "Wed",
    "THU": "Thu",
    "FRI": "Fri",
    "SAT": "Sat",
    "SUN": "Sun",
}


class LinuxScheduler:
    def __init__(self, profile_name: str, *, home: Path | None = None) -> None:
        self.base_name = f"naukri-resume-automation-{profile_name}"
        self.unit_dir = (home or Path.home()) / ".config/systemd/user"
        self.service_path = self.unit_dir / f"{self.base_name}.service"
        self.timer_path = self.unit_dir / f"{self.base_name}.timer"

    def install_schedule(
        self,
        schedule: ScheduleConfig,
        *,
        python_executable: Path,
        working_directory: Path,
        data_directory: Path,
        profile_name: str,
    ) -> str:
        del data_directory
        self.unit_dir.mkdir(parents=True, exist_ok=True)
        service = "\n".join(
            [
                "[Unit]",
                f"Description=Naukri resume automation for profile {profile_name}",
                "",
                "[Service]",
                "Type=oneshot",
                f"WorkingDirectory={_quote(working_directory.resolve())}",
                (
                    f"ExecStart={_quote(python_executable.resolve())} "
                    f"-m naukri_automation run --profile {profile_name}"
                ),
                "",
            ]
        )
        calendar_lines = [f"OnCalendar={value}" for value in _calendar_expressions(schedule)]
        timer = "\n".join(
            [
                "[Unit]",
                f"Description=Naukri resume automation timer for profile {profile_name}",
                "",
                "[Timer]",
                *calendar_lines,
                "Persistent=true",
                "AccuracySec=1min",
                f"Unit={self.base_name}.service",
                "",
                "[Install]",
                "WantedBy=timers.target",
                "",
            ]
        )
        _atomic_write(self.service_path, service)
        _atomic_write(self.timer_path, timer)
        self._run("daemon-reload")
        self._run("enable", "--now", f"{self.base_name}.timer")
        return f"Installed systemd user timer {self.base_name}.timer"

    def show(self, *, verbose: bool = False) -> str:
        if verbose:
            return self._run("status", "--no-pager", f"{self.base_name}.timer")
        return "\n".join(
            [
                f"Job: {self.base_name}.timer",
                f"Status: {'enabled' if self.is_installed() else 'not enabled'}",
                f"Definition: {self.timer_path}",
            ]
        )

    def run_now(self) -> str:
        return self._run("start", f"{self.base_name}.service")

    def remove(self) -> str:
        self._run("disable", "--now", f"{self.base_name}.timer")
        self.service_path.unlink(missing_ok=True)
        self.timer_path.unlink(missing_ok=True)
        self._run("daemon-reload")
        return f"Removed systemd user timer {self.base_name}.timer"

    def is_installed(self) -> bool:
        completed = subprocess.run(
            ["systemctl", "--user", "is-enabled", f"{self.base_name}.timer"],
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
                ["systemctl", "--user", *arguments],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            detail = getattr(error, "stderr", "") or str(error)
            raise SchedulerError(f"systemd user command failed: {detail.strip()}") from error
        return completed.stdout.strip()


def _calendar_expressions(schedule: ScheduleConfig) -> list[str]:
    expressions: list[str] = []
    for rule in schedule.rules:
        prefix = ",".join(WEEKDAYS[day] for day in rule.days) if rule.days else "*-*-*"
        for value in rule.times:
            expression = (
                f"{prefix} *-*-* {value}:00" if rule.days else f"{prefix} {value}:00"
            )
            expressions.append(expression)
    return expressions


def _quote(value: Path) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
