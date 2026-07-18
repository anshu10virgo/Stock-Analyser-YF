from core import scanner
from core.data_loader import DataLoader
from core.indicators import Indicators
from core.golden_cross import GoldenCrossDetector
from core.scanner import StockScanner
from core.slope_analyzer import SlopeAnalyzer

symbols = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "AAVAS.NS",
    "PAISALO.NS",
    "SONATSOFTW.NS"
]

data = DataLoader.download_batch(
    symbols
)

for symbol in symbols:

    df = DataLoader.get_symbol_history(
        data,
        symbol
    )

    if df.empty:
        continue

    df = Indicators.add_moving_averages(
        df,
        50,
        200
    )

    cross = (
        GoldenCrossDetector.find_cross(
            df,
            60,
            20
        )
    )

    slope = (
        SlopeAnalyzer.calculate_slope(
            df["MA_LONG"],
            20
        )
    )

    print(symbol)
    print(cross)
    print(slope)

    scanner = StockScanner(
        short_ma=50,
        long_ma=200,
        max_cross_age=60,
        pre_cross_days=20,
        slope_lookback=20,
        max_distance=5
    )

results = scanner.scan(symbols)
print("Scanner Results:")
print(results)
