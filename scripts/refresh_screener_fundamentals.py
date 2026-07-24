"""Refresh the Git-backed Screener fundamentals and valuation snapshot."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.data_loader import DataLoader
from providers.screener import (
    HISTORY_COLUMNS,
    SUMMARY_COLUMNS,
    ScreenerDataError,
    ScreenerFundamentalsProvider,
)
from services.stock_universe import StockUniverse


SCREENER_ROOT = PROJECT_ROOT / "data" / "market_data" / "screener"
UNIVERSE_ROOT = PROJECT_ROOT / "data" / "stock_universe"
SCHEMA_VERSION = 1
DEFAULT_BATCH_SIZE = 10
DEFAULT_BATCH_SLEEP_SECONDS = 5.0
logger = logging.getLogger(__name__)


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("refresh", "validate"),
        default="refresh",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=DEFAULT_BATCH_SLEEP_SECONDS,
    )
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Discard an unfinished compatible staging run and start again.",
    )
    return parser.parse_args()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def active_universe():
    universe = StockUniverse(UNIVERSE_ROOT)
    symbols = DataLoader.load_symbols(universe.active_file())
    return universe, symbols


def _staging_root(root: Path) -> Path:
    return Path(root) / ".staging"


def _checkpoint_file(root: Path) -> Path:
    return _staging_root(root) / "checkpoint.json"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)


def _write_batch(
    staging: Path,
    batch_number: int,
    summaries: list[dict],
    histories: list[pd.DataFrame],
    failures: list[dict],
) -> None:
    batches = staging / "batches"
    batches.mkdir(parents=True, exist_ok=True)
    prefix = batches / f"{batch_number:06d}"
    summary = pd.DataFrame(summaries, columns=SUMMARY_COLUMNS)
    history = (
        pd.concat(histories, ignore_index=True)
        if histories
        else pd.DataFrame(columns=HISTORY_COLUMNS)
    )
    failure_frame = pd.DataFrame(
        failures,
        columns=("symbol", "error_type", "reason", "failed_at"),
    )
    summary.to_csv(prefix.with_name(prefix.name + "_summary.csv"), index=False)
    history.to_parquet(
        prefix.with_name(prefix.name + "_history.parquet"),
        index=False,
        compression="zstd",
    )
    failure_frame.to_csv(
        prefix.with_name(prefix.name + "_failures.csv"), index=False
    )


def _load_staged(staging: Path):
    summaries = [
        pd.read_csv(path)
        for path in sorted((staging / "batches").glob("*_summary.csv"))
    ]
    histories = [
        pd.read_parquet(path)
        for path in sorted((staging / "batches").glob("*_history.parquet"))
    ]
    failures = [
        pd.read_csv(path)
        for path in sorted((staging / "batches").glob("*_failures.csv"))
    ]
    return (
        pd.concat(summaries, ignore_index=True)
        if summaries
        else pd.DataFrame(columns=SUMMARY_COLUMNS),
        pd.concat(histories, ignore_index=True)
        if histories
        else pd.DataFrame(columns=HISTORY_COLUMNS),
        pd.concat(failures, ignore_index=True)
        if failures
        else pd.DataFrame(
            columns=("symbol", "error_type", "reason", "failed_at")
        ),
    )


def validate_frames(
    summary: pd.DataFrame,
    history: pd.DataFrame,
    failures: pd.DataFrame,
    symbols: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Validate a complete audited run before activating its manifest."""
    missing_summary = set(SUMMARY_COLUMNS) - set(summary.columns)
    missing_history = set(HISTORY_COLUMNS) - set(history.columns)
    if missing_summary:
        raise ValueError(
            f"Screener summary is missing columns: {sorted(missing_summary)}"
        )
    if missing_history:
        raise ValueError(
            f"Screener history is missing columns: {sorted(missing_history)}"
        )

    summary = summary[list(SUMMARY_COLUMNS)].copy()
    history = history[list(HISTORY_COLUMNS)].copy()
    summary.drop_duplicates("symbol", keep="last", inplace=True)
    history["date"] = pd.to_datetime(history["date"], errors="coerce")
    history["pe"] = pd.to_numeric(history["pe"], errors="coerce")
    history["ttm_eps"] = pd.to_numeric(history["ttm_eps"], errors="coerce")
    history.dropna(subset=["symbol", "date"], inplace=True)
    history = history.loc[history[["pe", "ttm_eps"]].notna().any(axis=1)]
    history.sort_values(["symbol", "date"], inplace=True)
    history.drop_duplicates(["symbol", "date"], keep="last", inplace=True)
    failures = failures.drop_duplicates("symbol", keep="last").copy()

    requested = set(symbols)
    succeeded = set(summary["symbol"])
    failed = set(failures["symbol"])
    unexpected = (succeeded | failed) - requested
    missing = requested - succeeded - failed
    overlaps = succeeded & failed
    if unexpected or missing or overlaps:
        raise ValueError(
            "Screener refresh audit is incomplete: "
            f"missing={len(missing)}, unexpected={len(unexpected)}, "
            f"success/failure overlaps={len(overlaps)}"
        )
    if summary.empty:
        raise ValueError("Screener refresh produced no successful company records")
    history_symbols = set(history["symbol"])
    if not succeeded.issubset(history_symbols):
        raise ValueError(
            "Screener history is missing successful summary symbols"
        )
    return (
        summary.sort_values("symbol").reset_index(drop=True),
        history.reset_index(drop=True),
        failures.sort_values("symbol").reset_index(drop=True),
    )


