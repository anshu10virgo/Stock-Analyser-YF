"""Conditional S3 writes serialize publication, restore, and retention."""

import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from stock_analyser.infrastructure.r2.storage import SnapshotStorageError, safe_relative_path


class StorageLease:
    """A renewable one-hour lease; stale owners cannot activate or delete."""

    def __init__(self, client, bucket, prefix, clock=None):
        self.client, self.bucket = client, bucket
        self.key = f"{safe_relative_path(prefix)}/maintenance/lease.json"
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.owner = uuid4().hex

    def _read(self):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.key)
        except Exception as error:
            if getattr(error, "response", {}).get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                return None, None
            raise SnapshotStorageError("Cannot inspect cloud maintenance lease") from None
        try:
            return json.loads(response["Body"].read()), response["ETag"]
        finally:
            response["Body"].close()

    def _write(self, expires, etag):
        condition = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
        try:
            self.client.put_object(Bucket=self.bucket, Key=self.key,
                Body=json.dumps({"owner": self.owner, "expires_at": expires.isoformat()}).encode(),
                ContentType="application/json", **condition)
        except Exception:
            raise SnapshotStorageError("Cloud maintenance lease changed; retry later") from None

    def __enter__(self):
        previous, etag = self._read()
        if previous and datetime.fromisoformat(previous["expires_at"]) > self.clock():
            raise SnapshotStorageError("Another publisher or cleanup holds the cloud maintenance lease")
        self._write(self.clock() + timedelta(hours=1), etag)
        self.renew()
        return self

    def renew(self):
        current, etag = self._read()
        if (not current or current["owner"] != self.owner
                or datetime.fromisoformat(current["expires_at"]) <= self.clock()):
            raise SnapshotStorageError("Cloud maintenance lease expired or changed")
        self._write(self.clock() + timedelta(hours=1), etag)

    def __exit__(self, error_type, error, traceback):
        current, etag = self._read()
        if current and current["owner"] == self.owner:
            self._write(self.clock(), etag)
