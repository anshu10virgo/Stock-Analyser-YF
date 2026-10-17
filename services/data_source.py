"""Construct consistent live, cloud-snapshot, or downloaded-local services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.fundamentals import Fundamentals
from providers.repository_data import (
    RepositoryFundamentalsProvider,
    RepositoryHistoryProvider,
    RepositoryIndustryValuationService,
    RepositoryScreenerProvider,
)
from providers.yahoo_finance import YahooFinanceHistoryProvider
from services.industry_valuation import IndustryValuationService
from services.snapshot_storage import ScopedSnapshotStorage
from services.storage_config import application_snapshot_storage
from models.market import market_data_root, market_definition


LIVE_SOURCE = "Live Yahoo Finance"
SNAPSHOT_SOURCE = "Git snapshot (Yahoo fallback if missing)"
# Retain the historical session identifier so deployed sessions survive upgrades.
# All user-facing labels derive from the actual storage provider.


def snapshot_source_label(cloud):
    return "Cloud snapshot" if cloud else "Local snapshot"


@dataclass(frozen=True)
class DataServices:
    history: object
    fundamentals: object
    industry_valuation: object
    screener: object
    metadata: dict


def build_data_services(source: str, project_root: Path, storage=None, market="IN") -> DataServices:
    """Return providers that all use the selected source policy."""
    market_root = market_data_root(Path(project_root), market) / "data" / "market_data"
    storage = storage or application_snapshot_storage(project_root, market)
    if storage.market != market:
        raise ValueError("Storage belongs to a different market")
    market_storage = ScopedSnapshotStorage(storage, "data/market_data")
    fundamentals_directory = market_definition(market).fundamentals_directory
    screener = RepositoryScreenerProvider(
        market_root / fundamentals_directory,
        storage=ScopedSnapshotStorage(storage, f"data/market_data/{fundamentals_directory}"),
    )
    if source == LIVE_SOURCE:
        history = YahooFinanceHistoryProvider()
        return DataServices(
            history=history,
            fundamentals=Fundamentals,
            industry_valuation=IndustryValuationService(),
            screener=screener,
            metadata={"source": "yahoo_live", "market": market},
        )

    live_history = YahooFinanceHistoryProvider()
    live_industry = IndustryValuationService()
    # Cloud snapshots fail explicitly rather than silently mixing live data.
    history = RepositoryHistoryProvider(
        market_root, fallback=None if storage.cloud else live_history,
        storage=market_storage,
    )
    return DataServices(
        history=history,
        fundamentals=RepositoryFundamentalsProvider(
            market_root, fallback=None if storage.cloud else Fundamentals,
            storage=market_storage,
        ),
        industry_valuation=RepositoryIndustryValuationService(
            market_root, fallback=None if storage.cloud else live_industry,
            storage=market_storage,
        ),
        screener=screener,
        metadata={
            **history.metadata(),
            "market": market,
            "access_mode": "cloud_snapshot" if storage.cloud else "local_snapshot",
            **({"snapshot_id": storage.snapshot_id} if storage.cloud else {}),
        },
    )
