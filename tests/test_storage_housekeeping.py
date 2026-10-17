"""Retention, upload exclusion, offline cache safety, and usage reporting."""

import hashlib
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from services.cache_housekeeping import cache_cleanup_plan, apply_cache_cleanup
from services.snapshot_publication import json_bytes
from services.snapshot_storage import SnapshotStorageError, dataset_object_key
from services.storage_housekeeping import retention_plan, apply_retention
from services.storage_lease import StorageLease
from tests.test_cloud_snapshots import MemoryS3
from scripts.storage_housekeeping import workflow_write_audit


NOW = datetime(2026, 10, 17, tzinfo=timezone.utc)


class InventoryS3(MemoryS3):
    def __init__(self):
        super().__init__()
        self.modified = {}
        self.page_size = 2

    def put_object(self, **kwargs):
        super().put_object(**kwargs)
        self.modified[kwargs["Key"]] = NOW - timedelta(days=40)

    def list_objects_v2(self, Bucket, Prefix, ContinuationToken="0"):
        keys = sorted(key for key in self.objects if key.startswith(Prefix))
        start = int(ContinuationToken)
        page = keys[start:start + self.page_size]
        return {"Contents": [{"Key": key, "Size": len(self.objects[key]),
                    "LastModified": self.modified[key],
                    "ETag": hashlib.md5(self.objects[key]).hexdigest()} for key in page],
                "IsTruncated": start + self.page_size < len(keys),
                "NextContinuationToken": str(start + self.page_size)}


def policy():
    return {"keep_latest": 1, "keep_monthly": 0, "grace_days": 7,
            "protected_snapshot_ids": [], "storage_budget_bytes": 10_000_000,
            "warning_fraction": 0.8, "cache_max_age_days": 7, "cache_budget_bytes": 1000}


