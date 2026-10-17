"""Compare local and cloud India data, scanner output, and Backtest signals."""

from __future__ import annotations

import json
import argparse
import sys
import tomllib
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from models.scan_config import ScanConfig
from services.backtest_service import BacktestService
from services.data_source import SNAPSHOT_SOURCE, build_data_services
from services.scan_service import ScanService
from services.snapshot_storage import LocalSnapshotStorage, ScopedSnapshotStorage
from services.stock_universe import StockUniverse
from services.storage_config import configured_cloud_storage


def verify(root_layout=False, data_root=PROJECT_ROOT, snapshot_id=""):
    with (PROJECT_ROOT / ".streamlit/secrets.toml").open("rb") as stream:
        configuration = tomllib.load(stream)["storage"]
    if root_layout:
        configuration["prefix"] = ""
    if snapshot_id:
        configuration["snapshot_ids"] = {"IN": snapshot_id}
    cloud = configured_cloud_storage(configuration, PROJECT_ROOT)
    local = LocalSnapshotStorage(data_root)
    universes = [StockUniverse(PROJECT_ROOT, ScopedSnapshotStorage(storage, "data/stock_universe"))
                 for storage in (local, cloud)]
    frames = [pd.read_csv(universe.active_file()) for universe in universes]
    pd.testing.assert_frame_equal(*frames)
    symbols = frames[0]["Symbol"].head(3).tolist()
    providers = [build_data_services(SNAPSHOT_SOURCE, PROJECT_ROOT, storage) for storage in (local, cloud)]
    scans, signals = [], []
    config = ScanConfig(50, 200, 80, 60, 10, 10, adjusted_prices=False)
    for services in providers:
        services.history.fallback = None
        services.fundamentals.fallback = None
        services.industry_valuation.fallback = None
        batch = services.history.download_batch(symbols, years=10, adjusted_prices=False)
        scan = ScanService(config, services.history, services.fundamentals,
                           services.industry_valuation, services.screener).scan(symbols)
        scans.append(scan.as_dataframes())
        engine = BacktestService(config, services.screener)
        signals.append({symbol: engine.replay_symbol(
            symbol, services.history.get_symbol_history(batch, symbol)
        ).signals for symbol in symbols})
    for group in scans[0]:
        pd.testing.assert_frame_equal(scans[0][group], scans[1][group])
    if signals[0] != signals[1]:
        raise AssertionError("Cloud and local Backtest signals differ")
    for symbol in symbols:
        batches = [services.history.download_batch([symbol], years=10) for services in providers]
        pd.testing.assert_frame_equal(*batches)
        if providers[0].fundamentals.get_fundamentals(symbol) != providers[1].fundamentals.get_fundamentals(symbol):
            raise AssertionError("Cloud and local fundamentals differ")
        pd.testing.assert_frame_equal(*[services.screener.valuation_history(symbol) for services in providers])
    print(json.dumps({"snapshot_id": cloud.snapshot_id, "universe_rows": len(frames[0]),
                      "compared_symbols": symbols, "scan_and_backtest_match": True,
                      "backtest_signals": sum(len(rows) for rows in signals[0].values())}, indent=2))
    return cloud.snapshot_id


def check_app(snapshot_id, root_layout=False):
    """Exercise the real Setup page before changing local app configuration."""
    from streamlit.testing.v1 import AppTest

    with (PROJECT_ROOT / ".streamlit/secrets.toml").open("rb") as stream:
        configuration = dict(tomllib.load(stream)["storage"])
    configuration["provider"] = "r2"
    if root_layout:
        configuration["prefix"] = ""
    configuration["snapshot_ids"] = {"IN": snapshot_id}
    app = AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=90)
    app.secrets["storage"] = configuration
    app.run()
    if app.exception or app.session_state["selected_market_data_source"] != SNAPSHOT_SOURCE:
        raise AssertionError("Cloud Setup page did not load")
    print("Cloud Setup page loaded with cloud snapshot selected.")
    app.radio[0].set_value("2. Strategy").run()
    source = next((metric for metric in app.metric if metric.label == "Data source"), None)
    if app.exception or source is None or source.value != "Cloud snapshot":
        raise AssertionError("Strategy page did not identify cloud storage")
    print("Strategy page identifies the data source as Cloud snapshot.")


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--app", action="store_true", help="Also check the Setup page with R2 enabled")
        parser.add_argument("--root-layout", action="store_true", help="Check markets/ directly under the bucket")
        parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT,
                            help="Compare against an isolated refresh staging root")
        parser.add_argument("--snapshot-id", default="", help="Compare against the exact downloaded snapshot")
        arguments = parser.parse_args()
        snapshot_id = verify(arguments.root_layout, arguments.data_root, arguments.snapshot_id)
        if arguments.app:
            check_app(snapshot_id, arguments.root_layout)
    except Exception:
        print("Cloud/local comparison failed; application storage was not changed.", file=sys.stderr)
        sys.exit(1)
