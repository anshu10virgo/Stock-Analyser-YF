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
    YahooFinanceClassificationProvider,
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
CLASSIFICATION_REFRESH_DAYS = 180
CLASSIFICATION_COLUMNS = [
    "symbol",
    "sector",
    "industry",
    "sector_key",
    "industry_key",
]


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("full", "incremental", "classifications", "optimize", "validate"),
        default="incremental",
    )
    parser.add_argument(
        "--replay-file",
        type=Path,
        help="Use deterministic long-form CSV rows instead of calling Yahoo.",
    )
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument(
        "--refresh-classifications",
        action="store_true",
        help="Force the normally semiannual sector/industry refresh.",
    )
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
    active_paths = set()
    for year, frame in prices.groupby(prices["Date"].dt.year):
        year = int(year)
        path = prices_root / f"{year}.parquet"
        active_paths.add(path.resolve())
        alternate = prices_root / f"{year}.csv"
        must_write = affected_years is None or year in affected_years or not path.exists()
        if not must_write:
            continue
        frame = frame.sort_values(["Symbol", "Date"])
        frame.to_parquet(
            path,
            index=False,
            compression="zstd",
            row_group_size=10_000,
        )
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


def _classification_paths():
    root = MARKET_ROOT / "fundamentals"
    return root / "classifications.csv", root / "classification_metadata.json"


def load_classifications() -> pd.DataFrame:
    classification_file, _ = _classification_paths()
    if not classification_file.is_file():
        return pd.DataFrame(columns=CLASSIFICATION_COLUMNS)
    frame = pd.read_csv(classification_file)
    for column in CLASSIFICATION_COLUMNS:
        if column not in frame.columns:
            frame[column] = pd.NA
    return frame[CLASSIFICATION_COLUMNS].drop_duplicates("symbol", keep="last")


def active_symbols_sha256(symbols) -> str:
    return hashlib.sha256("\n".join(sorted(symbols)).encode("utf-8")).hexdigest()


def classifications_due(symbols, force=False) -> bool:
    if force:
        return True
    _, metadata_file = _classification_paths()
    if not metadata_file.is_file():
        return True
    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        if not metadata.get("refreshed_at"):
            return True
        stored_symbol_hash = metadata.get("active_symbols_sha256")
        if stored_symbol_hash and stored_symbol_hash != active_symbols_sha256(symbols):
            return True
        if not stored_symbol_hash and metadata.get("active_symbol_count") != len(symbols):
            return True
        refreshed_at = pd.Timestamp(metadata["refreshed_at"])
        if refreshed_at.tzinfo is None:
            refreshed_at = refreshed_at.tz_localize("UTC")
        return (
            pd.Timestamp.now(tz="UTC") - refreshed_at
        ).days >= CLASSIFICATION_REFRESH_DAYS
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return True


def refresh_classifications(symbols, force=False, provider=None) -> pd.DataFrame:
    """Refresh classifications at most every six months and preserve coverage."""
    fundamentals_root = MARKET_ROOT / "fundamentals"
    fundamentals_root.mkdir(parents=True, exist_ok=True)
    classification_file, metadata_file = _classification_paths()
    existing = load_classifications()
    if not classifications_due(symbols, force):
        return existing

    provider = provider or YahooFinanceClassificationProvider()
    incoming = provider.classifications(symbols)
    if not incoming.empty:
        combined = pd.concat([existing, incoming], ignore_index=True)
        combined.drop_duplicates("symbol", keep="last", inplace=True)
    else:
        combined = existing
    combined = combined.loc[combined["symbol"].isin(symbols)].copy()
    combined.to_csv(classification_file, index=False)
    metadata = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "refresh_interval_days": CLASSIFICATION_REFRESH_DAYS,
        "active_symbol_count": len(symbols),
        "classified_symbol_count": int(combined["symbol"].nunique()),
        "active_symbols_sha256": active_symbols_sha256(symbols),
        "provider_metrics": provider.metrics(),
    }
    temporary = metadata_file.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    temporary.replace(metadata_file)
    return combined