def add_catalog(client, content, age_days=30, shared=False):
    files = {}
    for name, payload in [("market_data/value.csv", content)] + (
            [("market_data/shared.csv", b"shared")] if shared else []):
        digest = hashlib.sha256(payload).hexdigest()
        key = dataset_object_key(name, digest)
        full = "markets/IN/" + key
        if full not in client.objects:
            client.put_object(Bucket="bucket", Key=full, Body=payload, Metadata={"sha256": digest})
            client.modified[full] = NOW - timedelta(days=age_days)
        files[name] = {"key": key, "sha256": digest, "size_bytes": len(payload)}
    catalog = {"schema_version": 2, "market": "IN", "files": files}
    content = json_bytes(catalog)
    sid = hashlib.sha256(content).hexdigest()
    key = f"markets/IN/snapshots/{sid}.json"
    client.put_object(Bucket="bucket", Key=key, Body=content)
    client.modified[key] = NOW - timedelta(days=age_days)
    return sid, catalog


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.client = InventoryS3()
        self.old, self.old_catalog = add_catalog(self.client, b"old", 80, shared=True)
        self.current, self.current_catalog = add_catalog(self.client, b"new", 30, shared=True)
        self.client.put_object(Bucket="bucket", Key="markets/IN/current.json",
                               Body=json_bytes({"snapshot_id": self.current}))
        self.policy = policy()

    def plan(self):
        return retention_plan(self.client, "bucket", "markets/IN", self.policy, NOW)

    def test_paginated_inventory_keeps_shared_and_active_files(self):
        plan = self.plan()
        deleted = {item["key"] for item in plan["delete_candidates"]}
        self.assertIn(f"markets/IN/snapshots/{self.old}.json", deleted)
        for entry in self.current_catalog["files"].values():
            self.assertNotIn("markets/IN/" + entry["key"], deleted)
        result = apply_retention(self.client, "bucket", "markets/IN", self.policy, plan["plan_id"], now=NOW)
        self.assertEqual(result["deleted_objects"], 2)
        self.assertEqual(json.loads(self.client.objects["markets/IN/current.json"])["snapshot_id"], self.current)

    def test_monthly_checkpoints_and_pins_survive(self):
        self.policy["keep_monthly"] = 12
        self.assertIn(self.old, self.plan()["retained_snapshot_ids"])
        self.policy["keep_monthly"] = 0
        self.policy["protected_snapshot_ids"] = [self.old]
        self.assertEqual(self.plan()["delete_candidates"], [])

    def test_current_snapshot_survives_even_when_it_is_not_newest(self):
        add_catalog(self.client, b"unactivated-newer", 20)
        plan = self.plan()
        self.assertIn(self.current, plan["retained_snapshot_ids"])
        self.assertNotIn("markets/IN/current.json", [x["key"] for x in plan["delete_candidates"]])

    def test_recent_uploads_unknown_files_and_other_markets_are_preserved(self):
        orphan = "markets/IN/market_data/orphan--" + "a" * 64 + ".csv"
        for key in [orphan, "markets/IN/private.txt", "markets/US/unknown.csv"]:
            self.client.put_object(Bucket="bucket", Key=key, Body=b"keep")
        self.client.modified[orphan] = NOW
        deleted = {item["key"] for item in self.plan()["delete_candidates"]}
        self.assertNotIn(orphan, deleted)
        self.assertNotIn("markets/IN/private.txt", deleted)
        self.assertFalse(any("markets/US" in key for key in deleted))
        self.assertIn("markets/IN/private.txt", self.plan()["unknown_keys_preserved"])

    def test_old_orphan_is_reclaimable(self):
        key = "markets/IN/market_data/orphan--" + "b" * 64 + ".csv"
        self.client.put_object(Bucket="bucket", Key=key, Body=b"orphan", Metadata={"sha256": "b" * 64})
        self.assertIn(key, [item["key"] for item in self.plan()["delete_candidates"]])

    def test_versioned_filename_without_ownership_metadata_is_preserved(self):
        key = "markets/IN/market_data/manual--" + "d" * 64 + ".csv"
        self.client.put_object(Bucket="bucket", Key=key, Body=b"manual")
        plan = self.plan()
        self.assertNotIn(key, [item["key"] for item in plan["delete_candidates"]])
        self.assertIn(key, plan["unknown_keys_preserved"])

    def test_storage_delete_errors_are_not_reported_as_success(self):
        plan = self.plan()
        with patch.object(self.client, "delete_objects", return_value={"Errors": [{"Code": "AccessDenied"}]}):
            with self.assertRaisesRegex(SnapshotStorageError, "partially failed"):
                apply_retention(self.client, "bucket", "markets/IN", self.policy, plan["plan_id"], now=NOW)

    def test_changed_pointer_rejects_a_reviewed_plan(self):
        plan = self.plan()
        self.client.put_object(Bucket="bucket", Key="markets/IN/current.json",
                               Body=json_bytes({"snapshot_id": self.old}))
        with self.assertRaisesRegex(SnapshotStorageError, "plan changed"):
            apply_retention(self.client, "bucket", "markets/IN", self.policy, plan["plan_id"], now=NOW)
        self.assertIn(f"markets/IN/snapshots/{self.old}.json", self.client.objects)

    def test_missing_retained_object_stops_cleanup(self):
        entry = self.current_catalog["files"]["market_data/value.csv"]
        del self.client.objects["markets/IN/" + entry["key"]]
        with self.assertRaisesRegex(SnapshotStorageError, "missing or inconsistent"):
            self.plan()

    def test_corrupt_catalog_and_missing_pin_stop_cleanup(self):
        self.policy["protected_snapshot_ids"] = ["a" * 64]
        with self.assertRaisesRegex(SnapshotStorageError, "protected catalog"):
            self.plan()
        self.policy["protected_snapshot_ids"] = []
        self.client.objects[f"markets/IN/snapshots/{self.old}.json"] = b"corrupt"
        with self.assertRaisesRegex(SnapshotStorageError, "hash mismatch"):
            self.plan()

    def test_budget_warning_is_reported_without_deleting(self):
        self.policy["storage_budget_bytes"] = 1
        before = dict(self.client.objects)
        self.assertTrue(self.plan()["usage_warning"])
        self.assertEqual(before, self.client.objects)

    def test_publisher_lease_blocks_cleanup(self):
        plan = self.plan()
        with StorageLease(self.client, "bucket", "markets/IN"):
            with self.assertRaisesRegex(SnapshotStorageError, "Another publisher"):
                apply_retention(self.client, "bucket", "markets/IN", self.policy, plan["plan_id"], now=NOW)

    def test_expired_owner_cannot_renew_or_release_new_owners_lease(self):
        clock = [NOW]
        first = StorageLease(self.client, "bucket", "markets/IN", lambda: clock[0])
        first.__enter__()
        clock[0] += timedelta(hours=2)
        with StorageLease(self.client, "bucket", "markets/IN", lambda: clock[0]) as second:
            with self.assertRaisesRegex(SnapshotStorageError, "expired or changed"):
                first.renew()
            first.__exit__(None, None, None)
            second.renew()


