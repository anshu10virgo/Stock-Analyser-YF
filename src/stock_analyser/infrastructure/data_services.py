"""Construct consistent live, cloud-snapshot, or downloaded-local services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from stock_analyser.application.ports import (
    FundamentalsPort,
    IndustryValuationPort,
    MarketDataPort,
    ScreenerFundamentalsPort,
)
from stock_analyser.infrastructure.r2.repository import (
    RepositoryFundamentalsProvider,
    RepositoryHistoryProvider,
    RepositoryIndustryValuationService,
    RepositoryScreenerProvider,
)
from stock_analyser.infrastructure.r2.storage import ScopedSnapshotStorage
from stock_analyser.infrastructure.r2.config import application_snapshot_storage
from stock_analyser.infrastructure.yahoo.fundamentals import YahooFundamentalsProvider
from stock_analyser.infrastructure.yahoo.industry_valuation import (
    YahooIndustryValuationService,
)
from stock_analyser.infrastructure.yahoo.providers import YahooFinanceHistoryProvider
from stock_analyser.domain.markets import market_data_root, market_definition


LIVE_SOURCE = "Live Yahoo Finance"
SNAPSHOT_SOURCE = "Git snapshot (Yahoo fallback if missing)"
# Retain the historical session identifier so deployed sessions survive upgrades.
# All user-facing labels derive from the actual storage provider.


def snapshot_source_label(cloud):
    return "Cloud snapshot" if cloud else "Local snapshot"


@dataclass(frozen=True)
class DataServices:
    history: MarketDataPort
    fundamentals: FundamentalsPort
    industry_valuation: IndustryValuationPort
    screener: ScreenerFundamentalsPort
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
            fundamentals=YahooFundamentalsProvider(),
            industry_valuation=YahooIndustryValuationService(),
            screener=screener,
            metadata={"source": "yahoo_live", "market": market},
        )

    live_history = YahooFinanceHistoryProvider()
    live_industry = YahooIndustryValuationService()
    # Cloud snapshots fail explicitly rather than silently mixing live data.
    history = RepositoryHistoryProvider(
        market_root, fallback=None if storage.cloud else live_history,
        storage=market_storage,
    )
    return DataServices(
        history=history,
        fundamentals=RepositoryFundamentalsProvider(
            market_root,
            fallback=None if storage.cloud else YahooFundamentalsProvider(),
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