def build_fundamentals(
    universe_frame: pd.DataFrame,
    classifications: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build a batch fundamentals snapshot from Yahoo's India screener."""
    quotes = YahooFinanceMarketCapProvider().quotes()
    company_names = universe_frame.set_index("Symbol").get("Company Name", pd.Series(dtype=object))
    classification_records = (
        classifications.set_index("symbol").to_dict("index")
        if classifications is not None and not classifications.empty
        else {}
    )
    rows = []
    for symbol in universe_frame["Symbol"]:
        quote = quotes.get(symbol, {})
        classification = classification_records.get(symbol, {})
        eps = quote.get("epsTrailingTwelveMonths")
        pe = quote.get("trailingPE")
        market_price = quote.get("regularMarketPrice")
        pe_source = "yahoo_trailing_pe" if pe is not None else None
        if pe is None and eps is not None and eps > 0 and market_price is not None:
            pe = market_price / eps
            pe_source = "price_divided_by_trailing_eps"
        rows.append(
            {
                "symbol": symbol,
                "company_name": quote.get("longName") or quote.get("shortName") or company_names.get(symbol),
                "market_cap": quote.get("marketCap"),
                "pe": pe,
                "pe_source": pe_source,
                "forward_pe": quote.get("forwardPE"),
                "eps": eps,
                "sector": classification.get("sector"),
                "industry": classification.get("industry"),
                "revenue_growth": None,
                "earnings_growth": None,
            }
        )
    return pd.DataFrame(rows)


def calculate_industry_valuations(fundamentals: pd.DataFrame) -> pd.DataFrame:
    """Calculate market-cap weighted and median positive P/E by industry."""
    columns = [
        "industry",
        "industry_weighted_pe",
        "industry_median_pe",
        "industry_peer_count",
    ]
    eligible = fundamentals.dropna(subset=["industry", "pe", "market_cap"]).copy()
    eligible = eligible.loc[eligible["pe"].gt(0) & eligible["market_cap"].gt(0)]
    rows = []
    for industry, peers in eligible.groupby("industry"):
        implied_earnings = (peers["market_cap"] / peers["pe"]).sum()
        weighted_pe = peers["market_cap"].sum() / implied_earnings
        rows.append(
            {
                "industry": industry,
                "industry_weighted_pe": round(weighted_pe, 2),
                "industry_median_pe": round(peers["pe"].median(), 2),
                "industry_peer_count": len(peers),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def write_supporting_files(
    prices,
    universe_frame,
    symbols,
    force_classifications=False,
    allow_classification_refresh=True,
):
    fundamentals_root = MARKET_ROOT / "fundamentals"
    fundamentals_root.mkdir(parents=True, exist_ok=True)
    fundamentals_file = fundamentals_root / "fundamentals.csv"
    industry_file = fundamentals_root / "industry_valuations.csv"
    classification_file, classification_metadata_file = _classification_paths()
    coverage_file = MARKET_ROOT / "symbol_coverage.csv"

    classifications = (
        refresh_classifications(symbols, force=force_classifications)
        if allow_classification_refresh
        else load_classifications()
    )
    if not classification_file.is_file():
        classifications.to_csv(classification_file, index=False)
    if not classification_metadata_file.is_file():
        classification_metadata_file.write_text(
            json.dumps(
                {
                    "refreshed_at": None,
                    "refresh_interval_days": CLASSIFICATION_REFRESH_DAYS,
                    "active_symbol_count": len(symbols),
                    "classified_symbol_count": int(classifications["symbol"].nunique()),
                    "active_symbols_sha256": active_symbols_sha256(symbols),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    fundamentals = build_fundamentals(universe_frame, classifications)
    fundamentals.to_csv(fundamentals_file, index=False)
    calculate_industry_valuations(fundamentals).to_csv(industry_file, index=False)

    grouped = prices.groupby("Symbol")["Date"]
    coverage = pd.DataFrame({"Symbol": symbols})
    coverage["First Date"] = coverage["Symbol"].map(grouped.min())
    coverage["Last Date"] = coverage["Symbol"].map(grouped.max())
    coverage["Trading Sessions"] = coverage["Symbol"].map(grouped.nunique()).fillna(0).astype(int)
    coverage.to_csv(coverage_file, index=False, date_format="%Y-%m-%d")
    return (
        fundamentals_file,
        industry_file,
        classification_file,
        classification_metadata_file,
        coverage_file,
    )


def existing_supporting_files():
    """Return committed support files for a storage-only optimization."""
    fundamentals_root = MARKET_ROOT / "fundamentals"
    classification_file, classification_metadata_file = _classification_paths()
    if not classification_file.is_file():
        pd.DataFrame(columns=CLASSIFICATION_COLUMNS).to_csv(
            classification_file, index=False
        )
    if not classification_metadata_file.is_file():
        classification_metadata_file.write_text(
            json.dumps({"refreshed_at": None}, indent=2), encoding="utf-8"
        )
    files = (
        fundamentals_root / "fundamentals.csv",
        fundamentals_root / "industry_valuations.csv",
        classification_file,
        classification_metadata_file,
        MARKET_ROOT / "symbol_coverage.csv",
    )
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Snapshot support file(s) missing: {missing}")
    return files


def write_manifest(prices, price_files, support_files, universe, active_symbols):
    (
        fundamentals_file,
        industry_file,
        classification_file,
        classification_metadata_file,
        coverage_file,
    ) = support_files
    fundamentals = pd.read_csv(fundamentals_file)
    industry_valuations = pd.read_csv(industry_file)
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
        "classifications_file": {
            "path": classification_file.relative_to(MARKET_ROOT).as_posix(),
            "sha256": file_sha256(classification_file),
        },
        "classification_metadata_file": {
            "path": classification_metadata_file.relative_to(MARKET_ROOT).as_posix(),
            "sha256": file_sha256(classification_metadata_file),
        },
        "fundamentals_coverage": {
            "pe": int(fundamentals["pe"].notna().sum()),
            "eps": int(fundamentals["eps"].notna().sum()),
            "sector": int(fundamentals["sector"].notna().sum()),
            "industry": int(fundamentals["industry"].notna().sum()),
            "industries_with_valuations": len(industry_valuations),
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


def refresh(
    mode,
    replay_file=None,
    chunk_size=CHUNK_SIZE,
    force_classifications=False,
):
    VALIDATION_STATS.update(invalid_rows_dropped=0, duplicate_rows_dropped=0)
    universe, universe_frame, symbols = active_universe()
    existing = load_existing_prices()
    if mode == "validate":
        if existing.empty:
            raise RuntimeError("No committed market-data snapshot exists")
        print(f"Validated {len(existing):,} stored rows through {existing['Date'].max().date()}")
        return None

    if mode in {"classifications", "optimize"}:
        if existing.empty:
            raise RuntimeError("No committed market-data snapshot exists")
        incoming = pd.DataFrame(columns=PRICE_COLUMNS)
    elif replay_file:
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
    if (
        mode not in {"classifications", "optimize"}
        and incoming.empty
        and not existing.empty
        and not universe_changed
        and not force_classifications
    ):
        print("No new trading rows; snapshot remains unchanged")
        return None
    combined = validate_prices(pd.concat([existing, incoming], ignore_index=True))
    cutoff = pd.Timestamp.today().normalize() - pd.DateOffset(years=RETENTION_YEARS)
    combined = combined.loc[combined["Date"].ge(cutoff)].copy()
    affected_years = (
        None
        if mode in {"full", "optimize"}
        else (
            set()
            if incoming.empty
            else set(incoming["Date"].dt.year.astype(int))
        )
    )
    price_files = write_price_partitions(combined, affected_years)
    support_files = (
        existing_supporting_files()
        if mode == "optimize"
        else write_supporting_files(
            combined,
            universe_frame,
            symbols,
            force_classifications=(
                force_classifications or mode == "classifications"
            ),
            allow_classification_refresh=replay_file is None,
        )
    )
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
    refresh(
        arguments.mode,
        arguments.replay_file,
        arguments.chunk_size,
        force_classifications=arguments.refresh_classifications,
    )


if __name__ == "__main__":
    main()
