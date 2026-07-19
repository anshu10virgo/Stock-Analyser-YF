"""Build or incrementally refresh the Git-backed Yahoo market-data snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.data_loader import DataLoader
from providers.yahoo_finance import (
    YahooFinanceHistoryProvider,
    YahooFinanceMarketCapProvider,
)
from services.stock_universe import StockUniverse


MARKET_ROOT = PROJECT_ROOT / "data" / "market_data"
UNIVERSE_ROOT = PROJECT_ROOT / "data" / "stock_universe"
RETENTION_YEARS = 10
MAXIMUM_SUPPORTED_LONG_MA = 2000
CHUNK_SIZE = 100
PRICE_COLUMNS = ["Date", "Symbol", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
MAX_INVALID_ROW_RATIO = 0.001
VALIDATION_STATS = {"invalid_rows_dropped": 0, "duplicate_rows_dropped": 0}


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("full", "incremental", "validate"),
        default="incremental",
    )
    parser.add_argument(
        "--replay-file",
        type=Path,
        help="Use deterministic long-form CSV rows instead of calling Yahoo.",
    )
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_universe():
    universe = StockUniverse(UNIVERSE_ROOT, PROJECT_ROOT / "stock_symbols.csv")
    frame = pd.read_csv(universe.active_file())
    symbols = DataLoader.load_symbols(universe.active_file())
    return universe, frame, symbols


def normalize_batch(provider, batch: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    """Convert Yahoo's wide batch response into a stable long-form contract."""
    frames = []
    for symbol in symbols:
        history = provider.get_symbol_history(batch, symbol)
        if history.empty:
            continue
        history = history.reset_index()
        date_column = "Date" if "Date" in history.columns else history.columns[0]
        history.rename(columns={date_column: "Date"}, inplace=True)
        history["Symbol"] = symbol
        for column in PRICE_COLUMNS:
            if column not in history.columns:
                history[column] = pd.NA
        frames.append(history[PRICE_COLUMNS])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=PRICE_COLUMNS)


def validate_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Reject malformed rows before any active manifest is changed."""
    if prices.empty:
        return pd.DataFrame(columns=PRICE_COLUMNS)
    missing = set(PRICE_COLUMNS) - set(prices.columns)
    if missing:
        raise ValueError(f"Price data is missing columns: {sorted(missing)}")
    result = prices[PRICE_COLUMNS].copy()
    result["Date"] = pd.to_datetime(result["Date"], errors="coerce").dt.tz_localize(None)
    result.dropna(subset=["Date", "Symbol", "Open", "High", "Low", "Close"], inplace=True)
    numeric = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    result[numeric] = result[numeric].apply(pd.to_numeric, errors="coerce")
    invalid_ohlc = (
        result[["Open", "High", "Low", "Close"]].le(0).any(axis=1)
        | result["High"].lt(result[["Open", "Low", "Close"]].max(axis=1))
        | result["Low"].gt(result[["Open", "High", "Close"]].min(axis=1))
        | result["Volume"].fillna(0).lt(0)
    )
    if invalid_ohlc.any():
        invalid_count = int(invalid_ohlc.sum())
        invalid_ratio = invalid_count / len(result)
        if invalid_ratio > MAX_INVALID_ROW_RATIO:
            raise ValueError(
                f"Price validation rejected {invalid_count} row(s) "
                f"({invalid_ratio:.3%}, above allowed {MAX_INVALID_ROW_RATIO:.3%})"
            )
        VALIDATION_STATS["invalid_rows_dropped"] += invalid_count
        print(
            f"Quarantined {invalid_count} malformed Yahoo row(s) "
            f"({invalid_ratio:.4%})"
        )
        result = result.loc[~invalid_ohlc].copy()
    result.sort_values(["Date", "Symbol"], inplace=True)
    duplicate_count = int(result.duplicated(["Date", "Symbol"], keep="last").sum())
    VALIDATION_STATS["duplicate_rows_dropped"] += duplicate_count
    result.drop_duplicates(["Date", "Symbol"], keep="last", inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


def load_existing_prices() -> pd.DataFrame:
    manifest_file = MARKET_ROOT / "manifest.json"
    if not manifest_file.is_file():
        return pd.DataFrame(columns=PRICE_COLUMNS)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    frames = []
    for entry in manifest.get("price_files", []):
        path = MARKET_ROOT / entry["path"]
        if not path.is_file():
            raise FileNotFoundError(f"Manifest price file is missing: {path}")
        frames.append(pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path))
    return validate_prices(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=PRICE_COLUMNS)


def write_price_partitions(
    prices: pd.DataFrame, affected_years: set[int] | None = None
) -> list[dict]:
    prices_root = MARKET_ROOT / "prices"
    prices_root.mkdir(parents=True, exist_ok=True)
    current_year = datetime.now(timezone.utc).year
    active_paths = set()
    for year, frame in prices.groupby(prices["Date"].dt.year):
        year = int(year)
        if year == current_year:
            path = prices_root / f"{year}.csv"
        else:
            path = prices_root / f"{year}.parquet"
        active_paths.add(path.resolve())
        alternate = prices_root / (
            f"{year}.parquet" if path.suffix == ".csv" else f"{year}.csv"
        )
        must_write = affected_years is None or year in affected_years or not path.exists()
        if not must_write:
            continue
        if path.suffix == ".csv":
            frame.to_csv(path, index=False, date_format="%Y-%m-%d")
        else:
            frame.to_parquet(path, index=False, compression="zstd")
        if alternate.exists():
            alternate.unlink()
    for path in prices_root.glob("*.*"):
        if path.resolve() not in active_paths and path.suffix in {".csv", ".parquet"}:
            path.unlink()
    entries = []
    for path in sorted(prices_root.glob("*.*")):
        if path.suffix not in {".csv", ".parquet"}:
            continue
        entries.append(
            {
                "path": path.relative_to(MARKET_ROOT).as_posix(),
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return entries


def build_fundamentals(universe_frame: pd.DataFrame) -> pd.DataFrame:
    """Build a batch fundamentals snapshot from Yahoo's India screener."""
    quotes = YahooFinanceMarketCapProvider().quotes()
    company_names = universe_frame.set_index("Symbol").get("Company Name", pd.Series(dtype=object))
    rows = []
    for symbol in universe_frame["Symbol"]:
        quote = quotes.get(symbol, {})
        rows.append(
            {
                "symbol": symbol,
                "company_name": quote.get("longName") or quote.get("shortName") or company_names.get(symbol),
                "market_cap": quote.get("marketCap"),
                "pe": quote.get("trailingPE"),
                "forward_pe": quote.get("forwardPE"),
                "eps": quote.get("epsTrailingTwelveMonths"),
                "sector": None,
                "industry": None,
                "revenue_growth": None,
                "earnings_growth": None,
            }
        )
    return pd.DataFrame(rows)


