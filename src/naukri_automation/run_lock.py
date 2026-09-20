from __future__ import annotations

import json
import os
import shutil
import socket
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

        metadata = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_epoch": time.time(),
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
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            age = time.time() - self.path.stat().st_mtime
            same_host = False
            pid = -1

        if same_host and _process_exists(pid):
            return False
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
