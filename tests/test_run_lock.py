from __future__ import annotations

import json
import socket
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from naukri_automation.run_lock import AlreadyRunningError, RunLock


class RunLockTests(unittest.TestCase):
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
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch("naukri_automation.run_lock._process_exists", return_value=False),
                RunLock(lock_path),
            ):
                self.assertTrue(lock_path.exists())

            self.assertFalse(lock_path.exists())


if __name__ == "__main__":
    unittest.main()
