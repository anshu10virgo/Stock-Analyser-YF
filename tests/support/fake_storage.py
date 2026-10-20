"""Deterministic in-memory object storage used by adapter tests."""

import hashlib
import io


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
        return {
            "ContentLength": len(self.objects[Key]),
            "Metadata": self.metadata[Key],
            "ETag": hashlib.md5(self.objects[Key]).hexdigest(),
        }

    def put_object(self, Bucket, Key, Body, IfNoneMatch=None, IfMatch=None, **kwargs):
        if self.fail_upload and "/snapshots/" not in Key and not Key.endswith(
            "current.json"
        ):
            raise FakeClientError("AccessDenied")
        current = self.objects.get(Key)
        if IfNoneMatch == "*" and current is not None:
            raise FakeClientError("PreconditionFailed")
        if IfMatch and (
            current is None or hashlib.md5(current).hexdigest() != IfMatch
        ):
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
        return {
            "Contents": [
                {"Key": key} for key in self.objects if key.startswith(Prefix)
            ],
            "IsTruncated": False,
        }

    def delete_objects(self, Bucket, Delete):
        for entry in Delete["Objects"]:
            self.objects.pop(entry["Key"], None)
            self.metadata.pop(entry["Key"], None)
        return {}
