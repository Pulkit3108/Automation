from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
