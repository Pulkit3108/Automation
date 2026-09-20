from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from naukri_automation.config import NotificationConfig
from naukri_automation.notifications import send_notification
from naukri_automation.result import Outcome, RunResult


class NotificationTests(unittest.TestCase):
    def test_disabled_notification_does_not_open_network(self) -> None:
        result = RunResult.create(Outcome.SUCCESS, "ok")

        with patch("urllib.request.urlopen") as urlopen:
            delivered = send_notification(NotificationConfig(enabled=False), result)

        self.assertTrue(delivered)
        urlopen.assert_not_called()

    def test_enabled_notification_posts_sanitized_json(self) -> None:
        response = MagicMock()
        response.status = 200
        response.__enter__.return_value = response
        result = RunResult.create(Outcome.SUCCESS, "resume upload verified")
        config = NotificationConfig(
            enabled=True,
            base_url="https://notify.example.test",
            topic="status",
        )

        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            delivered = send_notification(config, result)

        self.assertTrue(delivered)
        request = urlopen.call_args.args[0]
        body = request.data.decode("utf-8")
        self.assertIn('"outcome": "SUCCESS"', body)
        self.assertNotIn("cookie", body.lower())


if __name__ == "__main__":
    unittest.main()
