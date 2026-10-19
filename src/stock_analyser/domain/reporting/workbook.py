"""Pure workbook data preparation for completed scan reports."""

from __future__ import annotations

from datetime import datetime

import pandas as pd


OPTIONAL_FILTER_LABELS = {
    "relative_industry_pe": "Relative Industry P/E",
    "historical_stock_pe": "P/E vs. Historical Stock P/E",
    "peg_ratio": "PEG Ratio",
    "profit_growth": "Multi-Period Profit Growth",
    "eps_growth": "Multi-Period EPS Growth",
    "sales_growth": "Multi-Period Sales / Revenue Growth",
    "return_on_equity": "Return on Equity (ROE)",
    "debt_to_equity": "Debt-to-Equity (D/E) Ratio",
    "market_cap": "Market Capitalisation Buckets",
}

SETTING_LABELS = (
    ("stock_market", "Stock market"),
    ("market_data_source", "Market-data source"),
    ("stock_count", "Stocks analysed"),
    ("adjusted_prices", "Use adjusted prices"),
    ("short_ma", "Short-term moving average (days)"),
    ("long_ma", "Long-term moving average (days)"),
    ("cross_age", "Golden Cross maximum age (calendar days)"),
    ("min_long_ma_decline_duration", "Minimum high-to-trough decline duration (trading sessions)"),
    ("min_long_ma_decline", "Minimum Long MA decline from 52-week high (%)"),
    ("max_price_premium", "Maximum price above Long MA (%)"),
    ("include_impending_crosses", "Include Impending Golden Cross"),
    ("impending_max_gap_pct", "Maximum Short-to-Long MA gap (%)"),
    ("pre_cross_validation_sessions", "Pre-cross validation period (trading sessions)"),
)


def filter_records(
    settings: dict,
    scan_time: datetime,
    *,
    market_data_source_label: str | None = None,
) -> list[dict]:
    rows = [{"Setting": "Scan date and time", "Value": scan_time.isoformat()}]
    for key, label in SETTING_LABELS:
        value = settings.get(key, "Not recorded")
        if key == "market_data_source" and market_data_source_label is not None:
            value = market_data_source_label
        if isinstance(value, bool):
            value = "Yes" if value else "No"
        rows.append({"Setting": label, "Value": value})

    selected = settings.get("optional_filters", ())
    rows.append({"Setting": "Optional filters selected", "Value": len(selected)})
    for index, configured in enumerate(selected, start=1):
        key = configured.get("key", "")
        rows.append(
            {
                "Setting": f"Optional filter {index}",
                "Value": OPTIONAL_FILTER_LABELS.get(key, key or "Unknown"),
            }
        )
        for field, value in configured.items():
            if field == "key":
                continue
            if isinstance(value, (list, tuple)):
                value = ", ".join(map(str, value)) or "None"
            rows.append(
                {
                    "Setting": f"Optional filter {index} — {field.replace('_', ' ').title()}",
                    "Value": "Not set" if value is None else value,
                }
            )
    return rows


def export_results(frame: pd.DataFrame) -> pd.DataFrame:
    exported = frame.copy()
    if "market_cap" in exported:
        exported["market_cap"] = pd.to_numeric(
            exported["market_cap"], errors="coerce"
        ).div(10_000_000)
        exported.rename(columns={"market_cap": "Market Cap (₹ Cr)"}, inplace=True)
    exported.rename(
        columns={
            column: column.replace("_", " ").title()
            for column in exported.columns
            if column != "Market Cap (₹ Cr)"
        },
        inplace=True,
    )
    for column in exported.columns:
        exported[column] = exported[column].map(
            lambda value: ", ".join(map(str, value))
            if isinstance(value, (list, tuple))
            else value
        )
    return exported


def workbook_frames(
    settings: dict,
    scan_time: datetime,
    post_cross: pd.DataFrame,
    impending: pd.DataFrame,
    *,
    market_data_source_label: str | None = None,
) -> dict[str, pd.DataFrame]:
    return {
        "Filters": pd.DataFrame(
            filter_records(
                settings,
                scan_time,
                market_data_source_label=market_data_source_label,
            )
        ),
        "Post Golden Cross": export_results(post_cross),
        "Impending Golden Cross": export_results(impending),
    }


__all__ = [
    "OPTIONAL_FILTER_LABELS",
    "SETTING_LABELS",
    "export_results",
    "filter_records",
    "workbook_frames",
]
