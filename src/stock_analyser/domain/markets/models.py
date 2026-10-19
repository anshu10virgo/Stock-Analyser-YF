"""Provider-independent market identity and dataset-location rules."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketDefinition:
    code: str
    currency: str
    timezone: str
    fundamentals_directory: str


MARKETS = {
    "IN": MarketDefinition("IN", "INR", "Asia/Kolkata", "screener"),
    "US": MarketDefinition("US", "USD", "America/New_York", "sec"),
}


def market_definition(code: str) -> MarketDefinition:
    try:
        return MARKETS[code]
    except KeyError:
        raise ValueError("Market must be IN or US") from None


def stock_key(market: str, symbol: str) -> str:
    """Return a country-qualified identity without changing provider tickers."""
    market_definition(market)
    if not symbol or symbol != symbol.strip() or ":" in symbol:
        raise ValueError("A nonempty provider ticker is required")
    return f"{market}:{symbol}"


def market_data_root(project_root, market: str):
    """Preserve existing India paths; reserve a distinct US dataset root."""
    market_definition(market)
    return project_root if market == "IN" else project_root / "markets" / "US"


__all__ = [
    "MARKETS",
    "MarketDefinition",
    "market_data_root",
    "market_definition",
    "stock_key",
]
