"""Fundamental-data contracts used by application commands."""

from __future__ import annotations

from typing import Protocol

import pandas as pd


class FundamentalsPort(Protocol):
    def get_fundamentals(self, symbol: str) -> dict: ...


class IndustryValuationPort(Protocol):
    def valuation_for(self, industry: str) -> dict: ...


class ScreenerFundamentalsPort(Protocol):
    def fundamental_metrics_batch(self, symbols: list[str]) -> dict[str, dict]: ...

    def valuation_history(self, symbol: str) -> pd.DataFrame: ...
