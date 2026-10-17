"""Git archive integrity and complete, reproducible cloud exports."""

import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.data_retirement import archive_git_data, export_cloud_snapshot, restore_git_archive
from services.snapshot_publication import SnapshotPublisher, prepare_snapshot
from services.snapshot_storage import CloudSnapshotStorage, SnapshotStorageError
from tests.snapshot_fixtures import create_fixture
from tests.test_cloud_snapshots import MemoryS3


class GitArchiveTests(unittest.TestCase):
    def test_archive_verifies_exact_committed_bytes_and_preserves_active_pointer(self):
        client = MemoryS3()
        client.objects["markets/IN/current.json"] = b"unchanged"
        files = {"data/market_data/test.csv": b"Symbol\nTEST.NS\n",
                 "data/stock_universe/old.csv": b"historical-universe"}
        with patch("services.data_retirement.collect_git_data", return_value=("a" * 40, files)):
            record = archive_git_data(Path("unused"), client, "bucket", "markets/IN", "b" * 64)
        prefix = record["archive_prefix"]
        manifest = client.objects[prefix + "/manifest.json"]
        self.assertEqual(hashlib.sha256(manifest).hexdigest(), record["archive_id"])
        self.assertEqual(len(json.loads(manifest)["files"]), 2)
        for name, content in files.items():
            self.assertEqual(client.objects[f"{prefix}/files/{name}"], content)
        self.assertEqual(client.objects["markets/IN/current.json"], b"unchanged")
        with TemporaryDirectory() as temporary:
            result = restore_git_archive(client, "bucket", record, Path(temporary))
            self.assertEqual(result["restored_files"], len(files))
            for name, content in files.items():
                self.assertEqual((Path(temporary) / name).read_bytes(), content)

    def test_corrupted_archive_is_rejected_before_restore_writes(self):
        client = MemoryS3()
        files = {"data/market_data/test.csv": b"committed"}
        with patch("services.data_retirement.collect_git_data", return_value=("a" * 40, files)):
            record = archive_git_data(Path("unused"), client, "bucket", "markets/IN", "b" * 64)
        client.objects[record["archive_prefix"] + "/files/data/market_data/test.csv"] = b"changed"
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(SnapshotStorageError, "data verification"):
                restore_git_archive(client, "bucket", record, Path(temporary))
            self.assertFalse((Path(temporary) / "data").exists())

    def test_failed_upload_never_creates_a_verified_manifest(self):
        client = MemoryS3()
        client.fail_upload = True
        with patch("services.data_retirement.collect_git_data", return_value=("a" * 40, {"data/market_data/test.csv": b"data"})):
            with self.assertRaises(SnapshotStorageError):
                archive_git_data(Path("unused"), client, "bucket", "markets/IN", "b" * 64)
        self.assertFalse(any(key.endswith("/manifest.json") for key in client.objects))

    def test_india_archive_cannot_be_written_to_us(self):
        with self.assertRaisesRegex(SnapshotStorageError, "belongs to India"):
            archive_git_data(Path("unused"), MemoryS3(), "bucket", "markets/US", "b" * 64)


class CloudExportTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        create_fixture(self.root)
        prepared = self.root / "prepared"
        self.snapshot_id, self.catalog = prepare_snapshot(self.root, prepared)
        self.client = MemoryS3()
        SnapshotPublisher(self.client, "bucket").publish(prepared, self.snapshot_id)
        self.storage = CloudSnapshotStorage(self.client, "bucket", "markets/IN", self.root / "cache")

    def test_export_includes_every_source_manifest_and_per_symbol_file(self):
        destination = self.root / "download"
        result = export_cloud_snapshot(self.storage, destination)
        self.assertEqual(result["files"], len(self.catalog["files"]))
        for name, entry in self.catalog["files"].items():
            content = (destination / "data" / name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), entry["sha256"])
        self.assertTrue((destination / "data/market_data/symbol_prices/TEST.NS.parquet").exists())
        export_cloud_snapshot(self.storage, destination)  # matching exports resume safely

    def test_conflicting_local_data_requires_explicit_overwrite(self):
        destination = self.root / "download"
        path = destination / "data/market_data/manifest.json"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"local edits")
        with self.assertRaisesRegex(SnapshotStorageError, "Local data differs"):
            export_cloud_snapshot(self.storage, destination)
        self.assertEqual(path.read_bytes(), b"local edits")
        export_cloud_snapshot(self.storage, destination, overwrite=True)
        self.assertNotEqual(path.read_bytes(), b"local edits")

    def test_corrupt_remote_file_stops_export_before_any_manifest_is_written(self):
        entry = self.catalog["files"]["market_data/prices.parquet"]
        self.client.objects["markets/IN/" + entry["key"]] = b"corrupt"
        with self.assertRaises(SnapshotStorageError):
            export_cloud_snapshot(self.storage, self.root / "download")
        self.assertFalse((self.root / "download/data/market_data/manifest.json").exists())
