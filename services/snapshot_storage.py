"""Validated local files and pinned, cached S3-compatible snapshots.

Cloud access belongs to application data loading, never to Ticksy tools.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

TRANSFER_WORKERS = 16
# Different catalog entries and app sessions can share the same cached bytes.
# Bounded lock buckets prevent concurrent Windows reads/replaces of that file.
_CACHE_FILE_LOCKS = [Lock() for _ in range(128)]


def _cache_file_lock(path):
    # Resolving an existing Windows file can differ from resolving its missing
    # parent during the first write. Keep the lock identity independent of I/O.
    identity = os.path.normcase(os.path.abspath(path))
    return _CACHE_FILE_LOCKS[hash(identity) % len(_CACHE_FILE_LOCKS)]


class SnapshotStorageError(RuntimeError):
    """A snapshot cannot be read or verified safely."""


def safe_relative_path(value: str) -> str:
    path = PurePosixPath(value)
    if (not value or "\\" in value or ":" in value or path.is_absolute()
            or any(part in {".", ".."} for part in value.split("/"))):
        raise SnapshotStorageError("Invalid snapshot path")
    return path.as_posix()


def dataset_object_key(name: str, digest: str) -> str:
    """Keep the dataset folder and filename while making versions immutable."""
    path = PurePosixPath(safe_relative_path(name))
    return str(path.with_name(f"{path.stem}--{digest}{path.suffix}"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        stream.write(content)
    try:
        for attempt in range(6):
            try:
                temporary.replace(path)
                break
            except PermissionError:
                # Windows scanners can briefly hold a newly closed cache file.
                if attempt == 5:
                    raise
                time.sleep(0.02 * 2 ** attempt)
    finally:
        temporary.unlink(missing_ok=True)


class LocalSnapshotStorage:
    """Resolve files inside one local root."""

    cloud = False

    def __init__(self, root: Path, market="IN"):
        self.root = Path(root).resolve()
        self.market = market

    def path(self, relative: str) -> Path:
        path = (self.root / safe_relative_path(relative)).resolve()
        if self.root not in path.parents:
            raise SnapshotStorageError("Snapshot path escapes its root")
        return path

    def read_json(self, relative: str) -> dict:
        return json.loads(self.path(relative).read_text(encoding="utf-8"))


def validate_catalog(catalog: dict) -> None:
    if catalog.get("schema_version") not in {1, 2} or not isinstance(catalog.get("files"), dict):
        raise SnapshotStorageError("Unsupported snapshot catalog")
    if catalog.get("market") not in {"IN", "US"}:
        raise SnapshotStorageError("Snapshot catalog must identify IN or US")
    for name, entry in catalog["files"].items():
        safe_relative_path(name)
        digest = entry.get("sha256", "")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SnapshotStorageError("Invalid snapshot hash")
        expected_key = (f"objects/{digest}" if catalog["schema_version"] == 1
                        else dataset_object_key(name, digest))
        if entry.get("key") != expected_key:
            raise SnapshotStorageError("Invalid snapshot object key")
        if not isinstance(entry.get("size_bytes"), int) or entry["size_bytes"] < 0:
            raise SnapshotStorageError("Invalid snapshot size")


class CloudSnapshotStorage:
    """Pin one catalog and lazily download immutable, hash-checked objects."""

    cloud = True

    def __init__(self, client, bucket: str, prefix: str, cache_root: Path,
                 snapshot_id: str = "", market="IN"):
        from models.market import market_definition

        market_definition(market)
        self.client = client
        self.bucket = bucket
        self.market = market
        self.prefix = safe_relative_path(prefix.strip("/"))
        self.root = Path(cache_root)
        self._metrics_lock = Lock()
        self.metrics = {"get_requests": 0, "downloaded_bytes": 0, "cache_hits": 0}
        if snapshot_id:
            self.snapshot_id = safe_relative_path(snapshot_id)
        else:
            pointer = json.loads(self._get("current.json"))
            self.snapshot_id = pointer["snapshot_id"]
        if not re.fullmatch(r"[0-9a-f]{64}", self.snapshot_id):
            raise SnapshotStorageError("Invalid snapshot ID")
        catalog_file = self.root / "catalogs" / f"{self.snapshot_id}.json"
        with _cache_file_lock(catalog_file):
            content = catalog_file.read_bytes() if catalog_file.is_file() else None
            if content is None or hashlib.sha256(content).hexdigest() != self.snapshot_id:
                content = self._get(f"snapshots/{self.snapshot_id}.json")
                if hashlib.sha256(content).hexdigest() != self.snapshot_id:
                    raise SnapshotStorageError("Snapshot catalog hash mismatch")
                atomic_write(catalog_file, content)
        self.catalog = json.loads(content)
        validate_catalog(self.catalog)
        if self.catalog.get("market") != market:
            raise SnapshotStorageError("Snapshot belongs to a different market")

    def _get(self, key: str) -> bytes:
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=f"{self.prefix}/{key}")
            try:
                content = response["Body"].read()
            finally:
                response["Body"].close()
        except Exception:
            raise SnapshotStorageError("Cloud snapshot read failed; check storage access") from None
        with self._metrics_lock:
            self.metrics["get_requests"] += 1
            self.metrics["downloaded_bytes"] += len(content)
        return content

    def path(self, relative: str) -> Path:
        relative = safe_relative_path(relative)
        if self.catalog["schema_version"] == 2:
            relative = relative.removeprefix("data/")
        entry = self.catalog["files"].get(relative)
        if entry is None:
            raise SnapshotStorageError("File is absent from the pinned snapshot")
        # Preserve extensions for pandas readers without trusting remote paths.
        path = self.root / "objects" / (entry["sha256"] + Path(relative).suffix)
        with _cache_file_lock(path):
            return self._verified_file(path, entry)

    def _verified_file(self, path, entry):
        if (path.is_file() and path.stat().st_size == entry["size_bytes"]
                and sha256_file(path) == entry["sha256"]):
            with self._metrics_lock:
                self.metrics["cache_hits"] += 1
            return path
        content = self._get(entry["key"])
        if (len(content) != entry["size_bytes"]
                or hashlib.sha256(content).hexdigest() != entry["sha256"]):
            raise SnapshotStorageError("Cloud snapshot file failed integrity validation")
        atomic_write(path, content)
        return path

    def read_json(self, relative: str) -> dict:
        return json.loads(self.path(relative).read_text(encoding="utf-8"))

    def verify_files(self, progress=None):
        """Read and hash every object, with bounded network concurrency."""
        names = list(self.catalog["files"])
        with ThreadPoolExecutor(max_workers=TRANSFER_WORKERS) as executor:
            futures = [executor.submit(self.path, name) for name in names]
            try:
                for completed, future in enumerate(futures, 1):
                    future.result()
                    if progress:
                        progress(completed, len(names))
            except Exception:
                for future in futures:
                    future.cancel()
                raise


class ScopedSnapshotStorage:
    """Expose a dataset directory through the same file interface."""

    def __init__(self, storage, prefix: str):
        self.storage = storage
        self.prefix = safe_relative_path(prefix)
        self.cloud = storage.cloud
        self.market = storage.market

    def path(self, relative: str) -> Path:
        return self.storage.path(f"{self.prefix}/{safe_relative_path(relative)}")

    def read_json(self, relative: str) -> dict:
        return self.storage.read_json(f"{self.prefix}/{safe_relative_path(relative)}")
