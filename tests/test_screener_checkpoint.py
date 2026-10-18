"""Resume completed batches across fresh runners without modifying production data."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import requests

from providers.screener import ScreenerDataError, ScreenerUnavailableError, ScreenerFundamentalsProvider
from scripts.refresh_screener_fundamentals import refresh
from services.screener_checkpoint import ScreenerCheckpointStore, checkpoint_identity
from services.snapshot_storage import SnapshotStorageError
from tests.test_cloud_snapshots import MemoryS3
from tests.test_screener_fundamentals import FakeProvider, InterruptingProvider


class DurableScreenerTests(unittest.TestCase):
    def store(self, client):
        return ScreenerCheckpointStore(client, "bucket", "markets/IN", "test-run")

    def test_fresh_runner_restores_only_complete_batches(self):
        client = MemoryS3()
        client.objects["markets/IN/current.json"] = b"unchanged"
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            with self.assertRaises(KeyboardInterrupt):
                refresh(symbols=["A.NS", "B.NS", "C.NS", "D.NS"], root=Path(first),
                        provider=InterruptingProvider("C.NS"), batch_size=2,
                        sleep_seconds=0, checkpoint_store=self.store(client))
            index = json.loads(client.objects[self.store(client).key])
            self.assertEqual(index["checkpoint"]["completed_symbols"], ["A.NS", "B.NS"])
            self.assertEqual(index["checkpoint"]["successful_symbol_count"], 2)
            provider = FakeProvider()
            manifest = refresh(symbols=["A.NS", "B.NS", "C.NS", "D.NS"], root=Path(second),
                               provider=provider, batch_size=2, sleep_seconds=0,
                               checkpoint_store=self.store(client))
            self.assertEqual(provider.fetched, ["C.NS", "D.NS"])
            self.assertEqual(manifest["successful_symbol_count"], 4)
        self.assertEqual(client.objects["markets/IN/current.json"], b"unchanged")

    def test_failed_upload_cannot_advance_durable_progress(self):
        client = MemoryS3()
        with TemporaryDirectory() as directory:
            staging = Path(directory)
            (staging / "checkpoint.json").write_text('{"completed_symbols": []}')
            store = self.store(client)
            store.save(staging)
            before = client.objects[store.key]
            (staging / "batches").mkdir()
            (staging / "batches/000001_summary.csv").write_text("symbol\nA.NS\n")
            (staging / "checkpoint.json").write_text('{"completed_symbols": ["A.NS"]}')
            client.fail_upload = True
            with self.assertRaises(SnapshotStorageError):
                store.save(staging)
            self.assertEqual(client.objects[store.key], before)

    def test_corrupt_remote_batch_is_rejected_before_local_checkpoint(self):
        client = MemoryS3()
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            with self.assertRaises(KeyboardInterrupt):
                refresh(symbols=["A.NS", "B.NS"], root=Path(first), batch_size=1,
                        provider=InterruptingProvider("B.NS"), sleep_seconds=0,
                        checkpoint_store=self.store(client))
            key = next(key for key in client.objects if "/objects/" in key)
            client.objects[key] = b"corrupted"
            with self.assertRaises(SnapshotStorageError):
                self.store(client).restore(Path(second))
            self.assertFalse((Path(second) / "checkpoint.json").exists())

    def test_competing_checkpoint_writer_is_rejected(self):
        client = MemoryS3()
        with TemporaryDirectory() as directory:
            staging = Path(directory)
            (staging / "checkpoint.json").write_text('{"completed_symbols": []}')
            self.store(client).save(staging)
            with self.assertRaises(SnapshotStorageError):
                self.store(client).save(staging)

    def test_identity_changes_for_universe_order_or_source_version(self):
        baseline = checkpoint_identity(["A.NS", "B.NS"], b"version-one")
        self.assertNotEqual(baseline, checkpoint_identity(["B.NS", "A.NS"], b"version-one"))
        self.assertNotEqual(baseline, checkpoint_identity(["A.NS", "B.NS"], b"version-two"))

    def test_same_local_runner_discards_batch_not_in_durable_index(self):
        client = MemoryS3()
        with TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(KeyboardInterrupt):
                refresh(symbols=["A.NS", "B.NS"], root=root, batch_size=1,
                        provider=InterruptingProvider("B.NS"), sleep_seconds=0,
                        checkpoint_store=self.store(client))
            orphan = root / ".staging/batches/000002_summary.csv"
            orphan.write_text("symbol\nOLD.NS\n")
            provider = FakeProvider()
            manifest = refresh(symbols=["A.NS", "B.NS"], root=root, batch_size=1,
                               provider=provider, sleep_seconds=0,
                               checkpoint_store=self.store(client))
            self.assertEqual(provider.fetched, ["B.NS"])
            self.assertEqual(manifest["successful_symbol_count"], 2)

    def test_provider_outage_does_not_turn_remaining_stocks_into_failures(self):
        client = MemoryS3()
        provider = FakeProvider()
        original = provider.fetch
        def fetch(symbol, refreshed_at):
            if symbol == "B.NS":
                raise ScreenerUnavailableError("Provider throttled")
            return original(symbol, refreshed_at)
        provider.fetch = fetch
        with TemporaryDirectory() as directory:
            with self.assertRaises(ScreenerUnavailableError):
                refresh(symbols=["A.NS", "B.NS", "C.NS"], root=Path(directory),
                        provider=provider, batch_size=1, sleep_seconds=0,
                        checkpoint_store=self.store(client))
            index = json.loads(client.objects[self.store(client).key])
            self.assertEqual(index["checkpoint"]["completed_symbols"], ["A.NS"])
            self.assertEqual(provider.fetched, ["A.NS"])

    def test_retry_failed_and_pending_preserves_successes_and_replaces_failure_audit(self):
        client = MemoryS3()
        symbols = ["A.NS", "B.NS", "C.NS", "D.NS"]
        with TemporaryDirectory() as first, TemporaryDirectory() as second:
            provider = InterruptingProvider("D.NS")
            provider.failed = {"B.NS"}
            with self.assertRaises(KeyboardInterrupt):
                refresh(symbols=symbols, root=Path(first), provider=provider,
                        batch_size=1, sleep_seconds=0, checkpoint_store=self.store(client))
            retry = FakeProvider(failed={"D.NS"})
            manifest = refresh(symbols=symbols, root=Path(second), provider=retry,
                               batch_size=1, sleep_seconds=0,
                               checkpoint_store=self.store(client), retry_failed=True)
            self.assertEqual(retry.fetched, ["B.NS", "D.NS"])
            self.assertEqual(manifest["successful_symbol_count"], 3)
            self.assertEqual(manifest["failed_symbol_count"], 1)
            import pandas as pd
            summary = pd.read_csv(Path(second) / manifest["summary_file"]["path"])
            failures = pd.read_csv(Path(second) / manifest["coverage_file"]["path"])
            self.assertEqual(set(summary["symbol"]), {"A.NS", "B.NS", "C.NS"})
            self.assertEqual(failures["symbol"].tolist(), ["D.NS"])
            index = json.loads(client.objects[self.store(client).key])["checkpoint"]
            self.assertEqual(index["successful_symbol_count"], 3)
            self.assertEqual(index["failed_symbol_count"], 1)

    def test_interrupted_retry_keeps_recovered_successes_on_next_runner(self):
        client = MemoryS3()
        symbols = ["A.NS", "B.NS", "C.NS"]
        with TemporaryDirectory() as first, TemporaryDirectory() as second, TemporaryDirectory() as third:
            provider = InterruptingProvider("C.NS")
            provider.failed = {"B.NS"}
            with self.assertRaises(KeyboardInterrupt):
                refresh(symbols=symbols, root=Path(first), provider=provider,
                        batch_size=1, sleep_seconds=0, checkpoint_store=self.store(client))
            with self.assertRaises(KeyboardInterrupt):
                refresh(symbols=symbols, root=Path(second), provider=InterruptingProvider("C.NS"),
                        batch_size=1, sleep_seconds=0, checkpoint_store=self.store(client), retry_failed=True)
            provider = FakeProvider()
            manifest = refresh(symbols=symbols, root=Path(third), provider=provider,
                               batch_size=1, sleep_seconds=0,
                               checkpoint_store=self.store(client), retry_failed=True)
            self.assertEqual(provider.fetched, ["C.NS"])
            self.assertEqual(manifest["successful_symbol_count"], 3)

    def test_exhausted_network_retries_stop_run_but_missing_company_is_auditable(self):
        session = Mock()
        session.get.side_effect = requests.Timeout("temporary")
        provider = ScreenerFundamentalsProvider(session=session, sleep=lambda _: None)
        with self.assertRaises(ScreenerUnavailableError):
            provider.fetch("A.NS", "2026-10-18")
        self.assertEqual(session.get.call_count, 3)
        response = Mock(status_code=404)
        session.reset_mock()
        session.get.side_effect = requests.HTTPError(response=response)
        with self.assertRaises(ScreenerDataError) as error:
            provider.fetch("MISSING.NS", "2026-10-18")
        self.assertNotIsInstance(error.exception, ScreenerUnavailableError)
        self.assertEqual(session.get.call_count, 1)
