"""Queries for one stock in the current bounded result sets."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


RESULT_SETS = (
    ("scan_results", "Post Golden Cross"),
    ("scan_impending_results", "Impending Golden Cross"),
    ("scan_failed_results", "Failed"),
)


def get_stock_status(state: Mapping, stock_query: str) -> dict:
    query = stock_query.strip().upper()
    if not query:
        return {"available": False, "reason": "No stock was provided."}
    for key, status in RESULT_SETS:
        frame = state.get(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        symbol_column = "symbol" if "symbol" in frame.columns else "Stock"
        company_column = (
            "company_name" if "company_name" in frame.columns else "Company"
        )
        symbol_match = (
            frame[symbol_column]
            .astype(str)
            .str.upper()
            .str.contains(query, regex=False)
        )
        company_match = (
            frame[company_column]
            .astype(str)
            .str.upper()
            .str.contains(query, regex=False)
            if company_column in frame.columns
            else False
        )
        matches = frame.loc[symbol_match | company_match]
        if matches.empty:
            continue
        record = matches.iloc[0].where(pd.notna(matches.iloc[0]), None).to_dict()
        return {"available": True, "status": status, "record": record}
    return {
        "available": False,
        "reason": "The stock is not available in the current local results.",
    }


def get_calculation_trace(state: Mapping, symbol: str) -> dict:
    status = get_stock_status(state, symbol)
    if not status.get("available"):
        return {"available": False, "reason": status.get("reason")}
    record = status["record"]
    close = _number(record.get("close"))
    short_ma = _number(record.get("ma_short"))
    long_ma = _number(record.get("ma_long"))
    return {
        "available": True,
        "symbol": symbol,
        "price_premium": {
            "formula": "(Close - Long MA) / Long MA × 100",
            "inputs": {"close": close, "long_ma": long_ma},
            "value": record.get("price_above_long_ma_percent"),
        },
        "ma_gap": {
            "formula": "(Long MA - Short MA) / Long MA × 100",
            "inputs": {"short_ma": short_ma, "long_ma": long_ma},
            "value": record.get("impending_gap_percent"),
        },
        "slope": {
            "formula": "Moving-average change over the configured five-session window",
            "inputs": {
                "short_ma_slope": record.get("short_ma_slope"),
                "long_ma_slope": record.get("long_ma_slope"),
            },
        },
        "pe": {
            "formula": "Share price / trailing earnings per share",
            "value": record.get("pe"),
            "source": record.get("pe_source"),
        },
    }


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None and not pd.isna(value) else None
    except (TypeError, ValueError):
        return None
