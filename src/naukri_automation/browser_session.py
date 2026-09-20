from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from types import TracebackType
from typing import Any


class BrowserDependencyError(RuntimeError):
    pass


class BrowserSession:
    def __init__(
        self,
        profile_dir: Path,
        *,
        headless: bool,
        timeout_seconds: int,
    ) -> None:
        self.profile_dir = profile_dir
        self.headless = headless
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
                "Playwright is not installed; install the package and run "
                "'playwright install chromium'"
            ) from error

        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        try:
            self.context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=self.profile_dir,
                headless=self.headless,
                accept_downloads=False,
            )
        except Exception:
            self._playwright.stop()
            self._playwright = None
            raise

        self.context.set_default_timeout(self.timeout_ms)
        self.context.set_default_navigation_timeout(self.timeout_ms)
        self.context.tracing.start(screenshots=True, snapshots=True, sources=False)
        self._tracing = True
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            if self._tracing:
                self.context.tracing.stop()
                self._tracing = False
        finally:
            if self.context is not None:
                self.context.close()
            if self._playwright is not None:
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
