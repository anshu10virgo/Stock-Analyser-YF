"""Prepare and publish content-addressed snapshots without replacing live files."""

from __future__ import annotations

import base64
import hashlib
import json
import re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from urllib.parse import quote
from tempfile import TemporaryDirectory

import pandas as pd

from services.snapshot_storage import (
    CloudSnapshotStorage, LocalSnapshotStorage, SnapshotStorageError, atomic_write, sha256_file,
    validate_catalog, dataset_object_key, TRANSFER_WORKERS,
)
from stock_analyser.domain.markets import market_data_root, market_definition
from services.storage_lease import StorageLease


def json_bytes(value: dict) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def _references(manifest: dict):
    for name, entry in manifest.items():
        if isinstance(entry, dict) and "path" in entry:
            yield entry
        elif name == "price_files":
            yield from entry
    for name in ("active_universe", "source_snapshot", "refresh_report"):
        if manifest.get(name):
            yield {"path": manifest[name], **(
                {"sha256": manifest["sha256"]}
                if name == "active_universe" and manifest.get("sha256") else {}
            )}


def prepare_snapshot(project_root: Path, output: Path, market="IN") -> tuple[str, dict]:
    """Copy only manifest-referenced data, validating source hashes first.

    Annual partitions support bulk scans; extra per-symbol files keep charts
    and small Backtests from downloading the entire price dataset.
    """
    definition = market_definition(market)
    source = LocalSnapshotStorage(market_data_root(project_root, market), market)
    files = {}

    def add_file(logical: str, path: Path, expected_hash=None):
        logical = logical.removeprefix("data/")
        content = path.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        # Windows Git checkouts can convert LF text files to CRLF. Accept only
        # normalization that reproduces the manifest's exact expected hash.
        if expected_hash and digest != expected_hash and path.suffix in {".csv", ".json"}:
            normalized = content.replace(b"\r\n", b"\n")
            if hashlib.sha256(normalized).hexdigest() == expected_hash:
                content = normalized
                digest = expected_hash
        if expected_hash and digest != expected_hash:
            raise SnapshotStorageError(f"Source hash mismatch: {logical}")
        key = dataset_object_key(logical, digest)
        target = output / key
        if not target.is_file() or sha256_file(target) != digest:
            atomic_write(target, content)
        entry = {"key": key, "sha256": digest,
                 "size_bytes": len(content)}
        files[logical] = entry
        return {"path": logical, "sha256": digest}

    def add_frame(prefix, folder, symbol, frame):
        # Hash symbols instead of treating exchange tickers as filesystem paths.
        name = hashlib.sha256(str(symbol).encode()).hexdigest()
        relative = f"{folder}/{quote(str(symbol), safe='.-_')}.parquet"
        temporary = output / "staging" / f"{folder}-{name}.parquet"
        temporary.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(temporary, index=False)
        entry = add_file(f"{prefix}/{relative}", temporary)
        temporary.unlink()
        return {**entry, "path": relative}

    valuation_prefix = f"data/market_data/{definition.fundamentals_directory}"
    datasets = ("data/stock_universe", "data/market_data", valuation_prefix)
    manifests = {prefix: source.read_json(f"{prefix}/manifest.json") for prefix in datasets}
    for prefix, manifest in manifests.items():
        if manifest.get("market", "IN") != market:
            raise SnapshotStorageError("Source manifest belongs to a different market")
        manifest["market"] = market
        manifest["currency"] = definition.currency
        for entry in _references(manifest):
            logical = f"{prefix}/{entry['path']}"
            add_file(logical, source.path(logical), entry.get("sha256"))
    market_manifest = manifests["data/market_data"]
    universe = manifests["data/stock_universe"]
    if market_manifest.get("universe_sha256") != universe.get("sha256"):
        raise SnapshotStorageError("Market data and universe snapshots do not match")
    frames = []
    for entry in market_manifest["price_files"]:
        logical = f"data/market_data/{entry['path']}"
        copied_path = output / files[logical.removeprefix("data/")]["key"]
        frames.append(pd.read_parquet(copied_path)
                      if entry["path"].endswith(".parquet") else pd.read_csv(copied_path))
    prices = pd.concat(frames, ignore_index=True)
    required = {"Date", "Symbol", "Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(prices.columns) or prices.empty:
        raise SnapshotStorageError("Invalid source price schema")
    market_manifest["symbol_price_files"] = {
        str(symbol): add_frame("data/market_data", "symbol_prices", symbol, frame)
        for symbol, frame in prices.groupby("Symbol", sort=True)
    }
    del frames, prices
    screener = manifests[valuation_prefix]
    history_logical = f"{valuation_prefix}/{screener['history_file']['path']}".removeprefix("data/")
    history_path = output / files[history_logical]["key"]
    history = pd.read_parquet(history_path)
    if not {"symbol", "date", "pe", "ttm_eps"}.issubset(history.columns):
        raise SnapshotStorageError("Invalid source valuation schema")
    screener["symbol_history_files"] = {
        str(symbol): add_frame(valuation_prefix, "symbol_history", symbol, frame)
        for symbol, frame in history.groupby("symbol", sort=True)
    }
    for prefix, manifest in manifests.items():
        path = output / "staging" / (prefix.replace("/", "-") + ".json")
        atomic_write(path, json_bytes(manifest))
        add_file(f"{prefix}/manifest.json", path)
        path.unlink()
    catalog = {"schema_version": 2, "market": market, "currency": definition.currency, "files": files,
               "last_trading_date": market_manifest.get("last_trading_date")}
    validate_catalog(catalog)
    content = json_bytes(catalog)
    snapshot_id = hashlib.sha256(content).hexdigest()
    atomic_write(output / "snapshots" / f"{snapshot_id}.json", content)
    return snapshot_id, catalog


def _error_code(error):
    return getattr(error, "response", {}).get("Error", {}).get("Code", "")


class SnapshotPublisher:
    """Publish only after every referenced object is validated remotely."""

    def __init__(self, client, bucket, prefix="markets/IN", market="IN"):
        from services.snapshot_storage import safe_relative_path

        self.client = client
        market_definition(market)
        self.market = market
        self.bucket = bucket
        self.prefix = safe_relative_path(prefix.strip("/"))
        self.metrics = {"uploaded_bytes": 0, "uploaded_objects": 0, "reused_objects": 0}
        self._metrics_lock = Lock()

    def _key(self, key):
        return f"{self.prefix}/{key}"

    def current(self):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key("current.json"))
        except Exception as error:
            if _error_code(error) in {"NoSuchKey", "404"}:
                return None, None
            raise SnapshotStorageError("Cannot read current cloud snapshot") from None
        try:
            return json.loads(response["Body"].read()), response["ETag"]
        finally:
            response["Body"].close()

    def _put_immutable(self, key, content, digest):
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=self._key(key), Body=content,
                IfNoneMatch="*", Metadata={"sha256": digest},
                ContentMD5=base64.b64encode(hashlib.md5(content).digest()).decode(),
            )
            with self._metrics_lock:
                self.metrics["uploaded_bytes"] += len(content)
                self.metrics["uploaded_objects"] += 1
        except Exception as error:
            if _error_code(error) not in {"PreconditionFailed", "412"}:
                raise SnapshotStorageError("Cloud snapshot upload failed") from None
            with self._metrics_lock:
                self.metrics["reused_objects"] += 1
        metadata = self.client.head_object(Bucket=self.bucket, Key=self._key(key))
        if (metadata["ContentLength"] != len(content)
                or metadata.get("Metadata", {}).get("sha256") != digest):
            raise SnapshotStorageError("Uploaded object validation failed")

    def activate(self, snapshot_id, expected_etag):
        with StorageLease(self.client, self.bucket, self.prefix) as lease, TemporaryDirectory() as temporary:
            # A rollback target could have been pruned since an earlier check.
            # Recheck remote bytes while retention is excluded by the lease.
            candidate = CloudSnapshotStorage(self.client, self.bucket, self.prefix,
                                            Path(temporary), snapshot_id, self.market)
            candidate.verify_files(lambda completed, total: lease.renew() if completed % 250 == 0 else None)
            lease.renew()
            self._activate(snapshot_id, expected_etag)

    def _activate(self, snapshot_id, expected_etag):
        condition = {"IfMatch": expected_etag} if expected_etag else {"IfNoneMatch": "*"}
        try:
            self.client.put_object(
                Bucket=self.bucket, Key=self._key("current.json"),
                Body=json_bytes({"schema_version": 1, "snapshot_id": snapshot_id}),
                ContentType="application/json", **condition,
            )
        except Exception as error:
            if _error_code(error) in {"PreconditionFailed", "412", "ConditionalRequestConflict", "409"}:
                raise SnapshotStorageError("Another publisher changed the active snapshot; retry from fresh data") from None
            raise SnapshotStorageError("Snapshot activation failed; previous snapshot retained") from None

    def _publish_file(self, prepared, entry, copy_source=None):
        path = prepared / entry["key"]
        if sha256_file(path) != entry["sha256"] or path.stat().st_size != entry["size_bytes"]:
            raise SnapshotStorageError("Prepared file hash mismatch")
        try:
            remote = self.client.head_object(Bucket=self.bucket, Key=self._key(entry["key"]))
        except Exception as error:
            if _error_code(error) not in {"NoSuchKey", "404", "NotFound"}:
                raise SnapshotStorageError("Cannot inspect cloud snapshot object") from None
            source_key = copy_source.get(entry["sha256"]) if copy_source else None
            if source_key:
                source = self.client.head_object(Bucket=self.bucket, Key=source_key)
                if (source["ContentLength"] != entry["size_bytes"]
                        or source.get("Metadata", {}).get("sha256") != entry["sha256"]):
                    raise SnapshotStorageError("Copy source failed validation")
                self.client.copy_object(
                    Bucket=self.bucket, Key=self._key(entry["key"]),
                    CopySource={"Bucket": self.bucket, "Key": source_key},
                    CopySourceIfMatch=source["ETag"], MetadataDirective="COPY",
                )
                copied = self.client.head_object(Bucket=self.bucket, Key=self._key(entry["key"]))
                if (copied["ContentLength"] != entry["size_bytes"]
                        or copied.get("Metadata", {}).get("sha256") != entry["sha256"]):
                    raise SnapshotStorageError("Copied object failed validation")
                with self._metrics_lock:
                    self.metrics["copied_objects"] = self.metrics.get("copied_objects", 0) + 1
            else:
                self._put_immutable(entry["key"], path.read_bytes(), entry["sha256"])
        else:
            if (remote["ContentLength"] != entry["size_bytes"]
                    or remote.get("Metadata", {}).get("sha256") != entry["sha256"]):
                raise SnapshotStorageError("Existing cloud object failed validation")
            with self._metrics_lock:
                self.metrics["reused_objects"] += 1

    def publish(self, prepared: Path, snapshot_id: str, progress=None, copy_source=None,
                expected_snapshot_id=None):
        with StorageLease(self.client, self.bucket, self.prefix) as lease:
            return self._publish(prepared, snapshot_id, progress, copy_source,
                                 expected_snapshot_id, lease)

    def _publish(self, prepared, snapshot_id, progress, copy_source, expected_snapshot_id, lease):
        if not re.fullmatch(r"[0-9a-f]{64}", snapshot_id):
            raise SnapshotStorageError("Invalid prepared snapshot ID")
        current, expected_etag = self.current()
        if expected_snapshot_id is not None and (current or {}).get("snapshot_id") != expected_snapshot_id:
            raise SnapshotStorageError("Active snapshot changed during refresh; publication stopped")
        content = (prepared / "snapshots" / f"{snapshot_id}.json").read_bytes()
        if hashlib.sha256(content).hexdigest() != snapshot_id:
            raise SnapshotStorageError("Prepared catalog hash mismatch")
        catalog = json.loads(content)
        validate_catalog(catalog)
        if catalog.get("market") != self.market:
            raise SnapshotStorageError("Prepared snapshot belongs to a different market")
        entries = list({e["key"]: e for e in catalog["files"].values()}.values())
        # Bound network concurrency; only the main thread can activate a catalog.
        with ThreadPoolExecutor(max_workers=TRANSFER_WORKERS) as executor:
            futures = [executor.submit(self._publish_file, prepared, entry, copy_source) for entry in entries]
            try:
                for completed, future in enumerate(futures, 1):
                    future.result()
                    if completed % 250 == 0:
                        lease.renew()
                    if progress:
                        progress(completed, len(entries))
            except Exception:
                for future in futures:
                    future.cancel()
                raise
        self._put_immutable(f"snapshots/{snapshot_id}.json", content, snapshot_id)
        # Read the uploaded candidate before making it visible to new sessions.
        # Hash metadata alone cannot prove the bytes served by storage are valid.
        candidate = CloudSnapshotStorage(self.client, self.bucket, self.prefix,
                                        prepared / "verified", snapshot_id, self.market)
        def verification_progress(completed, total):
            if completed % 250 == 0:
                lease.renew()
            if progress:
                progress(completed, total)

        candidate.verify_files(verification_progress)
        lease.renew()
        self._activate(snapshot_id, expected_etag)
        return self.metrics.copy()


