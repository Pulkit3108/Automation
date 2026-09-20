from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import MagicMock

from naukri_automation.browser_session import BrowserSession


class BrowserSessionTests(unittest.TestCase):
    def test_cleanup_tolerates_browser_already_closed(self) -> None:
        session = BrowserSession(
            Path("/tmp/profile"),
            browser_channel="chrome",
            headless=True,
            timeout_seconds=10,
        )
        session.context = MagicMock()
        session.context.tracing.stop.side_effect = RuntimeError("closed")
        session.context.close.side_effect = RuntimeError("closed")
        session._playwright = MagicMock()
        session._playwright.stop.side_effect = RuntimeError("closed")
        session._tracing = True

        session.__exit__(None, None, None)

        self.assertFalse(session._tracing)


if __name__ == "__main__":
    unittest.main()
