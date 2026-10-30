from __future__ import annotations

import asyncio
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from types import TracebackType
from typing import Any


class BrowserDependencyError(RuntimeError):
    pass


BACKGROUND_WINDOW_TITLE = "Resume Automation Background"


class BrowserSession:
    def __init__(
        self,
        profile_dir: Path,
        *,
        browser_channel: str,
        browser_mode: str,
        timeout_seconds: int,
    ) -> None:
        self.profile_dir = profile_dir
        self.browser_channel = browser_channel
        self.browser_mode = browser_mode
        self.timeout_ms = timeout_seconds * 1000
        self._playwright: Any = None
        self.context: Any = None
        self.page: Any = None
        self._tracing = False

    def __enter__(self) -> BrowserSession:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as error:
            raise BrowserDependencyError(
                "Playwright is not installed; install the project dependencies"
            ) from error

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = _start_playwright(
            sync_playwright,
            hide_driver_console=self.browser_mode == "background" and sys.platform == "win32",
        )
        try:
            launch_options = self._launch_options()
            self.context = self._playwright.chromium.launch_persistent_context(
                **launch_options,
            )
        except Exception as error:
            self._playwright.stop()
            self._playwright = None
            install_hint = (
                "run 'playwright install chromium'"
                if self.browser_channel == "chromium"
                else f"install the {self.browser_channel} browser"
            )
            raise BrowserDependencyError(
                f"could not launch browser channel '{self.browser_channel}'; {install_hint}"
            ) from error

        self.context.set_default_timeout(self.timeout_ms)
        self.context.set_default_navigation_timeout(self.timeout_ms)
        self.context.tracing.start(screenshots=True, snapshots=True, sources=False)
        self._tracing = True
        try:
            self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
            if self.browser_mode == "background" and sys.platform == "win32":
                self.page.set_content(f"<title>{BACKGROUND_WINDOW_TITLE}</title>")
                _remove_windows_taskbar_button(BACKGROUND_WINDOW_TITLE)
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def _launch_options(self) -> dict[str, Any]:
        options: dict[str, Any] = {
            "user_data_dir": self.profile_dir,
            "headless": self.browser_mode == "headless",
            "accept_downloads": False,
        }
        if self.browser_mode == "background":
            options["headless"] = False
            options["args"] = [
                "--window-position=-32000,-32000",
                "--window-size=1280,900",
            ]
        if self.browser_channel != "chromium":
            options["channel"] = self.browser_channel
        if sys.platform in {"win32", "darwin"}:
            options["chromium_sandbox"] = True
        return options

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._tracing:
            with suppress(Exception):
                self.context.tracing.stop()
            self._tracing = False
        if self.context is not None:
            with suppress(Exception):
                self.context.close()
        if self._playwright is not None:
            with suppress(Exception):
                self._playwright.stop()

    def capture_failure(self, artifact_dir: Path) -> None:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        if self.page is not None:
            with suppress(Exception):
                self.page.screenshot(path=artifact_dir / "failure.png", full_page=True)
        if self._tracing:
            try:
                self.context.tracing.stop(path=artifact_dir / "trace.zip")
            except Exception:
                pass
            finally:
                self._tracing = False


def _remove_windows_taskbar_button(title: str) -> None:
    try:
        import win32con
        import win32gui
    except ImportError as error:
        raise BrowserDependencyError(
            "Windows background mode requires the pywin32 package"
        ) from error

    def collect_matching_window(handle: int, state: tuple[str, list[int]]) -> bool:
        expected_title, matching_handles = state
        with suppress(Exception):
            if win32gui.GetWindowText(handle).startswith(expected_title):
                matching_handles.append(handle)
        return True

    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        matches: list[int] = []
        win32gui.EnumWindows(collect_matching_window, (title, matches))
        if matches:
            for handle in matches:
                win32gui.ShowWindow(handle, win32con.SW_HIDE)
                style = win32gui.GetWindowLong(handle, win32con.GWL_EXSTYLE)
                style = (style & ~win32con.WS_EX_APPWINDOW) | win32con.WS_EX_TOOLWINDOW
                win32gui.SetWindowLong(handle, win32con.GWL_EXSTYLE, style)
                win32gui.ShowWindow(handle, win32con.SW_SHOWNOACTIVATE)
            return
        time.sleep(0.05)

    raise BrowserDependencyError("could not remove the background browser taskbar button")


def _start_playwright(factory: Any, *, hide_driver_console: bool) -> Any:
    if not hide_driver_console:
        return factory().start()

    original_create_subprocess_exec = asyncio.create_subprocess_exec
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

    async def create_hidden_subprocess(*args: Any, **kwargs: Any) -> Any:
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | create_no_window
        return await original_create_subprocess_exec(*args, **kwargs)

    asyncio.create_subprocess_exec = create_hidden_subprocess
    try:
        return factory().start()
    finally:
        asyncio.create_subprocess_exec = original_create_subprocess_exec
