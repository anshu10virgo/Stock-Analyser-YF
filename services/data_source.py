"""Compatibility exports for infrastructure provider composition.

New code should import from ``stock_analyser.infrastructure.data_services``.
"""

from stock_analyser.infrastructure.data_services import (
    LIVE_SOURCE,
    SNAPSHOT_SOURCE,
    DataServices,
    build_data_services,
    snapshot_source_label,
)

__all__ = [
    "LIVE_SOURCE",
    "SNAPSHOT_SOURCE",
    "DataServices",
    "build_data_services",
    "snapshot_source_label",
]
