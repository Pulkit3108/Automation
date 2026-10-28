from __future__ import annotations

import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from resume_automation.run_lock import AlreadyRunningError, RunLock, _process_identity


class RunLockTests(unittest.TestCase):
    def test_windows_identity_does_not_use_posix_signal_probe(self) -> None:
        with (
            patch("resume_automation.run_lock.sys.platform", "win32"),
            patch(
                "resume_automation.run_lock._windows_process_identity",
                return_value="windows:13560:12345",
            ),
            patch("resume_automation.run_lock.os.kill") as kill,
        ):
            identity = _process_identity(13560)

        self.assertEqual("windows:13560:12345", identity)
        kill.assert_not_called()

    def test_second_live_lock_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"

            with (
                RunLock(lock_path),
                self.assertRaises(AlreadyRunningError),
                RunLock(lock_path),
            ):
                self.fail("second lock should not be acquired")

            self.assertFalse(lock_path.exists())

    def test_recent_dead_same_host_lock_is_reclaimed_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"
            lock_path.mkdir()
            (lock_path / "owner.json").write_text(
                json.dumps(
                    {
                        "pid": 424242,
                        "hostname": socket.gethostname(),
                        "created_epoch": time.time(),
                        "process_identity": "pid:424242",
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch("resume_automation.run_lock._process_identity", return_value=None),
                RunLock(lock_path),
            ):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())

    def test_reused_pid_does_not_own_old_lock(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"
            lock_path.mkdir()
            (lock_path / "owner.json").write_text(
                json.dumps(
                    {
                        "pid": 13560,
                        "hostname": socket.gethostname(),
                        "created_epoch": time.time(),
                        "process_identity": "windows:13560:old-start-time",
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch(
                    "resume_automation.run_lock._process_identity",
                    side_effect=["windows:13560:new-start-time", "windows:999:new-lock"],
                ),
                RunLock(lock_path),
            ):
                owner = json.loads((lock_path / "owner.json").read_text(encoding="utf-8"))
                self.assertEqual("windows:999:new-lock", owner["process_identity"])

            self.assertFalse(lock_path.exists())

    def test_legacy_windows_lock_cannot_be_claimed_by_reused_pid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            lock_path = Path(directory) / "run.lock"
            lock_path.mkdir()
            (lock_path / "owner.json").write_text(
                json.dumps(
                    {
                        "pid": 13560,
                        "hostname": socket.gethostname(),
                        "created_epoch": time.time(),
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch("resume_automation.run_lock.sys.platform", "win32"),
                patch(
                    "resume_automation.run_lock._process_identity",
                    side_effect=["windows:13560:new-start-time", "windows:999:new-lock"],
                ),
                RunLock(lock_path),
            ):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
