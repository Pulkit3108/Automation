"""Operating-system schedule integrations."""
from __future__ import annotations

import sys

from resume_automation.scheduling.base import NativeScheduler, SchedulerError
from resume_automation.scheduling.windows import WindowsScheduler


def scheduler_for_profile(profile_name: str) -> NativeScheduler:
    if sys.platform == "win32":
        return WindowsScheduler(task_name=f"ResumeAutomation-{profile_name}")
    if sys.platform == "darwin":
        from resume_automation.scheduling.macos import MacOSScheduler

        return MacOSScheduler(profile_name)
    if sys.platform.startswith("linux"):
        from resume_automation.scheduling.linux import LinuxScheduler

        return LinuxScheduler(profile_name)
    raise SchedulerError(f"scheduling is not supported on platform: {sys.platform}")
