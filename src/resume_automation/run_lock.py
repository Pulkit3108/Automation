from __future__ import annotations

import errno
import json
import os
import shutil
import socket
import sys
import time
from contextlib import AbstractContextManager, suppress
from pathlib import Path
from types import TracebackType
from typing import BinaryIO


class AlreadyRunningError(RuntimeError):
    pass


class RunLock(AbstractContextManager["RunLock"]):
    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: BinaryIO | None = None

    def __enter__(self) -> RunLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.is_dir():
            shutil.rmtree(self.path)

        handle = self.path.open("a+b")
        try:
            _ensure_lock_byte(handle)
            _lock_file(handle)
        except OSError as error:
            handle.close()
            if error.errno in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                raise AlreadyRunningError(f"another run owns {self.path}") from None
            raise

        try:
            metadata = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "created_epoch": time.time(),
            }
            handle.seek(0)
            handle.truncate()
            handle.write(json.dumps(metadata).encode("utf-8"))
            handle.flush()
        except Exception:
            _unlock_file(handle)
            handle.close()
            raise

        self._handle = handle
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._handle is None:
            return
        try:
            _unlock_file(self._handle)
        finally:
            self._handle.close()
            self._handle = None


def _ensure_lock_byte(handle: BinaryIO) -> None:
    handle.seek(0, 2)
    if handle.tell() == 0:
        handle.write(b"\0")
        handle.flush()
    handle.seek(0)


def _lock_file(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return

    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock_file(handle: BinaryIO) -> None:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt

        with suppress(OSError):
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return

    import fcntl

    with suppress(OSError):
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
