from __future__ import annotations

import csv
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

from resume_automation.config import ScheduleConfig, ScheduleRule
from resume_automation.scheduling.base import SchedulerError

TASK_NAME = "ResumeAutomation"
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


def build_task_xml(
    schedule: ScheduleConfig,
    *,
    python_executable: Path,
    user_id: str,
    config_path: Path | None = None,
    profile_name: str | None = None,
    working_directory: Path | None = None,
    now: datetime | None = None,
) -> bytes:
    if (config_path is None) == (profile_name is None):
        raise SchedulerError("provide exactly one of config_path or profile_name")
    if not user_id.strip():
        raise SchedulerError("Windows task user identifier is required")
    now = now or datetime.now().astimezone()
    ET.register_namespace("", TASK_NAMESPACE)

    task = ET.Element(_tag("Task"), {"version": "1.4"})
    registration = ET.SubElement(task, _tag("RegistrationInfo"))
    ET.SubElement(registration, _tag("Description")).text = (
        "Uploads the configured resume using the current user's local portal browser profile."
    )

    triggers = ET.SubElement(task, _tag("Triggers"))
    for rule in schedule.rules:
        for run_time in rule.times:
            boundary = _next_boundary(rule, run_time, now)
            trigger = ET.SubElement(triggers, _tag("CalendarTrigger"))
            ET.SubElement(trigger, _tag("Enabled")).text = "true"
            ET.SubElement(trigger, _tag("StartBoundary")).text = boundary.isoformat(
                timespec="seconds"
            )
            if not rule.days:
                daily = ET.SubElement(trigger, _tag("ScheduleByDay"))
                ET.SubElement(daily, _tag("DaysInterval")).text = "1"
            else:
                weekly = ET.SubElement(trigger, _tag("ScheduleByWeek"))
                days = ET.SubElement(weekly, _tag("DaysOfWeek"))
                for day in rule.days:
                    ET.SubElement(days, _tag(DAY_TAGS[day]))
                ET.SubElement(weekly, _tag("WeeksInterval")).text = "1"

    principals = ET.SubElement(task, _tag("Principals"))
    principal = ET.SubElement(principals, _tag("Principal"), {"id": "CurrentUser"})
    ET.SubElement(principal, _tag("UserId")).text = user_id
    ET.SubElement(principal, _tag("LogonType")).text = "InteractiveToken"
    ET.SubElement(principal, _tag("RunLevel")).text = "LeastPrivilege"

    settings = ET.SubElement(task, _tag("Settings"))
    ET.SubElement(settings, _tag("MultipleInstancesPolicy")).text = "IgnoreNew"
    ET.SubElement(settings, _tag("DisallowStartIfOnBatteries")).text = "false"
    ET.SubElement(settings, _tag("StopIfGoingOnBatteries")).text = "false"
    ET.SubElement(settings, _tag("StartWhenAvailable")).text = "false"
    ET.SubElement(settings, _tag("WakeToRun")).text = str(schedule.wake_computer).lower()
    ET.SubElement(settings, _tag("ExecutionTimeLimit")).text = "PT30M"

    actions = ET.SubElement(task, _tag("Actions"), {"Context": "CurrentUser"})
    command = ET.SubElement(actions, _tag("Exec"))
    scheduled_python = _windowed_python_executable(python_executable)
    ET.SubElement(command, _tag("Command")).text = str(scheduled_python.resolve())
    arguments = "-m resume_automation"
    if profile_name is not None:
        arguments += f' run --profile "{profile_name}"'
    else:
        arguments += f' --config "{config_path.resolve()}" run'
    ET.SubElement(command, _tag("Arguments")).text = arguments
    directory = working_directory or config_path.resolve().parent
    ET.SubElement(command, _tag("WorkingDirectory")).text = str(directory.resolve())

    ET.indent(task, space="  ")
    return ET.tostring(task, encoding="utf-16", xml_declaration=True)


class WindowsScheduler:
    def __init__(self, *, task_name: str = TASK_NAME) -> None:
        if sys.platform != "win32":
            raise SchedulerError("Windows Task Scheduler commands are available only on Windows")
        self.task_name = task_name

    def install(self, task_xml: bytes, temporary_path: Path) -> str:
        temporary_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path.write_bytes(task_xml)
        try:
            return self._run("/Create", "/TN", self.task_name, "/XML", str(temporary_path), "/F")
        finally:
            temporary_path.unlink(missing_ok=True)

    def install_schedule(
        self,
        schedule: ScheduleConfig,
        *,
        python_executable: Path,
        working_directory: Path,
        data_directory: Path,
        profile_name: str,
    ) -> str:
        task_xml = build_task_xml(
            schedule,
            python_executable=python_executable,
            user_id=self.current_user_id(),
            profile_name=profile_name,
            working_directory=working_directory,
        )
        return self.install(task_xml, data_directory / "task.xml")

    def show(self, *, verbose: bool = False) -> str:
        if verbose:
            return self._run("/Query", "/TN", self.task_name, "/V", "/FO", "LIST")
        output = self._run("/Query", "/TN", self.task_name, "/FO", "CSV", "/NH")
        try:
            task_name, next_run, status, *_ = next(csv.reader(output.splitlines()))
        except (StopIteration, ValueError) as error:
            raise SchedulerError("Task Scheduler returned an unreadable summary") from error
        return "\n".join(
            [
                f"Task: {task_name}",
                f"Status: {status}",
                f"Next run: {next_run}",
            ]
        )

    def run_now(self) -> str:
        return self._run("/Run", "/TN", self.task_name)

    def remove(self) -> str:
        return self._run("/Delete", "/TN", self.task_name, "/F")

    def is_installed(self) -> bool:
        completed = subprocess.run(
            ["schtasks.exe", "/Query", "/TN", self.task_name],
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return completed.returncode == 0

    @staticmethod
    def current_user_id() -> str:
        try:
            completed = subprocess.run(
                ["whoami.exe"],
                check=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise SchedulerError(
                f"could not resolve the current Windows user: {_command_error_detail(error)}"
            ) from error
        user_id = completed.stdout.strip()
        if not user_id:
            raise SchedulerError("could not resolve the current Windows user: empty result")
        return user_id

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
            raise SchedulerError(
                f"Task Scheduler command failed: {_command_error_detail(error)}"
            ) from error
        return completed.stdout.strip()


def _command_error_detail(error: BaseException) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        output = (error.stderr or error.stdout or "").strip()
        if output:
            return output
    return str(error)


def _windowed_python_executable(python_executable: Path) -> Path:
    if python_executable.name.casefold() != "python.exe":
        return python_executable
    candidate = python_executable.with_name("pythonw.exe")
    return candidate if candidate.is_file() else python_executable


def _next_boundary(rule: ScheduleRule, run_time: str, now: datetime) -> datetime:
    hour, minute = (int(part) for part in run_time.split(":"))
    if not rule.days:
        candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return candidate if candidate > now else candidate + timedelta(days=1)

    requested = {list(DAY_TAGS).index(day) for day in rule.days}
    for offset in range(8):
        candidate = (now + timedelta(days=offset)).replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate.weekday() in requested and candidate > now:
            return candidate
    raise SchedulerError("could not calculate the next weekly run")


def _tag(name: str) -> str:
    return f"{{{TASK_NAMESPACE}}}{name}"
