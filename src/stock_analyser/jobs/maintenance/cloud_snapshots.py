"""Prepare, publish, verify, or restore R2/S3 snapshots.

Credentials are read only from .streamlit/secrets.toml, never CLI arguments.
"""

from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

from stock_analyser.infrastructure.r2.publication import (
    SnapshotPublisher,
    prepare_snapshot,
    retire_legacy_snapshot,
)
from stock_analyser.infrastructure.r2.config import (
    configured_cloud_storage,
    create_storage_client,
    market_storage_prefix,
)
from stock_analyser.infrastructure.r2.storage import (
    CloudSnapshotStorage,
    SnapshotStorageError,
)
from stock_analyser.infrastructure.r2.data_retirement import export_cloud_snapshot


PROJECT_ROOT = Path(__file__).resolve().parents[4]


def report_progress(completed, total):
    if completed % 250 == 0 or completed == total:
        print(f"Validated objects: {completed}/{total}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "publish", "verify", "restore", "retire-legacy", "inventory", "download"))
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT,
                        help="Destination project root for a local cloud snapshot download")
    parser.add_argument("--overwrite", action="store_true", help="Explicitly overwrite differing local snapshot files")
    parser.add_argument("--snapshot-id", default="")
    parser.add_argument("--market", choices=("IN", "US"), default="IN")
    parser.add_argument("--root-layout", action="store_true", help="Use markets/ directly under the bucket")
    parser.add_argument("--copy-from-prefix", default="", help="Reuse verified objects from an older market prefix")
    parser.add_argument("--legacy-snapshot-id", default="", help="Exact initial snapshot to retire after cutover")
    arguments = parser.parse_args()
    prepared = PROJECT_ROOT / ".snapshot-cache" / "prepared" / arguments.market
    if arguments.mode == "prepare":
        snapshot_id, catalog = prepare_snapshot(PROJECT_ROOT, prepared, arguments.market)
        print(json.dumps({
            "snapshot_id": snapshot_id, "files": len(catalog["files"]),
            "logical_bytes": sum(entry["size_bytes"] for entry in catalog["files"].values()),
            "last_trading_date": catalog.get("last_trading_date"),
        }, indent=2))
        return
    if arguments.mode in {"publish", "restore", "retire-legacy"} and not arguments.snapshot_id:
        parser.error("--snapshot-id is required for publish and restore")
    with (PROJECT_ROOT / ".streamlit" / "secrets.toml").open("rb") as stream:
        secrets = tomllib.load(stream)
    section = "storage_publisher" if arguments.mode in {"publish", "restore", "retire-legacy"} else "storage"
    configuration = dict(secrets[section])
    if arguments.root_layout:
        configuration["prefix"] = ""
    client = create_storage_client(configuration)
    bucket = configuration["bucket"]
    prefix = market_storage_prefix(configuration, arguments.market)
    if arguments.mode == "inventory":
        folders = {}
        for directory in ("", f"{prefix}/", f"{prefix}/market_data/"):
            page = client.list_objects_v2(Bucket=bucket, Prefix=directory, Delimiter="/")
            folders[directory or "bucket root"] = [item["Prefix"] for item in page.get("CommonPrefixes", [])]
        print(json.dumps(folders, indent=2))
        return
    publisher = SnapshotPublisher(client, bucket, prefix, arguments.market)
    if arguments.mode == "publish":
        copy_source = None
        if arguments.copy_from_prefix:
            old = CloudSnapshotStorage(client, bucket, arguments.copy_from_prefix,
                PROJECT_ROOT / ".snapshot-cache" / "relocation-source" / arguments.market,
                market=arguments.market)
            copy_source = {entry["sha256"]: f"{old.prefix}/{entry['key']}"
                           for entry in old.catalog["files"].values()}
        print(json.dumps(publisher.publish(prepared, arguments.snapshot_id, report_progress, copy_source), indent=2))
        print(f"Published snapshot {arguments.snapshot_id}")
        return
    # Capture the pointer before verification so concurrent publications cannot
    # be overwritten by a restore that began against an older active version.
    _, expected_etag = publisher.current()
    pinned_configuration = dict(configuration)
    if arguments.snapshot_id:
        pinned_configuration["snapshot_ids"] = {arguments.market: arguments.snapshot_id}
    storage = configured_cloud_storage(pinned_configuration, PROJECT_ROOT, arguments.market)
    if arguments.mode == "download":
        print(json.dumps(export_cloud_snapshot(storage, arguments.data_root, arguments.overwrite), indent=2))
        return
    if arguments.mode == "retire-legacy":
        if not arguments.legacy_snapshot_id:
            parser.error("--legacy-snapshot-id is required for retirement")
        count = retire_legacy_snapshot(client, bucket, storage, arguments.legacy_snapshot_id)
        print(f"Retired {count} verified legacy keys; root layout retained")
        return
    storage.verify_files(report_progress)
    print(json.dumps({"snapshot_id": storage.snapshot_id, **storage.metrics}, indent=2))
    if arguments.mode == "restore":
        publisher.activate(storage.snapshot_id, expected_etag)
        print("Verified snapshot restored")


if __name__ == "__main__":
    try:
        main()
    except (SnapshotStorageError, KeyError, OSError, ValueError):
        # SDK/config exceptions can embed endpoint details; never dump secrets.
        print("Cloud snapshot operation failed. Check configuration, access, and snapshot integrity.", file=sys.stderr)
        sys.exit(1)