def write_supporting_files(prices, universe_frame, symbols):
    fundamentals_root = MARKET_ROOT / "fundamentals"
    fundamentals_root.mkdir(parents=True, exist_ok=True)
    fundamentals_file = fundamentals_root / "fundamentals.csv"
    industry_file = fundamentals_root / "industry_valuations.csv"
    coverage_file = MARKET_ROOT / "symbol_coverage.csv"

    fundamentals = build_fundamentals(universe_frame)
    fundamentals.to_csv(fundamentals_file, index=False)
    pd.DataFrame(
        columns=[
            "industry",
            "industry_weighted_pe",
            "industry_median_pe",
            "industry_peer_count",
        ]
    ).to_csv(industry_file, index=False)

    grouped = prices.groupby("Symbol")["Date"]
    coverage = pd.DataFrame({"Symbol": symbols})
    coverage["First Date"] = coverage["Symbol"].map(grouped.min())
    coverage["Last Date"] = coverage["Symbol"].map(grouped.max())
    coverage["Trading Sessions"] = coverage["Symbol"].map(grouped.nunique()).fillna(0).astype(int)
    coverage.to_csv(coverage_file, index=False, date_format="%Y-%m-%d")
    return fundamentals_file, industry_file, coverage_file


def write_manifest(prices, price_files, support_files, universe, active_symbols):
    fundamentals_file, industry_file, coverage_file = support_files
    generated_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 1,
        "source": "yahoo_finance",
        "generated_at": generated_at,
        "refreshed_at": generated_at,
        "history_start": prices["Date"].min().date().isoformat(),
        "history_end": prices["Date"].max().date().isoformat(),
        "last_trading_date": prices["Date"].max().date().isoformat(),
        "retention_calendar_years": RETENTION_YEARS,
        "maximum_supported_long_ma": MAXIMUM_SUPPORTED_LONG_MA,
        "symbol_count": len(active_symbols),
        "stored_symbol_count": int(prices["Symbol"].nunique()),
        "universe_sha256": universe.metadata().get("sha256"),
        "validation": VALIDATION_STATS.copy(),
        "price_files": price_files,
        "fundamentals_file": {
            "path": fundamentals_file.relative_to(MARKET_ROOT).as_posix(),
            "sha256": file_sha256(fundamentals_file),
        },
        "industry_valuations_file": {
            "path": industry_file.relative_to(MARKET_ROOT).as_posix(),
            "sha256": file_sha256(industry_file),
        },
        "coverage_file": {
            "path": coverage_file.relative_to(MARKET_ROOT).as_posix(),
            "sha256": file_sha256(coverage_file),
        },
    }
    MARKET_ROOT.mkdir(parents=True, exist_ok=True)
    temporary = MARKET_ROOT / "manifest.json.tmp"
    temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary.replace(MARKET_ROOT / "manifest.json")
    return manifest


