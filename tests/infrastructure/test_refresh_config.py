"""CI credentials are explicit and never fall back to local Secrets."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from stock_analyser.infrastructure.r2.refresh_config import load_refresh_configuration
from stock_analyser.infrastructure.r2.storage import SnapshotStorageError


class RefreshConfigurationTests(unittest.TestCase):
    def test_ci_configuration_uses_publisher_for_reads_and_writes(self):
        settings = {"endpoint_url": "https://example.test", "bucket": "bucket",
                    "access_key_id": "test-id", "secret_access_key": "test-secret",
                    "snapshot_ids": {"IN": "stale"}}
        reader, writer = load_refresh_configuration(Path("unused"), "github",
                            {"R2_PUBLISHER_CONFIG": json.dumps(settings)})
        self.assertEqual(reader, writer)
        self.assertIsNot(reader, writer)
        self.assertNotIn("snapshot_ids", reader)
        self.assertEqual(writer["prefix"], "")
        self.assertEqual(writer["region"], "auto")

    def test_invalid_secret_fails_without_opening_local_files_or_leaking_input(self):
        for payload in ["", "private-invalid-json", "[]", "null",
                        '{"secret_access_key":"private-invalid-value"}']:
            with self.subTest(payload=payload), patch.object(Path, "open") as opened:
                with self.assertRaises(SnapshotStorageError) as error:
                    load_refresh_configuration(Path("unused"), "github",
                                               {"R2_PUBLISHER_CONFIG": payload})
                self.assertNotIn("private-invalid", str(error.exception))
                opened.assert_not_called()
