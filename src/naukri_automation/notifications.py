from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from naukri_automation import __version__
from naukri_automation.config import NotificationConfig
from naukri_automation.result import RunResult

LOGGER = logging.getLogger(__name__)


def send_notification(config: NotificationConfig, result: RunResult) -> bool:
    if not config.enabled:
        return True

    url = f"{config.base_url.rstrip('/')}/{urllib.parse.quote(config.topic, safe='')}"
    payload = {
        "outcome": result.outcome.value,
        "message": result.message,
        "timestamp_utc": result.timestamp_utc,
        "version": __version__,
    }
    request = urllib.request.Request(
        url,
        data=(json.dumps(payload) + "\n").encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": f"naukri-resume-automation/{__version__}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        LOGGER.warning("notification delivery failed: %s", type(error).__name__)
        return False
