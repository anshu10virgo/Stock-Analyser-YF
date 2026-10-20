"""Manual scanner foundation smoke check.

The executable body is guarded so pytest collection never performs live Yahoo
requests. Run this file directly when the manual network smoke check is needed.
"""

from core.data_loader import DataLoader
from core.golden_cross import GoldenCrossDetector
from core.indicators import Indicators
from core.scanner import StockScanner
from core.slope_analyzer import SlopeAnalyzer


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

    scanner = StockScanner(
        short_ma=50,
        long_ma=200,
        max_cross_age=80,
        min_long_ma_decline_duration=60,
        min_long_ma_decline=10,
        max_price_premium=10,
    )
    results = scanner.scan(SYMBOLS)
    print("Scanner Results:")
    print(results)


if __name__ == "__main__":
    main()
