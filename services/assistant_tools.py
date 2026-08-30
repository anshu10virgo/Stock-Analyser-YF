"""Read-only local data tools used by Ticksy prompts and future tool calls."""

from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from math import ceil
from pathlib import Path

import pandas as pd


RESULT_SETS = (
    ("scan_results", "Post Golden Cross"),
    ("scan_impending_results", "Impending Golden Cross"),
    ("scan_failed_results", "Failed"),
)

PARAMETER_HELP = {
    "slope": "Slope shows how quickly a moving average is changing each session. A positive slope means it is rising.",
    "ma decline": "MA decline measures how far the Long MA fell from its 52-week high before recovering.",
    "cross age": "Cross age is the number of calendar days since the confirmed Golden Cross.",
    "premium": "Premium is how far the latest close is above the Long MA. The strategy limits this to avoid chasing an extended price.",
    "p/e": "P/E compares the current share price with trailing earnings per share. It is valuation context, not a Golden Cross rule unless an optional filter uses it.",
    "gap": "MA gap is the percentage distance between the Short MA and Long MA. A smaller positive gap means an Impending cross is closer.",
}


def active_strategy(session_state: Mapping) -> dict:
    """Return the active saved scan or Backtester settings."""
    return dict(session_state.get("scan_settings") or session_state.get("backtest_settings") or {})


def scan_summary(session_state: Mapping) -> dict:
    """Return local result-group counts and the completed scan timestamp."""
    def count(key: str) -> int:
        frame = session_state.get(key)
        return int(len(frame)) if isinstance(frame, pd.DataFrame) else 0

    return {
        "scan_time": str(session_state.get("scan_time")) if session_state.get("scan_time") else None,
        "post_golden_cross_count": count("scan_results"),
        "impending_golden_cross_count": count("scan_impending_results"),
        "failed_count": count("scan_failed_results"),
    }