def _activate_snapshot(
    root: Path,
    summary: pd.DataFrame,
    history: pd.DataFrame,
    failures: pd.DataFrame,
    symbols: list[str],
    universe_sha256: str | None,
    provider_metrics: dict,
    generated_at: str,
    batch_size: int,
    sleep_seconds: float,
) -> dict:
    snapshots = root / "snapshots"
    snapshots.mkdir(parents=True, exist_ok=True)
    version = pd.Timestamp(generated_at).strftime("%Y%m%dT%H%M%SZ")
    summary_file = snapshots / f"fundamental_metrics_{version}.csv"
    history_file = snapshots / f"historical_valuation_{version}.parquet"
    failures_file = snapshots / f"coverage_{version}.csv"
    summary.to_csv(summary_file, index=False)
    history.to_parquet(
        history_file,
        index=False,
        compression="zstd",
        row_group_size=10_000,
    )
    failures.to_csv(failures_file, index=False)

    coverage = {
        column: int(summary[column].notna().sum())
        for column in SUMMARY_COLUMNS
        if column not in {
            "symbol",
            "screener_company_id",
            "statement_type",
            "source_url",
            "refreshed_at",
        }
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source": "screener.in",
        "generated_at": generated_at,
        "universe_sha256": universe_sha256,
        "requested_symbol_count": len(symbols),
        "successful_symbol_count": int(summary["symbol"].nunique()),
        "failed_symbol_count": int(failures["symbol"].nunique()),
        "historical_observation_count": len(history),
        "batch_size": batch_size,
        "batch_sleep_seconds": sleep_seconds,
        "summary_file": {
            "path": summary_file.relative_to(root).as_posix(),
            "sha256": file_sha256(summary_file),
        },
        "history_file": {
            "path": history_file.relative_to(root).as_posix(),
            "sha256": file_sha256(history_file),
        },
        "coverage_file": {
            "path": failures_file.relative_to(root).as_posix(),
            "sha256": file_sha256(failures_file),
        },
        "metric_coverage": coverage,
        "provider_metrics": provider_metrics,
    }
    _atomic_json(root / "manifest.json", manifest)

    active = {summary_file.resolve(), history_file.resolve(), failures_file.resolve()}
    for path in snapshots.glob("*.*"):
        if path.resolve() not in active:
            path.unlink()
    return manifest


def validate_snapshot(root: Path = SCREENER_ROOT) -> dict:
    manifest_file = Path(root) / "manifest.json"
    if not manifest_file.is_file():
        raise FileNotFoundError("Committed Screener manifest is missing")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Committed Screener manifest schema is unsupported")
    for key in ("summary_file", "history_file", "coverage_file"):
        entry = manifest.get(key, {})
        path = Path(root) / entry.get("path", "")
        if not path.is_file():
            raise FileNotFoundError(f"Committed Screener {key} is missing")
        if file_sha256(path) != entry.get("sha256"):
            raise ValueError(f"Committed Screener {key} hash does not match")
    summary_path = Path(root) / manifest["summary_file"]["path"]
    history_path = Path(root) / manifest["history_file"]["path"]
    summary = pd.read_csv(summary_path)
    history = pd.read_parquet(history_path)
    if set(SUMMARY_COLUMNS) - set(summary.columns):
        raise ValueError("Committed Screener summary schema is invalid")
    if set(HISTORY_COLUMNS) - set(history.columns):
        raise ValueError("Committed Screener history schema is invalid")
    if summary["symbol"].nunique() != manifest["successful_symbol_count"]:
        raise ValueError("Committed Screener summary count does not match manifest")
    if len(history) != manifest["historical_observation_count"]:
        raise ValueError("Committed Screener history count does not match manifest")
    return manifest


