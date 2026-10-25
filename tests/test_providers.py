from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from resume_automation.config import ConfigurationError
from resume_automation.providers import create_provider
from resume_automation.providers.naukri import NaukriProvider


class ProviderRegistryTests(unittest.TestCase):
    def test_naukri_provider_is_created_from_registry(self) -> None:
        provider = create_provider("naukri", MagicMock(), timeout_seconds=10)

        self.assertIsInstance(provider, NaukriProvider)

    def test_unknown_provider_is_rejected(self) -> None:
        with self.assertRaisesRegex(ConfigurationError, "unsupported provider"):
            create_provider("unknown", MagicMock(), timeout_seconds=10)


if __name__ == "__main__":
    unittest.main()