def stock_status(session_state: Mapping, stock_query: str) -> dict:
    """Return a rule-value record for one locally available stock query."""
    query = stock_query.strip().upper()
    if not query:
        return {"available": False, "reason": "No stock was provided."}
    for key, status in RESULT_SETS:
        frame = session_state.get(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        symbol_column = "symbol" if "symbol" in frame.columns else "Stock"
        company_column = "company_name" if "company_name" in frame.columns else "Company"
        symbol_match = frame[symbol_column].astype(str).str.upper().str.contains(query, regex=False)
        company_match = (
            frame[company_column].astype(str).str.upper().str.contains(query, regex=False)
            if company_column in frame.columns
            else False
        )
        matches = frame.loc[symbol_match | company_match]
        if matches.empty:
            continue
        record = matches.iloc[0].where(pd.notna(matches.iloc[0]), None).to_dict()
        return {"available": True, "status": status, "record": record}
    return {"available": False, "reason": "The stock is not available in the current local results."}


def stock_query_from_prompt(session_state: Mapping, prompt: str) -> str | None:
    """Find an available result symbol referenced anywhere in a user prompt."""
    upper = prompt.upper()
    for key, _ in RESULT_SETS:
        frame = session_state.get(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        symbol_column = "symbol" if "symbol" in frame.columns else "Stock"
        for symbol in frame[symbol_column].dropna().astype(str):
            ticker = symbol.split(".", maxsplit=1)[0].upper()
            if symbol.upper() in upper or ticker in upper:
                return symbol
    return None


def symbols_from_prompt(session_state: Mapping, prompt: str) -> list[str]:
    """Return all unique local result symbols mentioned in a prompt."""
    upper = prompt.upper()
    matches: list[str] = []
    for key, _ in RESULT_SETS:
        frame = session_state.get(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            continue
        symbol_column = "symbol" if "symbol" in frame.columns else "Stock"
        company_column = "company_name" if "company_name" in frame.columns else None
        for _, row in frame.iterrows():
            symbol = str(row.get(symbol_column, ""))
            ticker = symbol.split(".", maxsplit=1)[0].upper()
            company = str(row.get(company_column, "")).upper() if company_column else ""
            if symbol.upper() in upper or ticker in upper or (company and company in upper):
                if symbol and symbol not in matches:
                    matches.append(symbol)
    return matches


def universe_lookup(session_state: Mapping, prompt: str) -> dict:
    """Return company and current-result industry details from local universe data."""
    upper = prompt.upper()
    symbol = next(
        (
            candidate
            for candidate in session_state.get("selected_symbols", [])
            if candidate.upper() in upper or candidate.split(".", maxsplit=1)[0].upper() in upper
        ),
        None,
    )
    if not symbol:
        return {"available": False, "reason": "No selected-universe symbol was recognised."}
    universe = _universe_records()
    record = universe.get(symbol)
    status = stock_status(session_state, symbol)
    result_record = status.get("record", {}) if status.get("available") else {}
    return {
        "available": record is not None,
        "symbol": symbol,
        "company_name": (record or {}).get("Company Name") or result_record.get("company_name"),
        "market_cap_rank": (record or {}).get("Market Cap Rank"),
        "industry": result_record.get("industry"),
        "current_scan_status": status.get("status") if status.get("available") else None,
    }


def backtest_records(session_state: Mapping, symbols: list[str] | None = None) -> list[dict]:
    """Return local Backtester records, optionally limited to symbols."""
    frame = session_state.get("backtest_results")
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    selected = frame
    if symbols and "Stock" in frame.columns:
        selected = frame.loc[frame["Stock"].isin(symbols)]
    return selected.where(pd.notna(selected), None).to_dict("records")


def market_condition_summary(session_state: Mapping) -> dict:
    """Summarise the current local scan without comparing historical snapshots."""
    summary = scan_summary(session_state)
    passed = session_state.get("scan_results")
    impending = session_state.get("scan_impending_results")
    failed = session_state.get("scan_failed_results")
    above_long = 0
    for frame in (passed, impending):
        if isinstance(frame, pd.DataFrame) and "price_above_long_ma_percent" in frame:
            above_long += int((pd.to_numeric(frame["price_above_long_ma_percent"], errors="coerce") > 0).sum())
    recent_crosses = 0
    if isinstance(passed, pd.DataFrame) and "days_since_cross" in passed:
        recent_crosses = int((pd.to_numeric(passed["days_since_cross"], errors="coerce") <= 20).sum())
    summary.update(
        {
            "above_long_ma_count": above_long,
            "recent_cross_count": recent_crosses,
            "failed_with_reason_count": int(len(failed)) if isinstance(failed, pd.DataFrame) else 0,
        }
    )
    return summary


def crossover_window(session_state: Mapping, symbol: str) -> dict:
    """Estimate a conditional crossover window from locally stored MA values."""
    status = stock_status(session_state, symbol)
    if not status.get("available") or status.get("status") != "Impending Golden Cross":
        return {"available": False, "reason": "An Impending Golden Cross record is required."}
    record = status["record"]
    short_ma = _number(record.get("ma_short"))
    long_ma = _number(record.get("ma_long"))
    short_slope = _number(record.get("short_ma_slope"))
    long_slope = _number(record.get("long_ma_slope"))
    if None in (short_ma, long_ma, short_slope, long_slope):
        return {"available": False, "reason": "MA values or slopes are unavailable."}
    convergence = short_slope - long_slope
    gap = long_ma - short_ma
    if gap <= 0 or convergence <= 0:
        return {"available": False, "reason": "The Short MA is not converging toward the Long MA at a positive rate."}
    return {
        "available": True,
        "gap": gap,
        "convergence_per_session": convergence,
        "estimated_sessions": ceil(gap / convergence),
    }


def calculation_trace(session_state: Mapping, symbol: str) -> dict:
    """Return local formula inputs for key displayed technical measures."""
    status = stock_status(session_state, symbol)
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
            "inputs": {"short_ma_slope": record.get("short_ma_slope"), "long_ma_slope": record.get("long_ma_slope")},
        },
        "pe": {"formula": "Share price / trailing earnings per share", "value": record.get("pe"), "source": record.get("pe_source")},
    }


def parameter_help(session_state: Mapping, prompt: str, symbol: str | None = None) -> dict:
    """Return plain-language parameter definitions and current local values."""
    lower = prompt.lower()
    selected = [name for name in PARAMETER_HELP if name in lower]
    if not selected:
        selected = list(PARAMETER_HELP)
    record = stock_status(session_state, symbol)["record"] if symbol and stock_status(session_state, symbol).get("available") else {}
    values = {
        "slope": record.get("short_ma_slope"),
        "ma decline": record.get("long_ma_decline_percent"),
        "cross age": record.get("days_since_cross"),
        "premium": record.get("price_above_long_ma_percent"),
        "p/e": record.get("pe"),
        "gap": record.get("impending_gap_percent"),
    }
    return {name: {"meaning": PARAMETER_HELP[name], "current_value": values[name]} for name in selected}


def data_dictionary() -> dict[str, str]:
    """Return a concise dictionary for the common Ticksy result fields."""
    return {
        "Post Golden Cross": "A confirmed recent Short-MA move above the Long MA that passed the active rules.",
        "Impending Golden Cross": "A near-cross setup that passed the active proximity and trend checks but is not confirmed.",
        "Short MA slope": "Five-session change in the Short moving average.",
        "Long MA decline": "Decline from the Long MA 52-week high to its trough before recovery.",
        "Price premium": "Latest close above the Long MA as a percentage.",
        "P/E": "Share price divided by trailing earnings per share when available.",
    }


def _number(value: object) -> float | None:
    try:
        return float(value) if value is not None and not pd.isna(value) else None
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def _universe_records() -> dict[str, dict]:
    """Load the manifest-selected local stock universe once per process."""
    root = Path(__file__).resolve().parents[1] / "data" / "stock_universe"
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        frame = pd.read_csv(root / manifest["active_universe"])
    except (FileNotFoundError, KeyError, OSError, ValueError, json.JSONDecodeError):
        return {}
    return {str(record["Symbol"]): record for record in frame.to_dict("records")}
