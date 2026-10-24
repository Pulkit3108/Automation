"""Operating-system schedule integrations."""
from __future__ import annotations

import sys
from typing import Any

from naukri_automation.scheduling.windows import SchedulerError, WindowsScheduler


def scheduler_for_profile(profile_name: str) -> Any:
    if sys.platform == "win32":
        return WindowsScheduler(task_name=f"NaukriResumeAutomation-{profile_name}")
    if sys.platform == "darwin":
        from naukri_automation.scheduling.macos import MacOSScheduler

        return MacOSScheduler(profile_name)
    if sys.platform.startswith("linux"):
        from naukri_automation.scheduling.linux import LinuxScheduler

        return LinuxScheduler(profile_name)
    raise SchedulerError(f"scheduling is not supported on platform: {sys.platform}")
