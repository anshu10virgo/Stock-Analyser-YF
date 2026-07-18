"""Resilient Yahoo Finance historical-price provider."""

from __future__ import annotations

import logging
import time
from copy import deepcopy
from datetime import datetime, timedelta
from threading import RLock

import pandas as pd
import yfinance as yf


logger = logging.getLogger(__name__)


class YahooFinanceHistoryProvider:
    """Downloads and caches batched Yahoo Finance OHLCV history."""

    CACHE_TTL_SECONDS = 900
    MAX_RETRIES = 3

    def __init__(self) -> None:
        self._cache = {}
        self._lock = RLock()
        self._metrics = {
            "requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "retries": 0,
            "failures": 0,
        }

    def _cache_key(self, symbols, years, adjusted_prices):
        return tuple(symbols), years, adjusted_prices

    def download_batch(self, symbols, years=3, adjusted_prices=False):
        symbols = list(symbols)
        if not symbols:
            return pd.DataFrame()

        key = self._cache_key(symbols, years, adjusted_prices)
        now = time.monotonic()
        with self._lock:
            cached = self._cache.get(key)
            if cached and now - cached[0] < self.CACHE_TTL_SECONDS:
                self._metrics["cache_hits"] += 1
                return cached[1].copy(deep=True)
            self._metrics["cache_misses"] += 1

        end_date = datetime.today()
        start_date = end_date - timedelta(days=365 * years)
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                with self._lock:
                    self._metrics["requests"] += 1
                data = yf.download(
                    tickers=symbols,
                    start=start_date,
                    end=end_date,
                    auto_adjust=adjusted_prices,
                    group_by="ticker",
                    progress=False,
                    threads=True,
                )
                with self._lock:
                    self._cache[key] = (time.monotonic(), data.copy(deep=True))
                return data
            except Exception as error:
                last_error = error
                logger.warning(
                    "Yahoo history request failed (%s/%s): %s",
                    attempt + 1,
                    self.MAX_RETRIES,
                    error,
                )
                if attempt < self.MAX_RETRIES - 1:
                    with self._lock:
                        self._metrics["retries"] += 1
                    time.sleep(attempt + 1)

        with self._lock:
            self._metrics["failures"] += 1
        raise RuntimeError("Yahoo Finance historical data is unavailable") from last_error

    @staticmethod
    def get_symbol_history(batch_df, symbol):
        try:
            if isinstance(batch_df.columns, pd.MultiIndex):
                history = batch_df[symbol].copy()
            else:
                history = batch_df.copy()
            return history.dropna()
        except (KeyError, TypeError, AttributeError):
            return pd.DataFrame()

    def metrics(self):
        with self._lock:
            return deepcopy(self._metrics)

    def clear_cache(self):
        with self._lock:
            self._cache.clear()


class YahooFinanceIndustryProvider:
    """Retrieve complete NSE peer groups from Yahoo's equity screener."""

    PAGE_SIZE = 250

    @staticmethod
    def industry_quotes(industry):
        """Return all Indian quotes assigned to the requested Yahoo industry."""
        query = yf.EquityQuery(
            "and",
            [
                yf.EquityQuery("eq", ["region", "in"]),
                yf.EquityQuery("eq", ["industry", industry]),
            ],
        )
        first_page = yf.screen(
            query,
            offset=0,
            size=YahooFinanceIndustryProvider.PAGE_SIZE,
            sortField="intradaymarketcap",
            sortAsc=False,
        )
        quotes = first_page.get("quotes", [])
        total = first_page.get("total", len(quotes))
        for offset in range(YahooFinanceIndustryProvider.PAGE_SIZE, total, YahooFinanceIndustryProvider.PAGE_SIZE):
            page = yf.screen(
                query,
                offset=offset,
                size=YahooFinanceIndustryProvider.PAGE_SIZE,
                sortField="intradaymarketcap",
                sortAsc=False,
            )
            quotes.extend(page.get("quotes", []))

        return list({quote["symbol"]: quote for quote in quotes if quote.get("symbol")}.values())
