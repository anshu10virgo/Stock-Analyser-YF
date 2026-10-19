"""Compatibility exports for snapshot-storage infrastructure adapters.

New code should import from ``stock_analyser.infrastructure.r2.storage``.
"""

from stock_analyser.infrastructure.r2.storage import (
    TRANSFER_WORKERS,
    CloudSnapshotStorage,
    LocalSnapshotStorage,
    ScopedSnapshotStorage,
    SnapshotStorageError,
    atomic_write,
    dataset_object_key,
    safe_relative_path,
    sha256_file,
    validate_catalog,
)

__all__ = [
    "TRANSFER_WORKERS",
    "CloudSnapshotStorage",
    "LocalSnapshotStorage",
    "ScopedSnapshotStorage",
    "SnapshotStorageError",
    "atomic_write",
    "dataset_object_key",
    "safe_relative_path",
    "sha256_file",
    "validate_catalog",
]
