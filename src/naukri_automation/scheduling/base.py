from __future__ import annotations

from pathlib import Path
from typing import Protocol

from naukri_automation.config import ScheduleConfig


class SchedulerError(RuntimeError):
    pass


class NativeScheduler(Protocol):
    def install_schedule(
        self,
        schedule: ScheduleConfig,
        *,
        python_executable: Path,
        working_directory: Path,
        data_directory: Path,
        profile_name: str,
    ) -> str: ...

    def show(self, *, verbose: bool = False) -> str: ...

    def run_now(self) -> str: ...

    def remove(self) -> str: ...

    def is_installed(self) -> bool: ...