def retire_legacy_snapshot(client, bucket, destination, old_snapshot_id):
    """Remove only the known initial ticksy namespace after verified cutover.

    Refuse unknown objects or changed data instead of recursively deleting a
    bucket or a prefix supplied by the caller.
    """
    from services.snapshot_storage import CloudSnapshotStorage

    if destination.prefix != f"markets/{destination.market}" or destination.catalog["schema_version"] != 2:
        raise SnapshotStorageError("Destination must use the verified root layout")
    destination.verify_files()
    old_prefix = f"ticksy/markets/{destination.market}"
    current, _ = SnapshotPublisher(client, bucket, old_prefix, destination.market).current()
    if not current or current.get("snapshot_id") != old_snapshot_id:
        raise SnapshotStorageError("Legacy snapshot changed; retirement stopped")
    old = CloudSnapshotStorage(client, bucket, old_prefix,
        destination.root / "legacy-retirement", old_snapshot_id, destination.market)
    new_hashes = {entry["sha256"] for entry in destination.catalog["files"].values()}
    for name, entry in old.catalog["files"].items():
        if not name.endswith("/manifest.json") and entry["sha256"] not in new_hashes:
            raise SnapshotStorageError("Legacy data is missing from the destination")
    expected = {f"{old_prefix}/{entry['key']}" for entry in old.catalog["files"].values()}
    expected.update({f"{old_prefix}/current.json", f"{old_prefix}/snapshots/{old_snapshot_id}.json"})
    existing = set()
    arguments = {"Bucket": bucket, "Prefix": f"{old_prefix}/"}
    while True:
        page = client.list_objects_v2(**arguments)
        existing.update(entry["Key"] for entry in page.get("Contents", []))
        if not page.get("IsTruncated"):
            break
        arguments["ContinuationToken"] = page["NextContinuationToken"]
    if existing != expected:
        raise SnapshotStorageError("Legacy prefix has unexpected or missing files; nothing deleted")
    # Every target is an exact key selected from the verified legacy catalog.
    keys = [f"{old_prefix}/current.json"] + sorted(expected - {f"{old_prefix}/current.json"})
    for start in range(0, len(keys), 1000):
        response = client.delete_objects(Bucket=bucket,
            Delete={"Objects": [{"Key": key} for key in keys[start:start + 1000]]})
        if response.get("Errors"):
            raise SnapshotStorageError("Legacy retirement was incomplete; destination remains active")
    return len(keys)
