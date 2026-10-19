"""Compatibility exports for the packaged markets domain."""

from stock_analyser.domain.markets import (
    MARKETS,
    MarketDefinition,
    market_data_root,
    market_definition,
    stock_key,
)

__all__ = [
    "MARKETS",
    "MarketDefinition",
    "market_data_root",
    "market_definition",
    "stock_key",
]
