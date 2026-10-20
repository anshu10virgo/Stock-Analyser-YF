"""Reference-aware retention and payload usage; every mutation starts with a plan."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from stock_analyser.infrastructure.r2.lease import StorageLease
from stock_analyser.infrastructure.r2.storage import (
    SnapshotStorageError,
    safe_relative_path,
    validate_catalog,
)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def list_objects(client, bucket, prefix):
    objects = {}
    arguments = {"Bucket": bucket, "Prefix": prefix + "/"}
    while True:
        response = client.list_objects_v2(**arguments)
        for item in response.get("Contents", []):
            if not item["Key"].startswith(prefix + "/"):
                raise SnapshotStorageError("Cloud inventory escaped the selected market")
            objects[item["Key"]] = item
        if not response.get("IsTruncated"):
            return objects
        arguments["ContinuationToken"] = response["NextContinuationToken"]


def read_object(client, bucket, key):
    response = client.get_object(Bucket=bucket, Key=key)
    try:
        return response["Body"].read(), response["ETag"]
    finally:
        response["Body"].close()


def _managed_data_key(relative):
    return bool(re.fullmatch(r"objects/[a-f0-9]{64}", relative) or re.fullmatch(
        r"(?:stock_universe|market_data)/.+--[a-f0-9]{64}(?:\.[^/]+)?", relative))


def retention_plan(client, bucket, prefix, policy, now=None, protected_ids=()):
    """Keep newest catalogs, monthly checkpoints, pins, and recent uploads."""
    now = now or datetime.now(timezone.utc)
    prefix = safe_relative_path(prefix)
    keep_latest, keep_monthly, grace = (int(policy[key]) for key in
                                       ("keep_latest", "keep_monthly", "grace_days"))
    if keep_latest < 1 or keep_monthly < 0 or grace < 1:
        raise ValueError("Retention needs at least one snapshot and a one-day upload grace period")
    objects = list_objects(client, bucket, prefix)
    pointer_bytes, pointer_etag = read_object(client, bucket, f"{prefix}/current.json")
    current = json.loads(pointer_bytes)["snapshot_id"]
    catalogs = {}
    for key, item in objects.items():
        match = re.fullmatch(re.escape(prefix) + r"/snapshots/([a-f0-9]{64})\.json", key)
        if not match:
            continue
        snapshot_id = match[1]
        content, _ = read_object(client, bucket, key)
        if hashlib.sha256(content).hexdigest() != snapshot_id:
            raise SnapshotStorageError("Catalog hash mismatch; retention stopped")
        catalog = json.loads(content)
        validate_catalog(catalog)
        if catalog["market"] != prefix.rsplit("/", 1)[-1]:
            raise SnapshotStorageError("Catalog belongs to another market")
        catalogs[snapshot_id] = {"key": key, "modified": item["LastModified"], "catalog": catalog}
    pins = set(policy.get("protected_snapshot_ids", ())) | set(protected_ids) | {current}
    if pins - catalogs.keys():
        raise SnapshotStorageError("A current or protected catalog is missing; retention stopped")
    ordered = sorted(catalogs, key=lambda sid: (catalogs[sid]["modified"], sid), reverse=True)
    retained = set(ordered[:keep_latest]) | pins
    months = set()
    cutoff = now - timedelta(days=grace)
    for sid in ordered:
        modified = catalogs[sid]["modified"]
        month = modified.strftime("%Y-%m")
        if month not in months and len(months) < keep_monthly:
            retained.add(sid)
            months.add(month)
        if modified > cutoff:
            retained.add(sid)
    referenced = {}
    known_keys = {f"{prefix}/{entry['key']}" for value in catalogs.values()
                  for entry in value["catalog"]["files"].values()}
    for sid in retained:
        for entry in catalogs[sid]["catalog"]["files"].values():
            key = f"{prefix}/{entry['key']}"
            if key not in objects or objects[key]["Size"] != entry["size_bytes"]:
                raise SnapshotStorageError("Retained snapshot has missing or inconsistent data; cleanup stopped")
            referenced[key] = entry["size_bytes"]
    expired_catalogs = {value["key"] for sid, value in catalogs.items() if sid not in retained}
    candidates, unknown = [], []
    for key, item in objects.items():
        relative = key[len(prefix) + 1:]
        safe_relative_path(relative)
        eligible = key in expired_catalogs or (_managed_data_key(relative) and key not in referenced)
        if eligible and key not in expired_catalogs and key not in known_keys and item["LastModified"] <= cutoff:
            # A filename alone does not establish ownership of an orphan.
            digest = re.search(r"(?:--|objects/)([a-f0-9]{64})(?:\.[^/]+)?$", relative)[1]
            metadata = client.head_object(Bucket=bucket, Key=key)
            if (metadata.get("Metadata", {}).get("sha256") != digest
                    or metadata["ContentLength"] != item["Size"]):
                unknown.append(key)
                continue
        if eligible and item["LastModified"] <= cutoff:
            candidates.append({"key": key, "size_bytes": item["Size"]})
        elif (not _managed_data_key(relative) and relative != "current.json"
              and not relative.startswith(("snapshots/", "maintenance/", "archives/git-data/"))):
            unknown.append(key)
    candidates.sort(key=lambda item: (item["key"] not in expired_catalogs, item["key"]))
    inventory = [(key, value["Size"], value.get("ETag", ""), value["LastModified"].isoformat())
                 for key, value in sorted(objects.items()) if not key.startswith(prefix + "/maintenance/")]
    total = sum(item["Size"] for item in objects.values())
    datasets = {}
    for key, item in objects.items():
        parts = key[len(prefix) + 1:].split("/")
        dataset = "/".join(parts[:2]) if parts[0] == "market_data" else parts[0]
        usage = datasets.setdefault(dataset, {"objects": 0, "bytes": 0})
        usage["objects"] += 1
        usage["bytes"] += item["Size"]
    budget = int(policy["storage_budget_bytes"])
    if budget <= 0 or not 0 < float(policy["warning_fraction"]) <= 1:
        raise ValueError("Invalid storage usage budget")
    return {"plan_id": fingerprint({"bucket": bucket, "prefix": prefix, "inventory": inventory,
                "pointer_etag": pointer_etag, "policy": policy, "pins": sorted(pins),
                "retained": sorted(retained), "delete": candidates}),
            "bucket": bucket, "prefix": prefix, "current_snapshot_id": current,
            "object_count": len(objects), "stored_bytes": total, "storage_budget_bytes": budget,
            "datasets": datasets,
            "budget_used_fraction": total / budget,
            "usage_warning": total >= budget * float(policy["warning_fraction"]),
            "catalog_count": len(catalogs), "retained_snapshot_ids": sorted(retained),
            "retired_snapshot_ids": sorted(set(catalogs) - retained),
            "referenced_bytes": sum(referenced.values()), "unknown_keys_preserved": unknown,
            "reclaimable_bytes": sum(item["size_bytes"] for item in candidates),
            "delete_candidates": candidates}


def apply_retention(client, bucket, prefix, policy, expected_plan_id, protected_ids=(), now=None):
    """Recompute under the same lease used by publishers; reject stale plans."""
    with StorageLease(client, bucket, prefix) as lease:
        plan = retention_plan(client, bucket, prefix, policy, now, protected_ids)
        if plan["plan_id"] != expected_plan_id:
            raise SnapshotStorageError("Cloud retention plan changed; review a fresh dry run")
        candidates = plan["delete_candidates"]
        for start in range(0, len(candidates), 1000):
            lease.renew()
            result = client.delete_objects(Bucket=bucket, Delete={"Objects": [
                {"Key": item["key"]} for item in candidates[start:start + 1000]]})
            if result.get("Errors"):
                raise SnapshotStorageError("Cloud deletion partially failed; inspect a new retention plan")
        return {"deleted_objects": len(candidates), "deleted_bytes": plan["reclaimable_bytes"]}
