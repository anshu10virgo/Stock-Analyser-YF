"""Deterministic Screener providers used by refresh and checkpoint tests."""

import pandas as pd

from stock_analyser.infrastructure.screener.provider import (
    SUMMARY_COLUMNS,
    ScreenerCompanySnapshot,
    ScreenerDataError,
)


class FakeProvider:
    def __init__(self, failed=None):
        self.failed = set(failed or [])
        self.fetched = []

    def fetch(self, symbol, refreshed_at):
        self.fetched.append(symbol)
        if symbol in self.failed:
            raise ScreenerDataError(f"No Screener company for {symbol}")
        history = pd.DataFrame(
            {
                "symbol": [symbol, symbol],
                "date": pd.to_datetime(["2025-07-01", "2026-07-01"]),
                "pe": [20.0, 21.0],
                "ttm_eps": [10.0, 11.0],
            }
        )
        summary = {column: None for column in SUMMARY_COLUMNS}
        summary.update(
            {
                "symbol": symbol,
                "screener_company_id": symbol,
                "statement_type": "consolidated",
                "source_url": "https://www.screener.in/",
                "refreshed_at": refreshed_at,
            }
        )
        return ScreenerCompanySnapshot(summary=summary, history=history)

    def metrics(self):
        return {"requests": len(self.fetched), "retries": 0, "failures": 0}


class InterruptingProvider(FakeProvider):
    def __init__(self, interrupt_symbol):
        super().__init__()
        self.interrupt_symbol = interrupt_symbol

    def fetch(self, symbol, refreshed_at):
        if symbol == self.interrupt_symbol:
            self.fetched.append(symbol)
            raise KeyboardInterrupt()
        return super().fetch(symbol, refreshed_at)
