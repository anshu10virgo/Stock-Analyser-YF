"""Offline cleanup of regenerable cache files within one verified cache root."""

import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from stock_analyser.infrastructure.r2.housekeeping import fingerprint
from stock_analyser.infrastructure.r2.storage import SnapshotStorageError


def _linked(path):
    return path.is_symlink() or bool(getattr(path, "is_junction", lambda: False)())


def cache_cleanup_plan(project_root, reader_cache, catalog, policy, now=None):
    now = now or datetime.now(timezone.utc)
    expected = Path(project_root).resolve() / ".snapshot-cache"
    if _linked(expected) or expected.resolve() != expected:
        raise SnapshotStorageError("Cache root must not be a link or junction")
    reader_cache = Path(reader_cache).absolute()
    if not reader_cache.is_relative_to(expected) or reader_cache.resolve() != reader_cache:
        raise SnapshotStorageError("Reader cache escapes the project cache")
    days = int(policy["cache_max_age_days"])
    if days < 1:
        raise ValueError("Cache cleanup requires at least a one-day grace period")
    cutoff = (now - timedelta(days=days)).timestamp()
    protected = {entry["sha256"] + Path(name).suffix
                 for name, entry in catalog["files"].items()}
    # All locally cached catalogs remain small and preserve audit/pin information.
    # Only obsolete reader objects and expired isolated run files are evicted.
    stages = {"daily-refresh", "market-refresh", "screener-refresh", "universe-refresh"}
    files, candidates, skipped_links = [], [], []
    if expected.exists():
        for directory, directories, names in os.walk(expected, followlinks=False):
            parent = Path(directory)
            for name in list(directories):
                if _linked(parent / name):
                    skipped_links.append(str((parent / name).relative_to(expected)))
                    directories.remove(name)
            for name in names:
                path = parent / name
                if _linked(path) or not path.resolve().is_relative_to(expected):
                    skipped_links.append(str(path.relative_to(expected)))
                    continue
                stat = path.stat()
                relative = path.relative_to(expected)
                item = {"path": relative.as_posix(), "size_bytes": stat.st_size,
                        "modified_ns": stat.st_mtime_ns}
                files.append(item)
                reader_object = (parent == reader_cache / "objects" and
                                 re.fullmatch(r"[a-f0-9]{64}(?:\.[^/]+)?", name)
                                 and name not in protected)
                staged_file = (len(relative.parts) >= 4 and relative.parts[0] in stages
                               and relative.parts[1] in {"IN", "US"}
                               and re.fullmatch(r"\d{8}T\d{12}Z", relative.parts[2])
                               and name not in {"refresh_report.json", "failed_refresh_report.json"})
                if stat.st_mtime <= cutoff and (reader_object or staged_file):
                    candidates.append(item)
    candidates.sort(key=lambda item: item["path"])
    total = sum(item["size_bytes"] for item in files)
    return {"plan_id": fingerprint({"root": str(expected), "reader_cache": str(reader_cache),
                "candidates": candidates, "protected": sorted(protected)}),
            "root": str(expected), "file_count": len(files), "stored_bytes": total,
            "cache_budget_bytes": int(policy["cache_budget_bytes"]),
            "usage_warning": total > int(policy["cache_budget_bytes"]),
            "reclaimable_bytes": sum(item["size_bytes"] for item in candidates),
            "skipped_links": skipped_links, "delete_candidates": candidates}


def apply_cache_cleanup(project_root, reader_cache, catalog, policy, expected_plan_id, offline=False, now=None):
    if not offline:
        raise SnapshotStorageError("Stop apps and maintenance processes, then use the explicit offline option")
    plan = cache_cleanup_plan(project_root, reader_cache, catalog, policy, now)
    if plan["plan_id"] != expected_plan_id:
        raise SnapshotStorageError("Cache plan changed; review a fresh dry run")
    root = Path(plan["root"])
    for item in plan["delete_candidates"]:
        path = root / item["path"]
        # Recheck the exact resolved target and file state immediately before unlink.
        if _linked(path) or not path.resolve().is_relative_to(root):
            raise SnapshotStorageError("Cache target changed or escaped the cache root")
        stat = path.stat()
        if stat.st_size != item["size_bytes"] or stat.st_mtime_ns != item["modified_ns"]:
            raise SnapshotStorageError("Cache file changed during cleanup")
        path.unlink()
    return {"deleted_files": len(plan["delete_candidates"]), "deleted_bytes": plan["reclaimable_bytes"]}
