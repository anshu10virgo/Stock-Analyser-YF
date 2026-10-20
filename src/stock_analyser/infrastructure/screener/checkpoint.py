"""Persist complete Screener batches independently of the active market snapshot."""

import hashlib
import json
import re

from stock_analyser.infrastructure.r2.storage import (
    SnapshotStorageError,
    atomic_write,
    safe_relative_path,
)


class ScreenerCheckpointStore:
    """Hash-verified batch files plus a conditionally replaced checkpoint index."""

    def __init__(self, client, bucket, market_prefix, identity):
        self.client, self.bucket = client, bucket
        self.identity = identity
        self.prefix = f"{safe_relative_path(market_prefix)}/maintenance/screener/{identity}"
        self.key = f"{self.prefix}/checkpoint.json"
        self.etag = None
        self.entries = {}

    def _read(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        try:
            return response["Body"].read(), response["ETag"]
        finally:
            response["Body"].close()

    @staticmethod
    def _valid_name(name):
        return bool(re.fullmatch(r"batches/\d{6}_(?:summary\.csv|history\.parquet|failures\.csv)", name))

    def restore(self, staging):
        """Validate the entire checkpoint before making it visible locally."""
        if staging.is_symlink() or (staging / "batches").is_symlink():
            raise SnapshotStorageError("Cannot restore checkpoint through a symbolic link")
        try:
            content, self.etag = self._read(self.key)
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return False
            raise SnapshotStorageError("Cannot read durable Screener checkpoint") from None
        index = json.loads(content)
        if index.get("schema_version") != 1:
            raise SnapshotStorageError("Unsupported Screener checkpoint schema")
        verified = []
        for name, entry in index["files"].items():
            if not self._valid_name(name) or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"]):
                raise SnapshotStorageError("Unexpected Screener checkpoint path")
            payload, _ = self._read(f"{self.prefix}/objects/{entry['sha256']}")
            if len(payload) != entry["size_bytes"] or hashlib.sha256(payload).hexdigest() != entry["sha256"]:
                raise SnapshotStorageError("Screener checkpoint hash mismatch")
            verified.append((staging / name, payload))
        # An interrupted local upload can leave batches beyond the durable index.
        # They must not be counted as committed progress on the next attempt.
        for path in (staging / "batches").glob("*"):
            name = path.relative_to(staging).as_posix()
            if not self._valid_name(name) or path.is_symlink():
                raise SnapshotStorageError("Unexpected local Screener checkpoint file")
            if name not in index["files"]:
                path.unlink()
        for path, payload in verified:
            atomic_write(path, payload)
        atomic_write(staging / "checkpoint.json", json.dumps(index["checkpoint"]).encode())
        self.entries = index["files"]
        return True

    def save(self, staging):
        """Upload batch data first; atomically advance progress only after verification."""
        entries = {}
        if staging.is_symlink() or (staging / "batches").is_symlink():
            raise SnapshotStorageError("Cannot save checkpoint through a symbolic link")
        for path in sorted((staging / "batches").glob("*")):
            name = path.relative_to(staging).as_posix()
            if not self._valid_name(name) or path.is_symlink():
                raise SnapshotStorageError("Unexpected Screener staging file")
            payload = path.read_bytes()
            digest = hashlib.sha256(payload).hexdigest()
            entry = {"sha256": digest, "size_bytes": len(payload)}
            if self.entries.get(name) != entry:
                key = f"{self.prefix}/objects/{digest}"
                try:
                    self.client.put_object(Bucket=self.bucket, Key=key, Body=payload,
                                           IfNoneMatch="*", Metadata={"sha256": digest})
                except Exception as error:
                    if getattr(error, "response", {}).get("Error", {}).get("Code") not in {
                        "PreconditionFailed", "412", "ConditionalRequestConflict"}:
                        raise SnapshotStorageError("Cannot upload Screener checkpoint batch") from None
                remote, _ = self._read(key)
                if remote != payload:
                    raise SnapshotStorageError("Screener checkpoint upload verification failed")
            entries[name] = entry
        checkpoint = json.loads((staging / "checkpoint.json").read_text(encoding="utf-8"))
        content = json.dumps({"schema_version": 1, "checkpoint": checkpoint, "files": entries},
                             sort_keys=True).encode()
        condition = {"IfMatch": self.etag} if self.etag else {"IfNoneMatch": "*"}
        try:
            self.client.put_object(Bucket=self.bucket, Key=self.key, Body=content,
                                   ContentType="application/json", **condition)
        except Exception:
            raise SnapshotStorageError("Screener checkpoint changed; restart from its durable version") from None
        remote, self.etag = self._read(self.key)
        if remote != content:
            raise SnapshotStorageError("Screener checkpoint index verification failed")
        self.entries = entries


def checkpoint_identity(symbols, manifest_bytes):
    """Reuse progress only for the same ordered universe and source Screener version."""
    return hashlib.sha256("\n".join(symbols).encode() + b"\0" + manifest_bytes).hexdigest()
