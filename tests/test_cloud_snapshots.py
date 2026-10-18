"""Cloud storage contracts, publication safety, and market isolation."""

import hashlib
import io
import json
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from models.market import market_data_root, market_definition, stock_key
from models.scan_config import ScanConfig
from services.backtest_service import BacktestService
from services.data_source import SNAPSHOT_SOURCE, build_data_services
from services.scan_service import ScanService
from services.snapshot_publication import SnapshotPublisher, json_bytes, prepare_snapshot, retire_legacy_snapshot
from services.storage_config import market_storage_prefix
from scripts.refresh_cloud_market_data import stage_source_snapshot, run_daily_refresh
from services.snapshot_storage import (
    CloudSnapshotStorage, LocalSnapshotStorage, ScopedSnapshotStorage,
    SnapshotStorageError, safe_relative_path,
)
from services.stock_universe import StockUniverse


class FakeClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class MemoryS3:
    """Exercise conditional writes against a deterministic in-memory bucket."""

    def __init__(self):
        self.objects = {}
        self.metadata = {}
        self.reads = []
        self.fail_upload = False

    def get_object(self, Bucket, Key):
        self.reads.append(Key)
        if Key not in self.objects:
            raise FakeClientError("NoSuchKey")
        body = self.objects[Key]
        return {"Body": io.BytesIO(body), "ETag": hashlib.md5(body).hexdigest()}

    def head_object(self, Bucket, Key):
        if Key not in self.objects:
            raise FakeClientError("404")
        return {"ContentLength": len(self.objects[Key]), "Metadata": self.metadata[Key], "ETag": hashlib.md5(self.objects[Key]).hexdigest()}

    def put_object(self, Bucket, Key, Body, IfNoneMatch=None, IfMatch=None, **kwargs):
        if self.fail_upload and "/snapshots/" not in Key and not Key.endswith("current.json"):
            raise FakeClientError("AccessDenied")
        current = self.objects.get(Key)
        if IfNoneMatch == "*" and current is not None:
            raise FakeClientError("PreconditionFailed")
        if IfMatch and (current is None or hashlib.md5(current).hexdigest() != IfMatch):
            raise FakeClientError("PreconditionFailed")
        self.objects[Key] = Body
        self.metadata[Key] = kwargs.get("Metadata", {})

    def copy_object(self, Bucket, Key, CopySource, CopySourceIfMatch, **kwargs):
        source = CopySource["Key"]
        if hashlib.md5(self.objects[source]).hexdigest() != CopySourceIfMatch:
            raise FakeClientError("PreconditionFailed")
        self.objects[Key] = self.objects[source]
        self.metadata[Key] = self.metadata[source].copy()

    def list_objects_v2(self, Bucket, Prefix, **kwargs):
        return {"Contents": [{"Key": key} for key in self.objects if key.startswith(Prefix)], "IsTruncated": False}

    def delete_objects(self, Bucket, Delete):
        for entry in Delete["Objects"]:
            self.objects.pop(entry["Key"], None)
            self.metadata.pop(entry["Key"], None)
        return {}


from tests.snapshot_fixtures import create_fixture, write_json


class CloudSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        create_fixture(self.root)
        self.prepared = self.root / "prepared"
        self.snapshot_id, self.catalog = prepare_snapshot(self.root, self.prepared)
        self.client = MemoryS3()
        self.publisher = SnapshotPublisher(self.client, "bucket")
        self.publisher.publish(self.prepared, self.snapshot_id)
        self.client.reads.clear()

    def storage(self, snapshot_id="", market="IN"):
        return CloudSnapshotStorage(self.client, "bucket", "markets/IN", self.root / "cache", snapshot_id, market)

    def test_provider_values_match_local_and_single_stock_reads_are_selective(self):
        cloud = self.storage()
        local = build_data_services(SNAPSHOT_SOURCE, self.root, LocalSnapshotStorage(self.root))
        remote = build_data_services(SNAPSHOT_SOURCE, self.root, cloud)
        for adjusted in (False, True):
            pd.testing.assert_frame_equal(local.history.download_batch(["TEST.NS"], adjusted_prices=adjusted), remote.history.download_batch(["TEST.NS"], adjusted_prices=adjusted))
        self.assertEqual(local.fundamentals.get_fundamentals("TEST.NS"), remote.fundamentals.get_fundamentals("TEST.NS"))
        self.assertEqual(local.industry_valuation.valuation_for("Tech"), remote.industry_valuation.valuation_for("Tech"))
        pd.testing.assert_frame_equal(local.screener.valuation_history("TEST.NS"), remote.screener.valuation_history("TEST.NS"))
        self.assertEqual(local.screener.fundamental_metrics("TEST.NS"), remote.screener.fundamental_metrics("TEST.NS"))
        downloaded = set(self.client.reads)
        bulk_key = self.catalog["files"]["market_data/prices.parquet"]["key"]
        self.assertNotIn(f"markets/IN/{bulk_key}", downloaded)
        self.assertEqual(remote.metadata["snapshot_id"], self.snapshot_id)

    def test_universe_uses_the_same_pinned_catalog(self):
        storage = self.storage()
        universe = StockUniverse(self.root, ScopedSnapshotStorage(storage, "data/stock_universe"))
        self.assertEqual(pd.read_csv(universe.active_file())["Symbol"].tolist(), ["TEST.NS", "OTHER.NS"])
        self.client.objects["markets/IN/current.json"] = b"invalid changed pointer"
        self.assertEqual(universe.metadata()["market"], "IN")
        self.assertTrue(storage.path("data/market_data/manifest.json").is_file())

    def test_cache_reuse_and_corruption_repair(self):
        storage = self.storage()
        name = "data/market_data/manifest.json"
        path = storage.path(name)
        count = storage.metrics["get_requests"]
        storage.path(name)
        self.assertEqual(storage.metrics["get_requests"], count)
        path.write_bytes(b"corrupt")
        storage.path(name)
        self.assertEqual(storage.metrics["get_requests"], count + 1)

    def test_concurrent_cache_reads_download_the_same_file_once(self):
        storage = self.storage()
        before = storage.metrics["get_requests"]
        with ThreadPoolExecutor(max_workers=16) as executor:
            paths = list(executor.map(lambda _: storage.path("market_data/manifest.json"), range(64)))
        self.assertEqual(len(set(paths)), 1)
        self.assertEqual(storage.metrics["get_requests"], before + 1)

    def test_explicit_cached_snapshot_can_be_read_offline(self):
        storage = self.storage()
        storage.path("data/market_data/manifest.json")
        with patch.object(self.client, "get_object", side_effect=AssertionError("network")):
            cached = self.storage(self.snapshot_id)
            self.assertEqual(cached.read_json("data/market_data/manifest.json")["market"], "IN")

    def test_bulk_verification_reuses_valid_cache(self):
        storage = self.storage()
        storage.verify_files()
        count = storage.metrics["get_requests"]
        hits = storage.metrics["cache_hits"]
        with patch.object(self.client, "get_object", side_effect=AssertionError("network")):
            storage.verify_files()
        self.assertEqual(storage.metrics["get_requests"], count)
        self.assertEqual(storage.metrics["cache_hits"] - hits, len(storage.catalog["files"]))

    def test_refresh_during_preparation_cannot_mix_bulk_and_symbol_prices(self):
        read_parquet = pd.read_parquet
        source_path = self.root / "data/market_data/prices.parquet"
        replacement = read_parquet(source_path).assign(Close=9999.0)
        changed = False

        def concurrent_refresh(path, *args, **kwargs):
            nonlocal changed
            if not changed:
                changed = True
                replacement.to_parquet(source_path, index=False)
            return read_parquet(path, *args, **kwargs)

        with patch("services.snapshot_publication.pd.read_parquet", side_effect=concurrent_refresh):
            _, catalog = prepare_snapshot(self.root, self.prepared)
        entries = catalog["files"]
        bulk = read_parquet(self.prepared / entries["market_data/prices.parquet"]["key"])
        manifest = json.loads((self.prepared / entries["market_data/manifest.json"]["key"]).read_bytes())
        for symbol, entry in manifest["symbol_price_files"].items():
            shard = read_parquet(self.prepared / entries[f"market_data/{entry['path']}"]["key"])
            pd.testing.assert_frame_equal(
                bulk.loc[bulk["Symbol"].eq(symbol)].reset_index(drop=True),
                shard.reset_index(drop=True),
            )

    def test_corrupt_download_is_never_cached(self):
        storage = self.storage()
        entry = self.catalog["files"]["market_data/manifest.json"]
        self.client.objects[f"markets/IN/{entry['key']}"] = b"corrupt"
        with self.assertRaisesRegex(SnapshotStorageError, "integrity"):
            storage.path("data/market_data/manifest.json")

    def test_interrupted_upload_does_not_activate(self):
        before = self.client.objects["markets/IN/current.json"]
        (self.root / "data/market_data/fundamentals/fundamentals.csv").write_text("symbol,pe\nTEST.NS,15\n")
        snapshot_id, _ = prepare_snapshot(self.root, self.prepared)
        self.client.fail_upload = True
        with self.assertRaises(SnapshotStorageError):
            self.publisher.publish(self.prepared, snapshot_id)
        self.assertEqual(self.client.objects["markets/IN/current.json"], before)

    def test_concurrent_activation_cannot_overwrite_another_publisher(self):
        _, etag = self.publisher.current()
        self.client.objects["markets/IN/current.json"] = json_bytes(
            {"snapshot_id": self.snapshot_id, "changed": True})
        with self.assertRaisesRegex(SnapshotStorageError, "Another publisher"):
            self.publisher.activate(self.snapshot_id, etag)

    def test_repeated_publication_reuses_unchanged_objects(self):
        second = SnapshotPublisher(self.client, "bucket")
        result = second.publish(self.prepared, self.snapshot_id)
        self.assertEqual(result["uploaded_bytes"], 0)
        self.assertGreater(result["reused_objects"], 0)

    def test_new_layout_has_readable_folders_and_symbol_names(self):
        self.assertEqual(self.catalog["schema_version"], 2)
        for name, entry in self.catalog["files"].items():
            self.assertFalse(name.startswith("data/"))
            self.assertEqual(Path(name).parent, Path(entry["key"]).parent)
            self.assertEqual(Path(name).suffix, Path(entry["key"]).suffix)
        self.assertIn("market_data/symbol_prices/TEST.NS.parquet", self.catalog["files"])
        self.assertIn("market_data/screener/symbol_history/TEST.NS.parquet", self.catalog["files"])

    def _legacy_storage(self):
        files = {}
        for name, entry in self.catalog["files"].items():
            legacy_entry = {**entry, "key": f"objects/{entry['sha256']}"}
            files[f"data/{name}"] = legacy_entry
            key = f"ticksy/markets/IN/{legacy_entry['key']}"
            self.client.objects[key] = (self.prepared / entry["key"]).read_bytes()
            self.client.metadata[key] = {"sha256": entry["sha256"]}
        catalog = {**self.catalog, "schema_version": 1, "files": files}
        content = json_bytes(catalog)
        snapshot_id = hashlib.sha256(content).hexdigest()
        key = f"ticksy/markets/IN/snapshots/{snapshot_id}.json"
        self.client.objects[key] = content
        self.client.metadata[key] = {"sha256": snapshot_id}
        key = "ticksy/markets/IN/current.json"
        self.client.objects[key] = json_bytes({"snapshot_id": snapshot_id})
        self.client.metadata[key] = {}
        return CloudSnapshotStorage(self.client, "bucket", "ticksy/markets/IN",
                                    self.root / "legacy-cache", snapshot_id)

    def test_legacy_snapshots_remain_readable_during_cutover(self):
        legacy = self._legacy_storage()
        self.assertEqual(legacy.read_json("data/market_data/manifest.json")["market"], "IN")

    def test_existing_files_can_be_relocated_by_server_side_copy(self):
        old = self._legacy_storage()
        copies = {entry["sha256"]: f"{old.prefix}/{entry['key']}" for entry in old.catalog["files"].values()}
        publisher = SnapshotPublisher(self.client, "bucket", "relocated/markets/IN")
        result = publisher.publish(self.prepared, self.snapshot_id, copy_source=copies)
        self.assertEqual(result["copied_objects"], len(self.catalog["files"]))
        moved = CloudSnapshotStorage(self.client, "bucket", "relocated/markets/IN", self.root / "moved-cache")
        moved.verify_files()

    def test_invalid_copy_source_prevents_activation(self):
        old = self._legacy_storage()
        copies = {entry["sha256"]: f"{old.prefix}/{entry['key']}" for entry in old.catalog["files"].values()}
        self.client.metadata[next(iter(copies.values()))] = {"sha256": "invalid"}
        publisher = SnapshotPublisher(self.client, "bucket", "relocated/markets/IN")
        with self.assertRaises(SnapshotStorageError):
            publisher.publish(self.prepared, self.snapshot_id, copy_source=copies)
        self.assertNotIn("relocated/markets/IN/current.json", self.client.objects)

    def test_empty_prefix_uses_markets_at_bucket_root(self):
        self.assertEqual(market_storage_prefix({}, "IN"), "markets/IN")
        self.assertEqual(market_storage_prefix({"prefix": ""}, "US"), "markets/US")
        self.assertEqual(market_storage_prefix({"prefix": "ticksy"}, "IN"), "ticksy/markets/IN")

    def test_legacy_retirement_preserves_destination_and_unrelated_files(self):
        old = self._legacy_storage()
        self.client.objects["unrelated/file.txt"] = b"keep"
        count = retire_legacy_snapshot(self.client, "bucket", self.storage(), old.snapshot_id)
        self.assertGreater(count, 0)
        self.assertFalse(any(key.startswith("ticksy/") for key in self.client.objects))
        self.assertIn("markets/IN/current.json", self.client.objects)
        self.assertIn("unrelated/file.txt", self.client.objects)
        self.storage().verify_files()

    def test_legacy_retirement_refuses_unexpected_source_objects(self):
        old = self._legacy_storage()
        self.client.objects["ticksy/markets/IN/unexpected.txt"] = b"keep"
        before = set(self.client.objects)
        with self.assertRaisesRegex(SnapshotStorageError, "unexpected"):
            retire_legacy_snapshot(self.client, "bucket", self.storage(), old.snapshot_id)
        self.assertEqual(before, set(self.client.objects))

    def test_daily_staging_retains_source_data_without_derived_chart_copies(self):
        staged = self.root / "daily-stage"
        self.assertGreater(stage_source_snapshot(self.storage(), staged), 0)
        self.assertTrue((staged / "data/market_data/prices.parquet").is_file())
        self.assertTrue((staged / "data/market_data/screener/history.parquet").is_file())
        self.assertFalse((staged / "data/market_data/symbol_prices").exists())

    def test_daily_refresh_no_new_data_keeps_cloud_snapshot(self):
        from unittest.mock import Mock

        configuration = {"bucket": "bucket", "prefix": "", "endpoint_url": "https://example.test"}
        before = dict(self.client.objects)
        command = Mock()
        with patch("scripts.refresh_cloud_market_data.configured_cloud_storage", return_value=self.storage()), \
             patch("scripts.refresh_cloud_market_data.create_storage_client", return_value=self.client):
            result = run_daily_refresh(self.root, configuration, configuration, command)
        self.assertEqual(result["status"], "no_new_data")
        self.assertEqual(before, self.client.objects)
        self.assertEqual([call.args[0][4] for call in command.call_args_list], ["incremental", "validate"])

    def test_daily_refresh_publishes_and_verifies_changed_snapshot(self):
        configuration = {"bucket": "bucket", "prefix": "", "endpoint_url": "https://example.test"}

        def execute(arguments, check):
            if arguments[4] == "incremental":
                path = Path(arguments[-1]) / "data/market_data/manifest.json"
                value = json.loads(path.read_text())
                value["generated_at"] = "new-refresh"
                write_json(path, value)

        def storage_for(settings, project_root):
            return self.storage(settings.get("snapshot_ids", {}).get("IN", ""))

        with patch("scripts.refresh_cloud_market_data.configured_cloud_storage", side_effect=storage_for), \
             patch("scripts.refresh_cloud_market_data.create_storage_client", return_value=self.client):
            result = run_daily_refresh(self.root, configuration, configuration, execute)
        self.assertEqual(result["status"], "published")
        self.assertNotEqual(result["snapshot_id"], self.snapshot_id)
        self.assertEqual(self.storage().read_json("market_data/manifest.json")["generated_at"], "new-refresh")

    def test_refresh_cannot_overwrite_a_newer_parent_snapshot(self):
        with self.assertRaisesRegex(SnapshotStorageError, "changed during refresh"):
            self.publisher.publish(self.prepared, self.snapshot_id, expected_snapshot_id="b" * 64)
        self.assertEqual(self.storage().snapshot_id, self.snapshot_id)

    def test_remote_verification_failure_keeps_previous_pointer(self):
        before = self.client.objects["markets/IN/current.json"]
        manifest = self.root / "data/market_data/manifest.json"
        value = json.loads(manifest.read_text())
        value["generated_at"] = "candidate"
        write_json(manifest, value)
        candidate, _ = prepare_snapshot(self.root, self.prepared)
        with patch.object(CloudSnapshotStorage, "verify_files", side_effect=SnapshotStorageError("corrupt")):
            with self.assertRaisesRegex(SnapshotStorageError, "corrupt"):
                self.publisher.publish(self.prepared, candidate)
        self.assertEqual(self.client.objects["markets/IN/current.json"], before)

    def test_cloud_validation_never_publishes(self):
        from unittest.mock import Mock

        configuration = {"bucket": "bucket", "prefix": "", "endpoint_url": "https://example.test"}
        before = dict(self.client.objects)
        command = Mock()
        with patch("scripts.refresh_cloud_market_data.configured_cloud_storage", return_value=self.storage()), \
             patch("scripts.refresh_cloud_market_data.create_storage_client", return_value=self.client):
            result = run_daily_refresh(self.root, configuration, configuration, command, mode="validate")
        self.assertEqual(result["status"], "validated")
        self.assertEqual(before, self.client.objects)
        self.assertEqual([call.args[0][4] for call in command.call_args_list], ["validate"])

    def test_screener_refresh_updates_supporting_data_before_publication(self):
        configuration = {"bucket": "bucket", "prefix": "", "endpoint_url": "https://example.test"}
        operations = []

        def execute(arguments, check):
            operations.append((Path(arguments[2]).name, arguments[4]))
            if arguments[4] == "refresh":
                self.assertIn("--durable-checkpoint", arguments)
                self.assertEqual(arguments[arguments.index("--config-source") + 1], "github")
                path = Path(arguments[arguments.index("--data-root") + 1]) / "data/market_data/screener/manifest.json"
                manifest = json.loads(path.read_text())
                manifest["successful_symbol_count"] = 1
                manifest["generated_at"] = "new-screener"
                write_json(path, manifest)

        def storage_for(settings, project_root):
            return self.storage(settings.get("snapshot_ids", {}).get("IN", ""))

        with patch("scripts.refresh_cloud_market_data.configured_cloud_storage", side_effect=storage_for), \
             patch("scripts.refresh_cloud_market_data.create_storage_client", return_value=self.client):
            result = run_daily_refresh(self.root, configuration, configuration, execute,
                                       dataset="screener", config_source="github")
        self.assertEqual([mode for _, mode in operations], ["refresh", "validate", "fundamentals", "validate"])
        self.assertEqual(result["status"], "published")
        self.assertEqual(self.storage().read_json("market_data/screener/manifest.json")["generated_at"], "new-screener")

    def test_empty_screener_refresh_cannot_publish(self):
        configuration = {"bucket": "bucket", "prefix": "", "endpoint_url": "https://example.test"}
        before = dict(self.client.objects)
        with patch("scripts.refresh_cloud_market_data.configured_cloud_storage", return_value=self.storage()), \
             patch("scripts.refresh_cloud_market_data.create_storage_client", return_value=self.client), \
             self.assertRaisesRegex(SnapshotStorageError, "coverage"):
            run_daily_refresh(self.root, configuration, configuration, lambda *args, **kwargs: None,
                              dataset="screener")
        self.assertEqual(before, self.client.objects)

    def test_universe_refresh_synchronizes_market_data_before_publication(self):
        configuration = {"bucket": "bucket", "prefix": "", "endpoint_url": "https://example.test"}
        operations = []

        def execute(arguments, check):
            staged = Path(arguments[-1])
            universe_path = staged / "data/stock_universe/manifest.json"
            if arguments[2].endswith("refresh_stock_universe.py"):
                operations.append("universe")
                universe = json.loads(universe_path.read_text())
                universe["refreshed_at"] = "2026-10-17"
                write_json(universe_path, universe)
            else:
                operations.append(arguments[4])

        def storage_for(settings, project_root):
            return self.storage(settings.get("snapshot_ids", {}).get("IN", ""))

        with patch("scripts.refresh_cloud_market_data.configured_cloud_storage", side_effect=storage_for), \
             patch("scripts.refresh_cloud_market_data.create_storage_client", return_value=self.client):
            result = run_daily_refresh(self.root, configuration, configuration, execute, refresh_universe=True)
        self.assertEqual(operations, ["universe", "incremental", "validate"])
        self.assertEqual(result["status"], "published")
        self.assertEqual(result["universe"]["validated_count"], 2)
        self.assertEqual(result["universe"]["added"], [])

    def test_failed_universe_refresh_does_not_change_active_cloud_snapshot(self):
        from subprocess import CalledProcessError

        configuration = {"bucket": "bucket", "prefix": "", "endpoint_url": "https://example.test"}
        before = dict(self.client.objects)
        with patch("scripts.refresh_cloud_market_data.configured_cloud_storage", return_value=self.storage()), \
             patch("scripts.refresh_cloud_market_data.create_storage_client", return_value=self.client), \
             self.assertRaises(CalledProcessError):
            run_daily_refresh(self.root, configuration, configuration,
                              lambda *args, **kwargs: (_ for _ in ()).throw(CalledProcessError(1, "universe")),
                              refresh_universe=True)
        self.assertEqual(before, self.client.objects)

    def test_market_identity_and_namespaces_cannot_mix(self):
        self.assertNotEqual(stock_key("IN", "SAME"), stock_key("US", "SAME"))
        with self.assertRaisesRegex(SnapshotStorageError, "different market"):
            self.storage(market="US")
        with self.assertRaises(ValueError):
            build_data_services(SNAPSHOT_SOURCE, self.root, self.storage(), market="US")
        with self.assertRaises(SnapshotStorageError):
            SnapshotPublisher(self.client, "bucket", "markets/US", "US").publish(self.prepared, self.snapshot_id)
        with self.assertRaises(ValueError):
            stock_key("UNKNOWN", "TEST")

    def test_us_preparation_requires_explicit_us_manifests(self):
        us_root = market_data_root(self.root, "US")
        create_fixture(us_root, "US")
        _, catalog = prepare_snapshot(self.root, self.root / "us-prepared", "US")
        self.assertEqual(catalog["market"], "US")
        self.assertEqual(catalog["currency"], "USD")
        self.assertIn("market_data/sec/manifest.json", catalog["files"])
        self.assertNotIn("market_data/screener/manifest.json", catalog["files"])

    def test_source_hash_validation_and_path_traversal(self):
        for name in ("../secrets.toml", "/absolute", "C:/secrets", "a\\b", "a/../b"):
            with self.subTest(name=name), self.assertRaises(SnapshotStorageError):
                safe_relative_path(name)
        path = self.root / "data/stock_universe/universe.csv"
        path.write_text("Symbol\nWRONG\n")
        with self.assertRaisesRegex(SnapshotStorageError, "Source hash"):
            prepare_snapshot(self.root, self.prepared)

    def test_windows_newlines_are_accepted_only_when_manifest_hash_matches(self):
        path = self.root / "data/market_data/fundamentals/fundamentals.csv"
        original = path.read_bytes().replace(b"\r\n", b"\n")
        manifest_path = self.root / "data/market_data/manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["fundamentals_file"]["sha256"] = hashlib.sha256(original).hexdigest()
        write_json(manifest_path, manifest)
        path.write_bytes(original.replace(b"\n", b"\r\n"))
        _, catalog = prepare_snapshot(self.root, self.prepared)
        self.assertEqual(catalog["files"]["market_data/fundamentals/fundamentals.csv"]["sha256"], hashlib.sha256(original).hexdigest())
        path.write_bytes(b"unrelated corruption")
        with self.assertRaises(SnapshotStorageError):
            prepare_snapshot(self.root, self.prepared)

    def test_restore_reuses_verified_old_snapshot(self):
        old = self.snapshot_id
        (self.root / "data/market_data/fundamentals/fundamentals.csv").write_text("symbol,pe\nTEST.NS,15\n")
        new, _ = prepare_snapshot(self.root, self.prepared)
        self.publisher.publish(self.prepared, new)
        _, etag = self.publisher.current()
        storage = self.storage(old)
        for name in storage.catalog["files"]:
            storage.path(name)
        self.publisher.activate(old, etag)
        self.assertEqual(self.storage().snapshot_id, old)

    def test_scan_and_backtest_outputs_match_across_storage(self):
        local = build_data_services(SNAPSHOT_SOURCE, self.root, LocalSnapshotStorage(self.root))
        remote = build_data_services(SNAPSHOT_SOURCE, self.root, self.storage())
        config = ScanConfig(50, 200, 80, 60, 10, 10)
        scans, replays = [], []
        for services in (local, remote):
            run = ScanService(config, services.history, services.fundamentals, services.industry_valuation, services.screener).scan(["TEST.NS"])
            scans.append(run.as_dataframes())
            batch = services.history.download_batch(["TEST.NS"], years=10)
            history = services.history.get_symbol_history(batch, "TEST.NS")
            engine = BacktestService(config, services.screener)
            # Isolate signal/return parity from the strategy's decline rule.
            engine._qualifies = lambda history: True
            replays.append(engine.replay_symbol("TEST.NS", history).signals)
        for group in scans[0]:
            pd.testing.assert_frame_equal(scans[0][group], scans[1][group])
        self.assertEqual(len(replays[0]), 1)
        self.assertEqual(replays[0], replays[1])


if __name__ == "__main__":
    unittest.main()
