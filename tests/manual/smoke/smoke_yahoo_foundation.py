"""Manual scanner foundation smoke check.

The executable body is guarded so pytest collection never performs live Yahoo
requests. Run this file directly when the manual network smoke check is needed.
"""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = PROJECT_ROOT / "src"
if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from stock_analyser.application.commands.run_scan import RunScanCommand
from stock_analyser.application.workflows.scan_workflow import ScanWorkflow
from stock_analyser.domain.scanning.indicators import (
    GoldenCrossDetector,
    Indicators,
    SlopeAnalyzer,
)
from stock_analyser.domain.scanning.models import ScanConfig
from stock_analyser.infrastructure.data_services import LIVE_SOURCE, build_data_services
from stock_analyser.infrastructure.local.data_loader import DataLoader


SYMBOLS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "AAVAS.NS",
    "PAISALO.NS",
    "SONATSOFTW.NS",
]


def main() -> None:
    data = DataLoader.download_batch(SYMBOLS)

    for symbol in SYMBOLS:
        frame = DataLoader.get_symbol_history(data, symbol)
        if frame.empty:
            continue
        frame = Indicators.add_moving_averages(frame, 50, 200)
        cross = GoldenCrossDetector.find_cross(frame, 80)
        slope = SlopeAnalyzer.calculate_slope(frame["MA_LONG"], 20)
        print(symbol)
        print(cross)
        print(slope)

    config = ScanConfig(
        short_ma=50,
        long_ma=200,
        max_cross_age=80,
        min_long_ma_decline_duration=60,
        min_long_ma_decline=10,
        max_price_premium=10,
    )
    services = build_data_services(LIVE_SOURCE, PROJECT_ROOT)
    results = ScanWorkflow(services).execute(
        RunScanCommand.create(SYMBOLS, config)
    ).run.as_dataframes()
    print("Scanner Results:")
    print(results)


if __name__ == "__main__":
    main()
