from __future__ import annotations

import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from naukri_automation.config import ScheduleConfig

TASK_NAME = "NaukriResumeAutomation"
TASK_NAMESPACE = "http://schemas.microsoft.com/windows/2004/02/mit/task"
DAY_TAGS = {
    "MON": "Monday",
    "TUE": "Tuesday",
    "WED": "Wednesday",
    "THU": "Thursday",
    "FRI": "Friday",
    "SAT": "Saturday",
    "SUN": "Sunday",
}


class SchedulerError(RuntimeError):
    pass


def build_task_xml(
    schedule: ScheduleConfig,
    *,
    python_executable: Path,
    config_path: Path,
    now: datetime | None = None,
) -> str:
    now = now or datetime.now().astimezone()
    boundary = _next_boundary(schedule, now)
    ET.register_namespace("", TASK_NAMESPACE)

    task = ET.Element(_tag("Task"), {"version": "1.4"})
    registration = ET.SubElement(task, _tag("RegistrationInfo"))
    ET.SubElement(registration, _tag("Description")).text = (
        "Uploads the configured resume to Naukri using the current user's local browser profile."
    )

    triggers = ET.SubElement(task, _tag("Triggers"))
    trigger = ET.SubElement(triggers, _tag("CalendarTrigger"))
    ET.SubElement(trigger, _tag("StartBoundary")).text = boundary.isoformat(timespec="seconds")
    ET.SubElement(trigger, _tag("Enabled")).text = "true"
    if schedule.frequency == "daily":
        daily = ET.SubElement(trigger, _tag("ScheduleByDay"))
        ET.SubElement(daily, _tag("DaysInterval")).text = "1"
    else:
        weekly = ET.SubElement(trigger, _tag("ScheduleByWeek"))
        days = ET.SubElement(weekly, _tag("DaysOfWeek"))
        for day in schedule.days:
            ET.SubElement(days, _tag(DAY_TAGS[day]))
        ET.SubElement(weekly, _tag("WeeksInterval")).text = "1"

    principals = ET.SubElement(task, _tag("Principals"))
    principal = ET.SubElement(principals, _tag("Principal"), {"id": "CurrentUser"})
    ET.SubElement(principal, _tag("LogonType")).text = "InteractiveToken"
    ET.SubElement(principal, _tag("RunLevel")).text = "LeastPrivilege"

    settings = ET.SubElement(task, _tag("Settings"))
    ET.SubElement(settings, _tag("MultipleInstancesPolicy")).text = "IgnoreNew"
    ET.SubElement(settings, _tag("DisallowStartIfOnBatteries")).text = "false"
    ET.SubElement(settings, _tag("StopIfGoingOnBatteries")).text = "false"
    ET.SubElement(settings, _tag("StartWhenAvailable")).text = "true"
    ET.SubElement(settings, _tag("WakeToRun")).text = str(schedule.wake_computer).lower()
    ET.SubElement(settings, _tag("ExecutionTimeLimit")).text = "PT30M"

    actions = ET.SubElement(task, _tag("Actions"), {"Context": "CurrentUser"})
    command = ET.SubElement(actions, _tag("Exec"))
    ET.SubElement(command, _tag("Command")).text = str(python_executable.resolve())
    ET.SubElement(command, _tag("Arguments")).text = (
        f'-m naukri_automation --config "{config_path.resolve()}" run'
    )
    ET.SubElement(command, _tag("WorkingDirectory")).text = str(config_path.resolve().parent)

    ET.indent(task, space="  ")
    return ET.tostring(task, encoding="unicode", xml_declaration=True)


class WindowsScheduler:
    def __init__(self, *, task_name: str = TASK_NAME) -> None:
        if sys.platform != "win32":
            raise SchedulerError("Windows Task Scheduler commands are available only on Windows")
        self.task_name = task_name

    def install(self, task_xml: str, temporary_path: Path) -> str:
        temporary_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_text(task_xml, encoding="utf-8")
        try:
            return self._run("/Create", "/TN", self.task_name, "/XML", str(temporary_path), "/F")
        finally:
            temporary_path.unlink(missing_ok=True)

    def show(self) -> str:
        return self._run("/Query", "/TN", self.task_name, "/V", "/FO", "LIST")

    def run_now(self) -> str:
        return self._run("/Run", "/TN", self.task_name)

    def remove(self) -> str:
        return self._run("/Delete", "/TN", self.task_name, "/F")

    @staticmethod
    def _run(*arguments: str) -> str:
        try:
            completed = subprocess.run(
                ["schtasks.exe", *arguments],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise SchedulerError(f"Task Scheduler command failed: {error}") from error
        return completed.stdout.strip()


def _next_boundary(schedule: ScheduleConfig, now: datetime) -> datetime:
    hour, minute = (int(part) for part in schedule.time.split(":"))
    if schedule.frequency == "daily":
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return candidate if candidate > now else candidate + timedelta(days=1)

    requested = {list(DAY_TAGS).index(day) for day in schedule.days}
    for offset in range(8):
        candidate = (now + timedelta(days=offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate.weekday() in requested and candidate > now:
            return candidate
    raise SchedulerError("could not calculate the next weekly run")


def _tag(name: str) -> str:
    return f"{{{TASK_NAMESPACE}}}{name}"
