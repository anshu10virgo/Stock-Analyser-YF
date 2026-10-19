"""Compatibility exports for R2/S3 storage configuration.

New code should import from ``stock_analyser.infrastructure.r2.config``.
"""

from stock_analyser.infrastructure.r2.config import (
    application_snapshot_storage,
    configured_cloud_storage,
    create_storage_client,
    market_storage_prefix,
)

__all__ = [
    "application_snapshot_storage",
    "configured_cloud_storage",
    "create_storage_client",
    "market_storage_prefix",
]
