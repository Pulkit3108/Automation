from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from resume_automation.run_lock import (
    AlreadyRunningError,
    RunLock,
    _ensure_lock_byte,
    _lock_file,
    _unlock_file,
)


class RunLockTests(unittest.TestCase):
    def test_windows_uses_nonblocking_crt_file_lock(self) -> None:
        locking = Mock()
        fake_msvcrt = SimpleNamespace(LK_NBLCK=1, LK_UNLCK=2, locking=locking)
        with tempfile.TemporaryFile("w+b") as handle:
            file_descriptor = handle.fileno()
            _ensure_lock_byte(handle)
            with (
                patch("resume_automation.run_lock.sys.platform", "win32"),
                patch.dict(sys.modules, {"msvcrt": fake_msvcrt}),
            ):
                _lock_file(handle)
                _unlock_file(handle)

        self.assertEqual(
            [(file_descriptor, 1, 1), (file_descriptor, 2, 1)],
            [call.args for call in locking.call_args_list],
        )

    def test_second_live_lock_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"

            with (
                RunLock(lock_path),
                self.assertRaises(AlreadyRunningError),
                RunLock(lock_path),
            ):
                self.fail("second lock should not be acquired")

            self.assertTrue(lock_path.is_file())

    def test_lock_is_released_after_context_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"

            with RunLock(lock_path):
                first_owner = json.loads(lock_path.read_text(encoding="utf-8"))

            with RunLock(lock_path):
                second_owner = json.loads(lock_path.read_text(encoding="utf-8"))

            self.assertEqual(first_owner["pid"], second_owner["pid"])

    def test_lock_is_released_when_work_raises(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"

            with self.assertRaisesRegex(RuntimeError, "failed"), RunLock(lock_path):
                raise RuntimeError("failed")

            with RunLock(lock_path):
                self.assertTrue(lock_path.is_file())

    def test_legacy_lock_directory_is_migrated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"
            lock_path.mkdir()
            (lock_path / "owner.json").write_text('{"pid": 13560}', encoding="utf-8")

            with RunLock(lock_path):
                self.assertTrue(lock_path.is_file())


if __name__ == "__main__":
    unittest.main()
