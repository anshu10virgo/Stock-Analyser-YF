"""Git-backed market data and fundamentals providers."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pandas as pd


PRICE_COLUMNS = ("Open", "High", "Low", "Close", "Adj Close", "Volume")


class SnapshotUnavailableError(RuntimeError):
    """Raised when the committed snapshot cannot satisfy a request."""


def _clean_record(record: dict) -> dict:
    return {
        key: None if value is None or pd.isna(value) else value
        for key, value in record.items()
    }


def _as_symbol_batch(batch: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    if batch.empty:
        return batch
    if isinstance(batch.columns, pd.MultiIndex):
        return batch
    if len(symbols) != 1:
        raise SnapshotUnavailableError("Provider returned ambiguous multi-symbol data")
    return pd.concat({symbols[0]: batch}, axis=1)


class RepositoryHistoryProvider:
    """Read annual price partitions committed under ``data/market_data``."""

    FILTERED_SYMBOL_LIMIT = 10

    def __init__(self, root: Path, fallback=None) -> None:
        self.root = Path(root)
        self.fallback = fallback
        self.manifest_file = self.root / "manifest.json"
        self._prices = None
        self._metrics = {
            "requests": 0,
            "snapshot_hits": 0,
            "fallback_requests": 0,
            "failures": 0,
            "filtered_partition_reads": 0,
            "full_snapshot_loads": 0,
            "rows_loaded": 0,
        }

    def metadata(self) -> dict:
        if not self.manifest_file.is_file():
            return {}
        return json.loads(self.manifest_file.read_text(encoding="utf-8"))

    def _price_paths(self) -> list[Path]:
        manifest = self.metadata()
        entries = manifest.get("price_files", [])
        paths = [self.root / entry["path"] for entry in entries]
        if not paths or any(not path.is_file() for path in paths):
            raise SnapshotUnavailableError("Committed market-data price files are missing")
        return paths

    def _load_prices(self) -> pd.DataFrame:
        if self._prices is not None:
            return self._prices
        frames = []
        for path in self._price_paths():
            frame = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
            frames.append(frame)
        prices = pd.concat(frames, ignore_index=True)
        required = {"Date", "Symbol", "Open", "High", "Low", "Close", "Volume"}
        if not required.issubset(prices.columns):
            raise SnapshotUnavailableError("Committed market-data schema is invalid")
        prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
        prices.dropna(subset=["Date", "Symbol"], inplace=True)
        prices.sort_values(["Date", "Symbol"], inplace=True)
        prices.drop_duplicates(["Date", "Symbol"], keep="last", inplace=True)
        self._prices = prices
        self._metrics["full_snapshot_loads"] += 1
        self._metrics["rows_loaded"] += len(prices)
        return prices

    def _load_filtered_prices(
        self, symbols: list[str], cutoff: pd.Timestamp
    ) -> pd.DataFrame:
        """Read only requested symbols from Parquet-backed partitions."""
        frames = []
        for path in self._price_paths():
            if path.suffix == ".parquet":
                symbol_filter = (
                    ("Symbol", "==", symbols[0])
                    if len(symbols) == 1
                    else ("Symbol", "in", symbols)
                )
                frame = pd.read_parquet(
                    path,
                    filters=[symbol_filter, ("Date", ">=", cutoff)],
                )
            else:
                frame = pd.read_csv(path)
                frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
                frame = frame.loc[
                    frame["Symbol"].isin(symbols) & frame["Date"].ge(cutoff)
                ]
            if not frame.empty:
                frames.append(frame)
        self._metrics["filtered_partition_reads"] += 1
        if not frames:
            return pd.DataFrame()
        prices = pd.concat(frames, ignore_index=True)
        prices["Date"] = pd.to_datetime(prices["Date"], errors="coerce")
        prices.sort_values(["Date", "Symbol"], inplace=True)
        prices.drop_duplicates(["Date", "Symbol"], keep="last", inplace=True)
        self._metrics["rows_loaded"] += len(prices)
        return prices

    @staticmethod
    def _adjusted(group: pd.DataFrame) -> pd.DataFrame:
        result = group.copy()
        if "Adj Close" not in result.columns:
            return result
        factor = (
            result["Adj Close"]
            .div(result["Close"])
            .replace([float("inf"), -float("inf")], pd.NA)
            .fillna(1.0)
        )
        for column in ("Open", "High", "Low", "Close"):
            result[column] = result[column] * factor
        return result

    def _local_batch(self, symbols: list[str], years: int, adjusted_prices: bool):
        cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=years)
        prices = (
            self._load_filtered_prices(symbols, cutoff)
            if len(symbols) <= self.FILTERED_SYMBOL_LIMIT
            else self._load_prices()
        )
        selected = prices.loc[
            prices["Symbol"].isin(symbols) & prices["Date"].ge(cutoff)
        ].copy()
        available = set(selected["Symbol"].unique())
        batches = {}
        for symbol, group in selected.groupby("Symbol", sort=False):
            group = group.set_index("Date").sort_index()
            if adjusted_prices:
                group = self._adjusted(group)
            columns = [column for column in PRICE_COLUMNS if column in group.columns]
            batches[symbol] = group[columns]
        batch = pd.concat(batches, axis=1) if batches else pd.DataFrame()
        return batch, [symbol for symbol in symbols if symbol not in available]

    def download_batch(self, symbols, years=3, adjusted_prices=False):
        symbols = list(dict.fromkeys(symbols))
        self._metrics["requests"] += 1
        try:
            local, missing = self._local_batch(symbols, years, adjusted_prices)
            if not missing:
                self._metrics["snapshot_hits"] += 1
                return local
            if self.fallback is None:
                raise SnapshotUnavailableError(
                    f"Snapshot has no data for {len(missing)} requested symbol(s)"
                )
            self._metrics["fallback_requests"] += 1
            live = self.fallback.download_batch(
                missing, years=years, adjusted_prices=adjusted_prices
            )
            live = _as_symbol_batch(live, missing)
            return pd.concat([local, live], axis=1) if not local.empty else live
        except SnapshotUnavailableError:
            if self.fallback is None:
                self._metrics["failures"] += 1
                raise
            self._metrics["fallback_requests"] += 1
            return self.fallback.download_batch(
                symbols, years=years, adjusted_prices=adjusted_prices
            )

    @staticmethod
    def get_symbol_history(batch_df, symbol):
        try:
            if isinstance(batch_df.columns, pd.MultiIndex):
                history = batch_df[symbol].copy()
            else:
                history = batch_df.copy()
            return history.dropna(subset=["Close"])
        except (KeyError, TypeError, AttributeError):
            return pd.DataFrame()

    def market_data_metrics(self):
        return deepcopy(self._metrics)


class RepositoryFundamentalsProvider:
    """Read committed fundamentals, with optional fallback only when absent."""

    def __init__(self, root: Path, fallback=None) -> None:
        self.file = Path(root) / "fundamentals" / "fundamentals.csv"
        self.fallback = fallback
        self._records = None

    def _load(self) -> dict:
        if self._records is not None:
            return self._records
        if not self.file.is_file():
            raise SnapshotUnavailableError("Committed fundamentals file is missing")
        frame = pd.read_csv(self.file)
        if "symbol" not in frame.columns:
            raise SnapshotUnavailableError("Committed fundamentals schema is invalid")
        self._records = frame.set_index("symbol").to_dict("index")
        return self._records

    def get_fundamentals(self, symbol):
        try:
            record = self._load().get(symbol)
            if record is None:
                raise SnapshotUnavailableError(f"No committed fundamentals for {symbol}")
            return _clean_record(record)
        except SnapshotUnavailableError:
            if self.fallback is None:
                raise
            return self.fallback.get_fundamentals(symbol)


class RepositoryIndustryValuationService:
    """Read committed industry P/E benchmarks without live peer requests."""

    def __init__(self, root: Path, fallback=None) -> None:
        self.file = Path(root) / "fundamentals" / "industry_valuations.csv"
        self.fallback = fallback
        self._records = None
        self._metrics = {"requests": 0, "snapshot_hits": 0, "fallback_requests": 0, "failures": 0}

    @staticmethod
    def empty_result():
        return {
            "industry_weighted_pe": None,
            "industry_median_pe": None,
            "industry_peer_count": 0,
        }

    def _load(self):
        if self._records is not None:
            return self._records
        if not self.file.is_file():
            raise SnapshotUnavailableError("Committed industry valuation file is missing")
        frame = pd.read_csv(self.file)
        if "industry" not in frame.columns:
            raise SnapshotUnavailableError("Committed industry valuation schema is invalid")
        self._records = frame.set_index("industry").to_dict("index")
        return self._records

    def valuation_for(self, industry):
        self._metrics["requests"] += 1
        if not industry or pd.isna(industry):
            return self.empty_result()
        try:
            record = self._load().get(industry)
            if record is None:
                raise SnapshotUnavailableError(f"No committed benchmark for {industry}")
            self._metrics["snapshot_hits"] += 1
            return _clean_record(record)
        except SnapshotUnavailableError:
            if self.fallback is None:
                self._metrics["failures"] += 1
                return self.empty_result()
            self._metrics["fallback_requests"] += 1
            return self.fallback.valuation_for(industry)

    def metrics(self):
        return deepcopy(self._metrics)

    def begin_scan(self):
        self._metrics = {"requests": 0, "snapshot_hits": 0, "fallback_requests": 0, "failures": 0}
        if self.fallback is not None and hasattr(self.fallback, "begin_scan"):
            self.fallback.begin_scan()
