from __future__ import annotations

from typing import Any

from resume_automation.config import ConfigurationError
from resume_automation.providers.base import PortalProvider


def create_provider(name: str, page: Any, *, timeout_seconds: int) -> PortalProvider:
    if name == "naukri":
        from resume_automation.providers.naukri import NaukriProvider

        return NaukriProvider(page, timeout_seconds=timeout_seconds)
    raise ConfigurationError(f"unsupported provider: {name}")
