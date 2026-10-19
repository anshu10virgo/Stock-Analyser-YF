"""Market-history contract used by scan and Backtest use cases."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class MarketDataPort(Protocol):
    def download_batch(
        self, symbols: list[str], *, years: int, adjusted_prices: bool
    ) -> Any: ...

    def get_symbol_history(self, batch_data: Any, symbol: str) -> pd.DataFrame: ...