class WorkflowWriteAuditTests(unittest.TestCase):
    def test_actual_data_workflows_target_r2_with_read_only_git_permissions(self):
        reports = workflow_write_audit(Path(__file__).resolve().parents[1])
        self.assertEqual(len(reports), 3)
        for report in reports:
            self.assertEqual(report["data_target"], "R2")
            self.assertEqual(report["direct_git_write_commands"], [])
            self.assertEqual(report["repository_contents_permission"], "read")

    def test_git_writing_workflow_is_identified(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = root / ".github/workflows"
            directory.mkdir(parents=True)
            (directory / "legacy.yml").write_text("permissions:\n  contents: write\nsteps:\n  run: git push origin main\n")
            report = workflow_write_audit(root)[0]
        self.assertEqual(report["direct_git_write_commands"], ["git push"])
        self.assertEqual(report["repository_contents_permission"], "write")


class CacheCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.reader = self.root / ".snapshot-cache/reader/IN"
        self.policy = policy()
        digest = "a" * 64
        self.catalog = {"files": {"market_data/data.csv": {"sha256": digest}}}
        self.active = self.make_file(f"reader/IN/objects/{digest}.csv", old=True)
        self.stale = self.make_file(f"reader/IN/objects/{'b' * 64}.csv", old=True)
        self.fresh = self.make_file(f"reader/IN/objects/{'c' * 64}.csv", old=False)
        self.report = self.make_file("market-refresh/IN/20260101T120000000000Z/refresh_report.json", old=True)
        self.staged = self.make_file("market-refresh/IN/20260101T120000000000Z/data/prices.csv", old=True)
        self.unknown = self.make_file("personal-notes.txt", old=True)

    def make_file(self, name, old):
        path = self.root / ".snapshot-cache" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
        when = (NOW - timedelta(days=30) if old else NOW).timestamp()
        os.utime(path, (when, when))
        return path

    def plan(self):
        return cache_cleanup_plan(self.root, self.reader, self.catalog, self.policy, NOW)

    def test_offline_cleanup_only_removes_old_regenerable_files(self):
        plan = self.plan()
        self.assertEqual(len(plan["delete_candidates"]), 2)
        with self.assertRaisesRegex(SnapshotStorageError, "Stop apps"):
            apply_cache_cleanup(self.root, self.reader, self.catalog, self.policy, plan["plan_id"], now=NOW)
        apply_cache_cleanup(self.root, self.reader, self.catalog, self.policy, plan["plan_id"], offline=True, now=NOW)
        self.assertFalse(self.stale.exists())
        self.assertFalse(self.staged.exists())
        for path in [self.active, self.fresh, self.report, self.unknown]:
            self.assertTrue(path.exists())

    def test_changed_file_rejects_stale_preview(self):
        plan = self.plan()
        self.stale.write_text("new content")
        with self.assertRaisesRegex(SnapshotStorageError, "plan changed"):
            apply_cache_cleanup(self.root, self.reader, self.catalog, self.policy, plan["plan_id"], offline=True, now=NOW)

    def test_cache_scope_cannot_escape_project(self):
        with self.assertRaisesRegex(SnapshotStorageError, "escapes"):
            cache_cleanup_plan(self.root, self.root.parent, self.catalog, self.policy, NOW)

    def test_linked_cache_root_is_refused(self):
        with patch("services.cache_housekeeping._linked", return_value=True):
            with self.assertRaisesRegex(SnapshotStorageError, "link or junction"):
                self.plan()
