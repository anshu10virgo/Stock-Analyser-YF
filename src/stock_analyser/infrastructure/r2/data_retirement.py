"""Verified Git-data archival and explicit cloud-to-local development exports."""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from stock_analyser.domain.markets import market_data_root
from stock_analyser.infrastructure.r2.housekeeping import read_object
from stock_analyser.infrastructure.r2.lease import StorageLease
from stock_analyser.infrastructure.r2.publication import SnapshotPublisher, json_bytes
from stock_analyser.infrastructure.r2.storage import (
    LocalSnapshotStorage,
    SnapshotStorageError,
    atomic_write,
    sha256_file,
)


def collect_git_data(project_root):
    """Read committed bytes, not Windows-converted or untracked working files."""
    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=project_root)

    commit = git("rev-parse", "HEAD").decode().strip()
    paths = git("ls-tree", "-rz", "--name-only", commit, "--", "data").split(b"\0")
    files = {}
    for encoded in paths:
        if not encoded:
            continue
        name = encoded.decode("utf-8")
        if not name.startswith(("data/market_data/", "data/stock_universe/")):
            raise SnapshotStorageError("Git data contains an unexpected dataset")
        files[name] = git("show", f"{commit}:{name}")
    if not files:
        raise SnapshotStorageError("No committed production data remains to archive")
    return commit, files


def archive_git_data(project_root, client, bucket, market_prefix, baseline_snapshot_id):
    if market_prefix.rsplit("/", 1)[-1] != "IN":
        raise SnapshotStorageError("The Git production archive belongs to India")
    commit, files = collect_git_data(project_root)
    manifest = {"schema_version": 1, "kind": "git-data-archive", "market": "IN",
                "source_commit": commit, "files": {
                    name: {"sha256": hashlib.sha256(content).hexdigest(), "size_bytes": len(content)}
                    for name, content in sorted(files.items())}}
    content = json_bytes(manifest)
    archive_id = hashlib.sha256(content).hexdigest()
    prefix = f"{market_prefix}/archives/git-data/{archive_id}"
    publisher = SnapshotPublisher(client, bucket, prefix)
    with StorageLease(client, bucket, market_prefix) as lease:
        for index, (name, payload) in enumerate(files.items(), 1):
            publisher._put_immutable(f"files/{name}", payload, manifest["files"][name]["sha256"])
            remote, _ = read_object(client, bucket, f"{prefix}/files/{name}")
            if remote != payload:
                raise SnapshotStorageError("Git archive read-back verification failed")
            if index % 5 == 0:
                lease.renew()
        publisher._put_immutable("manifest.json", content, archive_id)
        remote, _ = read_object(client, bucket, f"{prefix}/manifest.json")
        if remote != content:
            raise SnapshotStorageError("Git archive manifest verification failed")
    return {"schema_version": 1, "status": "archived_and_verified", "archive_id": archive_id,
            "archive_prefix": prefix, "source_commit": commit, "market": "IN",
            "baseline_snapshot_id": baseline_snapshot_id, "file_count": len(files),
            "total_bytes": sum(len(payload) for payload in files.values()),
            "verified_at": datetime.now(timezone.utc).isoformat()}


def _export_path(target, name, entry, overwrite):
    relative = name.removeprefix("data/")
    raw = target.root / "data" / relative
    if any(path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())
           for path in (raw, *raw.parents) if path != target.root and target.root in path.parents):
        raise SnapshotStorageError("Cannot export through a symbolic link or junction")
    path = target.path(f"data/{relative}")
    if path.exists() and not overwrite and sha256_file(path) != entry["sha256"]:
        raise SnapshotStorageError("Local data differs; choose an empty destination or explicitly overwrite")
    return path


def restore_git_archive(client, bucket, record, destination_root, overwrite=False):
    prefix = record["archive_prefix"]
    content, _ = read_object(client, bucket, f"{prefix}/manifest.json")
    if hashlib.sha256(content).hexdigest() != record["archive_id"]:
        raise SnapshotStorageError("Git archive manifest hash mismatch")
    manifest = json.loads(content)
    if manifest.get("kind") != "git-data-archive" or manifest.get("market") != "IN":
        raise SnapshotStorageError("Unsupported Git data archive")
    target = LocalSnapshotStorage(Path(destination_root))
    verified = []
    for name, entry in manifest["files"].items():
        if not name.startswith(("data/market_data/", "data/stock_universe/")):
            raise SnapshotStorageError("Unexpected archive dataset path")
        path = _export_path(target, name, entry, overwrite)
        payload, _ = read_object(client, bucket, f"{prefix}/files/{name}")
        if len(payload) != entry["size_bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
            raise SnapshotStorageError("Git archive data verification failed")
        verified.append((name, path, payload))
    for name, path, payload in sorted(verified, key=lambda item: item[0].endswith("/manifest.json")):
        atomic_write(path, payload)
    return {"archive_id": record["archive_id"], "restored_files": len(verified), "destination": str(target.root)}


def export_cloud_snapshot(storage, destination_root, overwrite=False):
    """Export a complete pinned snapshot, including per-symbol chart files."""
    target = LocalSnapshotStorage(market_data_root(Path(destination_root), storage.market), storage.market)
    targets = []
    for name, entry in storage.catalog["files"].items():
        relative = name.removeprefix("data/")
        path = _export_path(target, name, entry, overwrite)
        targets.append((name, path, relative.endswith("/manifest.json")))
    storage.verify_files()
    # Source bytes are verified first; manifests become visible only after data.
    for name, path, _ in sorted(targets, key=lambda item: item[2]):
        atomic_write(path, storage.path(name).read_bytes())
    return {"snapshot_id": storage.snapshot_id, "market": storage.market,
            "files": len(targets), "destination": str(target.root)}
