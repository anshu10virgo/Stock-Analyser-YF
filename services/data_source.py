"""Construct consistent live or Git-snapshot data services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from core.fundamentals import Fundamentals
from providers.repository_data import (
    RepositoryFundamentalsProvider,
    RepositoryHistoryProvider,
    RepositoryIndustryValuationService,
)
from providers.yahoo_finance import YahooFinanceHistoryProvider
from services.industry_valuation import IndustryValuationService


LIVE_SOURCE = "Live Yahoo Finance"
SNAPSHOT_SOURCE = "Git snapshot (Yahoo fallback if missing)"


@dataclass(frozen=True)
class DataServices:
    history: object
    fundamentals: object
    industry_valuation: object
    metadata: dict


def build_data_services(source: str, project_root: Path) -> DataServices:
    """Return providers that all use the selected source policy."""
    if source == LIVE_SOURCE:
        history = YahooFinanceHistoryProvider()
        return DataServices(
            history=history,
            fundamentals=Fundamentals,
            industry_valuation=IndustryValuationService(),
            metadata={"source": "yahoo_live"},
        )

    market_root = Path(project_root) / "data" / "market_data"
    live_history = YahooFinanceHistoryProvider()
    live_industry = IndustryValuationService()
    history = RepositoryHistoryProvider(market_root, fallback=live_history)
    return DataServices(
        history=history,
        fundamentals=RepositoryFundamentalsProvider(market_root, fallback=Fundamentals),
        industry_valuation=RepositoryIndustryValuationService(
            market_root, fallback=live_industry
        ),
        metadata={**history.metadata(), "access_mode": "git_snapshot"},
    )
