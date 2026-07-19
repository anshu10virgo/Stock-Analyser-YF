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

    def download_range(self, symbols, start, end, adjusted_prices=False):
        """Download an explicit date range for incremental snapshot refreshes."""
        symbols = list(symbols)
        if not symbols:
            return pd.DataFrame()
        with self._lock:
            self._metrics["requests"] += 1
        try:
            return yf.download(
                tickers=symbols,
                start=start,
                end=end,
                auto_adjust=adjusted_prices,
                group_by="ticker",
                progress=False,
                threads=True,
            )
        except Exception:
            with self._lock:
                self._metrics["failures"] += 1
            raise

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

    def market_data_metrics(self):
        """Expose metrics through the common scan-provider contract."""
        return self.metrics()

    def clear_cache(self):
        with self._lock:
            self._cache.clear()


class YahooFinanceIndustryProvider:
    """Retrieve complete NSE peer groups from Yahoo's equity screener."""

    PAGE_SIZE = 250

    @staticmethod
    def industry_quotes(industry):
        """Return all Indian quotes assigned to the requested Yahoo industry."""
        # Yahoo domain data displays grouped industries with " - ", while the
        # equity screener validates those same names with an em dash.
        query_industry = industry.replace(" - ", "\u2014")
        query = yf.EquityQuery(
            "and",
            [
                yf.EquityQuery("eq", ["region", "in"]),
                yf.EquityQuery("eq", ["industry", query_industry]),
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


class YahooFinanceClassificationProvider:
    """Build Indian symbol classifications from Yahoo sector domains."""

    SECTOR_KEYS = (
        "basic-materials",
        "communication-services",
        "consumer-cyclical",
        "consumer-defensive",
        "energy",
        "financial-services",
        "healthcare",
        "industrials",
        "real-estate",
        "technology",
        "utilities",
    )

    def __init__(self, sector_factory=None, industry_provider=None) -> None:
        self.sector_factory = sector_factory or yf.Sector
        self.industry_provider = industry_provider or YahooFinanceIndustryProvider
        self._metrics = {
            "sector_requests": 0,
            "industry_requests": 0,
            "failures": 0,
        }

    def classifications(self, symbols=None) -> pd.DataFrame:
        """Return symbol, sector, and industry mappings for Indian equities."""
        requested = set(symbols or [])
        rows = []
        for sector_key in self.SECTOR_KEYS:
            try:
                self._metrics["sector_requests"] += 1
                sector = self.sector_factory(sector_key, region="IN")
                sector_name = sector.name
                industries = sector.industries
            except Exception as error:
                self._metrics["failures"] += 1
                logger.warning("Yahoo sector classification failed for %s: %s", sector_key, error)
                continue
            if industries is None or industries.empty:
                continue
            for industry_key, industry_row in industries.iterrows():
                industry_name = industry_row.get("name")
                try:
                    self._metrics["industry_requests"] += 1
                    quotes = self.industry_provider.industry_quotes(industry_name)
                except Exception as error:
                    self._metrics["failures"] += 1
                    logger.warning(
                        "Yahoo industry classification failed for %s: %s",
                        industry_name,
                        error,
                    )
                    continue
                for quote in quotes:
                    symbol = quote.get("symbol")
                    if not symbol or (requested and symbol not in requested):
                        continue
                    rows.append(
                        {
                            "symbol": symbol,
                            "sector": sector_name,
                            "industry": industry_name,
                            "sector_key": sector_key,
                            "industry_key": industry_key,
                        }
                    )
        if not rows:
            return pd.DataFrame(
                columns=("symbol", "sector", "industry", "sector_key", "industry_key")
            )
        return pd.DataFrame(rows).drop_duplicates("symbol", keep="last")

    def metrics(self) -> dict:
        return deepcopy(self._metrics)


class YahooFinanceMarketCapProvider:
    """Retrieve Indian Yahoo Finance market caps in ranked screener pages."""

    PAGE_SIZE = 250

    def __init__(self) -> None:
        self._metrics = {"requests": 0, "failures": 0}
        self._quotes = None

    def quotes(self) -> dict[str, dict]:
        """Return available Indian screener quotes keyed by Yahoo symbol."""
        if self._quotes is not None:
            return deepcopy(self._quotes)
        query = yf.EquityQuery("eq", ["region", "in"])
        try:
            first_page = self._screen(query, 0)
            quotes = first_page.get("quotes", [])
            total = first_page.get("total", len(quotes))
            for offset in range(self.PAGE_SIZE, total, self.PAGE_SIZE):
                quotes.extend(self._screen(query, offset).get("quotes", []))
        except Exception:
            self._metrics["failures"] += 1
            raise

        self._quotes = {
            quote["symbol"]: quote for quote in quotes if quote.get("symbol")
        }
        return deepcopy(self._quotes)

    def market_caps(self) -> dict[str, float]:
        """Return available INR market caps keyed by Yahoo NSE symbol."""
        return {
            symbol: float(quote["marketCap"])
            for symbol, quote in self.quotes().items()
            if quote.get("marketCap") is not None
        }

    def _screen(self, query, offset: int) -> dict:
        self._metrics["requests"] += 1
        return yf.screen(
            query,
            offset=offset,
            size=self.PAGE_SIZE,
            sortField="intradaymarketcap",
            sortAsc=False,
        )

    def metrics(self) -> dict:
        return deepcopy(self._metrics)