def download_full(symbols, chunk_size):
    provider = YahooFinanceHistoryProvider()
    frames = []
    for start in range(0, len(symbols), chunk_size):
        chunk = symbols[start:start + chunk_size]
        batch = provider.download_batch(chunk, years=RETENTION_YEARS, adjusted_prices=False)
        frames.append(normalize_batch(provider, batch, chunk))
        print(f"Downloaded {min(start + len(chunk), len(symbols))}/{len(symbols)} symbols")
    return validate_prices(pd.concat(frames, ignore_index=True))


def download_incremental(symbols, existing, chunk_size):
    if existing.empty:
        return download_full(symbols, chunk_size)
    provider = YahooFinanceHistoryProvider()
    frames = []
    available = set(existing["Symbol"].unique())
    added = [symbol for symbol in symbols if symbol not in available]
    for start in range(0, len(added), chunk_size):
        chunk = added[start:start + chunk_size]
        batch = provider.download_batch(
            chunk, years=RETENTION_YEARS, adjusted_prices=False
        )
        frames.append(normalize_batch(provider, batch, chunk))

    start_date = existing["Date"].max().date() + timedelta(days=1)
    end_date = datetime.now(timezone.utc).date() + timedelta(days=1)
    if start_date >= end_date:
        return validate_prices(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame(columns=PRICE_COLUMNS)
    for start in range(0, len(symbols), chunk_size):
        chunk = symbols[start:start + chunk_size]
        batch = provider.download_range(
            chunk,
            start=start_date,
            end=end_date,
            adjusted_prices=False,
        )
        frames.append(normalize_batch(provider, batch, chunk))
    return validate_prices(pd.concat(frames, ignore_index=True))


def retain_new_incremental_rows(incoming, existing):
    """Keep backfills for new symbols and only newer rows for stored symbols."""
    if incoming.empty or existing.empty:
        return incoming
    stored_symbols = set(existing["Symbol"].astype(str))
    latest_stored_date = existing["Date"].max()
    new_symbol = ~incoming["Symbol"].astype(str).isin(stored_symbols)
    newer_session = incoming["Date"].gt(latest_stored_date)
    return incoming.loc[new_symbol | newer_session].copy()


def refresh(mode, replay_file=None, chunk_size=CHUNK_SIZE):
    VALIDATION_STATS.update(invalid_rows_dropped=0, duplicate_rows_dropped=0)
    universe, universe_frame, symbols = active_universe()
    existing = load_existing_prices()
    if mode == "validate":
        if existing.empty:
            raise RuntimeError("No committed market-data snapshot exists")
        print(f"Validated {len(existing):,} stored rows through {existing['Date'].max().date()}")
        return None

    if replay_file:
        incoming = validate_prices(pd.read_csv(replay_file))
    elif mode == "full":
        incoming = download_full(symbols, chunk_size)
        existing = pd.DataFrame(columns=PRICE_COLUMNS)
    else:
        incoming = download_incremental(symbols, existing, chunk_size)

    if mode == "incremental":
        incoming = retain_new_incremental_rows(incoming, existing)

    universe_changed = (
        bool(existing.size)
        and json.loads((MARKET_ROOT / "manifest.json").read_text(encoding="utf-8")).get("universe_sha256")
        != universe.metadata().get("sha256")
    ) if (MARKET_ROOT / "manifest.json").is_file() else False
    if incoming.empty and not existing.empty and not universe_changed:
        print("No new trading rows; snapshot remains unchanged")
        return None
    combined = validate_prices(pd.concat([existing, incoming], ignore_index=True))
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=RETENTION_YEARS)
    combined = combined.loc[combined["Date"].ge(cutoff)].copy()
    affected_years = None if mode == "full" else set(incoming["Date"].dt.year.astype(int))
    current_year = datetime.now(timezone.utc).year
    for csv_path in (MARKET_ROOT / "prices").glob("*.csv") if (MARKET_ROOT / "prices").exists() else []:
        if csv_path.stem.isdigit() and int(csv_path.stem) != current_year:
            affected_years.add(int(csv_path.stem))
    price_files = write_price_partitions(combined, affected_years)
    support_files = write_supporting_files(combined, universe_frame, symbols)
    manifest = write_manifest(
        combined, price_files, support_files, universe, symbols
    )
    print(
        f"Stored {len(combined):,} rows for {manifest['symbol_count']:,} symbols "
        f"through {manifest['last_trading_date']}"
    )
    return manifest


def main():
    arguments = parse_arguments()
    refresh(arguments.mode, arguments.replay_file, arguments.chunk_size)


if __name__ == "__main__":
    main()
