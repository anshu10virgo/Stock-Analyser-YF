"""Fundamental-data contracts used by application commands."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class FundamentalsPort(Protocol):
    def get_fundamentals(self, symbol: str) -> dict: ...


@runtime_checkable
class IndustryValuationPort(Protocol):
    def valuation_for(self, industry: str) -> dict: ...


@runtime_checkable
class ScreenerFundamentalsPort(Protocol):
    def fundamental_metrics_batch(self, symbols: list[str]) -> dict[str, dict]: ...

    def valuation_history(self, symbol: str) -> pd.DataFrame: ...
