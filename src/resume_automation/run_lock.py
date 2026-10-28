from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import time
from contextlib import AbstractContextManager
from pathlib import Path
from types import TracebackType


class AlreadyRunningError(RuntimeError):
    pass


class RunLock(AbstractContextManager["RunLock"]):
    def __init__(self, path: Path, *, stale_after_seconds: int = 3600) -> None:
        self.path = path
        self.stale_after_seconds = stale_after_seconds
        self._acquired = False

    def __enter__(self) -> RunLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.path.mkdir()
        except FileExistsError:
            if not self._remove_if_stale():
                raise AlreadyRunningError(f"another run owns {self.path}") from None
            self.path.mkdir()

        process_identity = _process_identity(os.getpid())
        if sys.platform == "win32" and process_identity is None:
            shutil.rmtree(self.path, ignore_errors=True)
            raise OSError("could not determine the Windows process identity")
        metadata = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_epoch": time.time(),
            "process_identity": process_identity,
        }
        (self.path / "owner.json").write_text(json.dumps(metadata), encoding="utf-8")
        self._acquired = True
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._acquired:
            shutil.rmtree(self.path, ignore_errors=True)
            self._acquired = False

    def _remove_if_stale(self) -> bool:
        metadata_path = self.path / "owner.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            age = time.time() - float(metadata["created_epoch"])
            same_host = metadata.get("hostname") == socket.gethostname()
            pid = int(metadata["pid"])
            expected_identity = metadata.get("process_identity")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            age = time.time() - self.path.stat().st_mtime
            same_host = False
            pid = -1
            expected_identity = None

        if same_host:
            current_identity = _process_identity(pid)
            if current_identity is not None and (
                (expected_identity is None and sys.platform != "win32")
                or current_identity == expected_identity
            ):
                return False
            shutil.rmtree(self.path)
            return True
        if age < self.stale_after_seconds:
            return False

        shutil.rmtree(self.path)
        return True


def _process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _process_identity(pid: int) -> str | None:
    if pid <= 0:
        return None
    if sys.platform == "win32":
        return _windows_process_identity(pid)
    return f"pid:{pid}" if _process_exists(pid) else None


def _windows_process_identity(pid: int) -> str | None:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
        ctypes.POINTER(wintypes.FILETIME),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel_time = wintypes.FILETIME()
        user_time = wintypes.FILETIME()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel_time),
            ctypes.byref(user_time),
        ):
            return None
        created_100ns = (creation.dwHighDateTime << 32) | creation.dwLowDateTime
        return f"windows:{pid}:{created_100ns}"
    finally:
        kernel32.CloseHandle(handle)
