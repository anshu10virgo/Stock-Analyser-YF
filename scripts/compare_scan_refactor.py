"""Compare the refactored scanner with a committed baseline on one snapshot.

Run this after downloading the local R2 datasets. The script executes the
baseline ``services/scan_service.py`` from Git and the current facade against
the same ranked symbols, configuration, and immutable local snapshot.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import types
from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRE_REFACTOR_BASELINE = "1b6c390"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.data_loader import DataLoader
from models.scan_config import ScanConfig
from stock_analyser.infrastructure.data_services import (
    SNAPSHOT_SOURCE,
    build_data_services,
)
from services.stock_universe import StockUniverse
from stock_analyser.application.commands.run_scan import RunScanCommand
from stock_analyser.application.workflows.scan_workflow import ScanWorkflow


def _baseline_service(git_ref: str):
    source = subprocess.run(
        ["git", "show", f"{git_ref}:services/scan_service.py"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    module = types.ModuleType("scan_service_baseline")
    module.__file__ = f"{git_ref}:services/scan_service.py"
    exec(compile(source, module.__file__, "exec"), module.__dict__)
    return module.ScanService


def _scan_service(service_type, config: ScanConfig, symbols: list[str]):
    data = build_data_services(SNAPSHOT_SOURCE, PROJECT_ROOT)
    return service_type(
        config,
        data_provider=data.history,
        fundamentals_provider=data.fundamentals,
        industry_valuation_service=data.industry_valuation,
        screener_provider=data.screener,
    ).scan(symbols).as_dataframes()


def _scan_application(config: ScanConfig, symbols: list[str]):
    data = build_data_services(SNAPSHOT_SOURCE, PROJECT_ROOT)
    return ScanWorkflow(data).execute(
        RunScanCommand.create(symbols, config)
    ).run.as_dataframes()


def compare(git_ref: str, stock_count: int) -> None:
    universe = StockUniverse(PROJECT_ROOT / "data" / "stock_universe")
    symbols = DataLoader.load_symbols(universe.active_file())[:stock_count]
    config = ScanConfig(
        short_ma=50,
        long_ma=200,
        max_cross_age=80,
        min_long_ma_decline_duration=60,
        min_long_ma_decline=10,
        max_price_premium=10,
        include_impending_crosses=True,
    )
    baseline = _scan_service(_baseline_service(git_ref), config, symbols)
    current = _scan_application(config, symbols)
    for group in ("passed", "impending", "failed"):
        assert_frame_equal(
            baseline[group].reset_index(drop=True),
            current[group].reset_index(drop=True),
            check_dtype=False,
            check_exact=True,
        )
    print(
        "Scanner parity confirmed: "
        f"{len(symbols):,} symbols; "
        f"{len(current['passed']):,} Post-Cross; "
        f"{len(current['impending']):,} Impending; "
        f"{len(current['failed']):,} failed."
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", default=PRE_REFACTOR_BASELINE)
    parser.add_argument("--stock-count", type=int, default=1500)
    arguments = parser.parse_args()
    compare(arguments.baseline_ref, arguments.stock_count)


if __name__ == "__main__":
    main()