def refresh(
    symbols: list[str] | None = None,
    root: Path = SCREENER_ROOT,
    universe=None,
    provider=None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    sleep_seconds: float = DEFAULT_BATCH_SLEEP_SECONDS,
    restart: bool = False,
    sleep=time.sleep,
) -> dict:
    """Run one resumable refresh for every Screener-derived metric."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if sleep_seconds < 0:
        raise ValueError("sleep_seconds cannot be negative")
    root = Path(root)
    if symbols is None:
        universe, symbols = active_universe()
    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise ValueError("Screener refresh requires at least one symbol")
    universe_sha256 = universe.metadata().get("sha256") if universe else None

    staging = _staging_root(root)
    if restart and staging.exists():
        shutil.rmtree(staging)
    checkpoint_file = _checkpoint_file(root)
    if checkpoint_file.is_file():
        checkpoint = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        if (
            checkpoint.get("symbols_sha256")
            != hashlib.sha256("\n".join(symbols).encode()).hexdigest()
        ):
            raise ValueError(
                "Staged Screener run belongs to another universe; use --restart"
            )
    else:
        checkpoint = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "symbols_sha256": hashlib.sha256(
                "\n".join(symbols).encode()
            ).hexdigest(),
            "completed_symbols": [],
            "next_batch_number": 1,
        }
        _atomic_json(checkpoint_file, checkpoint)

    completed = set(checkpoint["completed_symbols"])
    pending = [symbol for symbol in symbols if symbol not in completed]
    provider = provider or ScreenerFundamentalsProvider()
    generated_at = datetime.now(timezone.utc).isoformat()

    for start in range(0, len(pending), batch_size):
        batch = pending[start : start + batch_size]
        summaries = []
        histories = []
        failures = []
        for symbol in batch:
            try:
                snapshot = provider.fetch(symbol, refreshed_at=generated_at)
                summaries.append(snapshot.summary)
                histories.append(snapshot.history)
            except (ScreenerDataError, ValueError, TypeError) as error:
                failures.append(
                    {
                        "symbol": symbol,
                        "error_type": type(error).__name__,
                        "reason": str(error),
                        "failed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
        _write_batch(
            staging,
            checkpoint["next_batch_number"],
            summaries,
            histories,
            failures,
        )
        completed.update(batch)
        checkpoint["completed_symbols"] = [
            symbol for symbol in symbols if symbol in completed
        ]
        checkpoint["next_batch_number"] += 1
        checkpoint["updated_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(checkpoint_file, checkpoint)
        logger.info(
            "Processed %s/%s Screener symbols", len(completed), len(symbols)
        )
        if start + len(batch) < len(pending) and sleep_seconds:
            sleep(sleep_seconds)

    summary, history, failures = _load_staged(staging)
    summary, history, failures = validate_frames(
        summary, history, failures, symbols
    )
    manifest = _activate_snapshot(
        root,
        summary,
        history,
        failures,
        symbols,
        universe_sha256,
        provider.metrics(),
        generated_at,
        batch_size,
        sleep_seconds,
    )
    validate_snapshot(root)
    shutil.rmtree(staging)
    logger.info(
        "Stored Screener data for %s symbols; %s failed with audit reasons",
        manifest["successful_symbol_count"],
        manifest["failed_symbol_count"],
    )
    return manifest


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    arguments = parse_arguments()
    if arguments.mode == "validate":
        result = validate_snapshot()
        logger.info(
            "Validated Screener snapshot generated %s for %s symbols",
            result["generated_at"],
            result["successful_symbol_count"],
        )
    else:
        refresh(
            batch_size=arguments.batch_size,
            sleep_seconds=arguments.sleep_seconds,
            restart=arguments.restart,
        )
