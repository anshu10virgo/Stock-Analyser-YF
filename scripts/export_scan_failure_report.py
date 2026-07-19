"""Export a detailed Excel report for one configured stock scan."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.data_loader import DataLoader
from core.golden_cross import GoldenCrossDetector
from core.indicators import Indicators
from core.slope_analyzer import SlopeAnalyzer
from models.scan_config import ScanConfig
from models.scan_run import ScanRun
from services.scan_service import ScanService
from services.data_source import SNAPSHOT_SOURCE, build_data_services
from services.stock_universe import StockUniverse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_ROOT / "reports"
REPORT_TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
REPORT_FILE = REPORT_DIR / (
    f"scan_failures_1500_gc80_52week_m60_decline10_premium10_{REPORT_TIMESTAMP}.xlsx"
)


def _value(value, decimals: int = 4):
    """Convert numeric values to Excel-friendly rounded values."""
    if value is None or pd.isna(value):
        return None
    return round(float(value), decimals)


def _date(value):
    return value.date() if value is not None and not pd.isna(value) else None


def _metrics_row(service: ScanService, batch_data, symbol: str) -> dict:
    """Calculate audit metrics even when a stock failed an earlier rule."""
    row = {"symbol": symbol}
    history = service.data_provider.get_symbol_history(batch_data, symbol)
    if history.empty:
        row["data_status"] = "No complete market data"
        return row

    try:
        history = Indicators.add_moving_averages(
            history, service.config.short_ma, service.config.long_ma
        )
        latest = history.iloc[-1]
        previous = history.iloc[-2]
        row.update(
            {
                "data_status": "Available",
                "latest_date": _date(history.index[-1]),
                "close": _value(latest["Close"], 2),
                "short_ma": _value(latest["MA_SHORT"], 2),
                "previous_short_ma": _value(previous["MA_SHORT"], 2),
                "short_ma_daily_change": _value(
                    latest["MA_SHORT"] - previous["MA_SHORT"], 4
                ),
                "short_ma_5_session_slope": _value(
                    SlopeAnalyzer.calculate_slope(history["MA_SHORT"], 5), 4
                ),
                "short_ma_rising": bool(
                    SlopeAnalyzer.calculate_slope(history["MA_SHORT"], 5) > 0
                ),
                "long_ma": _value(latest["MA_LONG"], 2),
                "short_ma_above_long_ma": bool(
                    latest["MA_SHORT"] > latest["MA_LONG"]
                ),
                "close_above_long_ma": bool(latest["Close"] > latest["MA_LONG"]),
                "price_above_long_ma_percent": _value(
                    Indicators.distance_from_ma(latest["Close"], latest["MA_LONG"]), 2
                ),
            }
        )

        cross = GoldenCrossDetector.find_cross(
            history, service.config.max_cross_age
        )
        row.update(
            {
                "golden_cross_valid": cross["valid"],
                "golden_cross_date": _date(cross.get("cross_date")),
                "days_since_golden_cross": cross.get("days_since_cross"),
            }
        )

        reversal = service._long_ma_reversal(history)
        if reversal is None:
            row["long_ma_reversal_status"] = "Insufficient Long-MA history for 52-week high"
            return row

        (
            peak_value,
            peak_date,
            peak_age,
            trough_value,
            trough_date,
            decline_duration,
            decline_percent,
            recovery_slope,
            recovering,
        ) = reversal
        row.update(
            {
                "long_ma_reversal_status": "Calculated",
                "long_ma_52_week_high": _value(peak_value, 2),
                "long_ma_high_date": _date(peak_date),
                "long_ma_high_age_sessions": peak_age,
                "long_ma_trough": _value(trough_value, 2),
                "long_ma_trough_date": _date(trough_date),
                "long_ma_decline_duration_sessions": decline_duration,
                "long_ma_high_to_trough_decline_percent": _value(
                    decline_percent, 2
                ),
                "post_trough_5_session_slope": _value(recovery_slope, 4),
                "long_ma_recovering": recovering,
            }
        )
    except Exception as error:  # Keep the report useful if one calculation is bad.
        row["data_status"] = f"Metric calculation error: {error}"
    return row


def main() -> None:
    config = ScanConfig(
        short_ma=50,
        long_ma=200,
        max_cross_age=80,
        min_long_ma_decline_duration=60,
        min_long_ma_decline=10,
        max_price_premium=10,
    )
    universe = StockUniverse(
        PROJECT_ROOT / "data" / "stock_universe",
        PROJECT_ROOT / "stock_symbols.csv",
    )
    symbols = DataLoader.load_symbols(universe.active_file())[:1500]
    data_services = build_data_services(SNAPSHOT_SOURCE, PROJECT_ROOT)
    service = ScanService(
        config,
        data_provider=data_services.history,
        fundamentals_provider=data_services.fundamentals,
        industry_valuation_service=data_services.industry_valuation,
    )
    batch_data = service.data_provider.download_batch(
        symbols, years=3, adjusted_prices=False
    )
    run = ScanRun()
    audit_rows = []
    for symbol in symbols:
        service._scan_symbol(batch_data, symbol, run)
        audit_rows.append(_metrics_row(service, batch_data, symbol))

    results = run.as_dataframes()
    failures = results["failed"].merge(
        pd.DataFrame(audit_rows), on="symbol", how="left"
    )
    failures.sort_values(["stage", "reason", "symbol"], inplace=True)
    failure_counts = (
        failures.groupby(["stage", "reason", "check_type"], dropna=False)
        .size()
        .reset_index(name="failed_stocks")
        .sort_values("failed_stocks", ascending=False)
    )
    fundamentals_coverage = data_services.metadata.get("fundamentals_coverage", {})
    summary = pd.DataFrame(
        [
            ("Report generated", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            ("Universe file", str(universe.active_file().relative_to(PROJECT_ROOT))),
            ("Market-data access mode", data_services.metadata.get("access_mode")),
            ("Market-data upstream source", data_services.metadata.get("source")),
            ("Market-data snapshot date", data_services.metadata.get("last_trading_date")),
            ("Market-data manifest generated", data_services.metadata.get("generated_at")),
            ("Yahoo fallback requests", service.data_provider.market_data_metrics().get("fallback_requests")),
            ("Industry Yahoo fallback requests", service.industry_valuation_service.metrics().get("fallback_requests", 0)),
            ("Snapshot stocks with PE", fundamentals_coverage.get("pe")),
            ("Snapshot stocks with industry", fundamentals_coverage.get("industry")),
            ("Snapshot industry PE benchmarks", fundamentals_coverage.get("industries_with_valuations")),
            ("Symbols scanned", len(symbols)),
            ("Qualified stocks", len(results["passed"])),
            ("Failed stocks", len(failures)),
            ("Short MA", config.short_ma),
            ("Long MA", config.long_ma),
            ("Golden Cross maximum age (days)", config.max_cross_age),
            ("Minimum high-to-trough decline duration (sessions)", config.min_long_ma_decline_duration),
            ("Minimum Long-MA high-to-trough decline (%)", config.min_long_ma_decline),
            ("Maximum price premium above Long MA (%)", config.max_price_premium),
            ("Post-cross optional check", "Not enabled"),
        ],
        columns=["setting", "value"],
    )

    REPORT_DIR.mkdir(exist_ok=True)
    with pd.ExcelWriter(REPORT_FILE, engine="xlsxwriter", date_format="yyyy-mm-dd") as writer:
        summary.to_excel(writer, sheet_name="Scan Summary", index=False)
        failure_counts.to_excel(writer, sheet_name="Failure Summary", index=False)
        failures.to_excel(writer, sheet_name="Failed Stocks", index=False)
        results["passed"].to_excel(writer, sheet_name="Qualified Stocks", index=False)
        for sheet_name, frame in {
            "Scan Summary": summary,
            "Failure Summary": failure_counts,
            "Failed Stocks": failures,
            "Qualified Stocks": results["passed"],
        }.items():
            worksheet = writer.sheets[sheet_name]
            worksheet.freeze_panes(1, 0)
            worksheet.autofilter(0, 0, max(len(frame), 1), max(len(frame.columns) - 1, 0))
            for column, name in enumerate(frame.columns):
                width = min(max(len(str(name)) + 2, 14), 42)
                worksheet.set_column(column, column, width)

    print(REPORT_FILE)
    print(f"Failed stocks: {len(failures)}")
    print(f"Qualified stocks: {len(results['passed'])}")


if __name__ == "__main__":
    main()
