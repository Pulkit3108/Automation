from __future__ import annotations

import asyncio
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from resume_automation.browser_session import (
    BrowserSession,
    _remove_windows_taskbar_button,
    _start_playwright,
)


class BrowserSessionTests(unittest.TestCase):
    def test_desktop_launch_uses_browser_sandbox(self) -> None:
        session = BrowserSession(
            Path("/tmp/profile"),
            browser_channel="chrome",
            browser_mode="headless",
            timeout_seconds=10,
        )

        with patch("resume_automation.browser_session.sys.platform", "win32"):
            options = session._launch_options()

        self.assertIs(options["chromium_sandbox"], True)

    def test_linux_keeps_playwright_default_arguments(self) -> None:
        session = BrowserSession(
            Path("/tmp/profile"),
            browser_channel="chrome",
            browser_mode="headless",
            timeout_seconds=10,
        )

        with patch("resume_automation.browser_session.sys.platform", "linux"):
            options = session._launch_options()

        self.assertNotIn("chromium_sandbox", options)

    def test_cleanup_tolerates_browser_already_closed(self) -> None:
        session = BrowserSession(
            Path("/tmp/profile"),
            browser_channel="chrome",
            browser_mode="headless",
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

    def test_background_mode_uses_headed_offscreen_window(self) -> None:
        session = BrowserSession(
            Path("/tmp/profile"),
            browser_channel="chrome",
            browser_mode="background",
            timeout_seconds=10,
        )

        options = session._launch_options()

        self.assertIs(options["headless"], False)
        self.assertIn("--window-position=-32000,-32000", options["args"])

    def test_windows_background_window_is_removed_from_taskbar(self) -> None:
        show_window = MagicMock()
        set_window_long = MagicMock()
        win32con = SimpleNamespace(
            GWL_EXSTYLE=-20,
            SW_HIDE=0,
            SW_SHOWNOACTIVATE=4,
            WS_EX_APPWINDOW=0x40000,
            WS_EX_TOOLWINDOW=0x80,
        )
        win32gui = SimpleNamespace(
            EnumWindows=lambda callback, argument: callback(42, argument),
            GetWindowText=lambda handle: "Resume Automation Background - Google Chrome",
            GetWindowLong=lambda handle, index: 0x40000,
            SetWindowLong=set_window_long,
            ShowWindow=show_window,
        )

        with patch.dict(
            "sys.modules",
            {"win32con": win32con, "win32gui": win32gui},
        ):
            _remove_windows_taskbar_button("Resume Automation Background")

        self.assertEqual(
            [(42, 0), (42, 4)],
            [call.args for call in show_window.call_args_list],
        )
        set_window_long.assert_called_once_with(42, -20, 0x80)

    def test_windows_background_driver_is_started_without_console(self) -> None:
        factory = MagicMock()

        def start() -> object:
            return asyncio.run(asyncio.create_subprocess_exec("node", creationflags=4))

        factory.return_value.start.side_effect = start
        with patch(
            "resume_automation.browser_session.asyncio.create_subprocess_exec",
            new_callable=AsyncMock,
            return_value="driver",
        ) as create_subprocess:
            result = _start_playwright(factory, hide_driver_console=True)

        self.assertEqual("driver", result)
        create_subprocess.assert_awaited_once_with(
            "node",
            creationflags=4 | 0x08000000,
        )


if __name__ == "__main__":
    unittest.main()
