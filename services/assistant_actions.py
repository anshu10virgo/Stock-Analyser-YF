"""Local intent proposals and confirmed workflow handoffs for Ticksy."""

from __future__ import annotations

import re
from collections.abc import Mapping, MutableMapping

from models.assistant_action import AssistantAction
from models.optional_filter import (
    DEBT_TO_EQUITY,
    EPS_GROWTH,
    HISTORICAL_STOCK_PE,
    MARKET_CAP,
    PEG_RATIO,
    PROFIT_GROWTH,
    RELATIVE_INDUSTRY_PE,
    RETURN_ON_EQUITY,
    SALES_GROWTH,
)
from models.scan_config import ScanConfig
from services.data_source import LIVE_SOURCE
from ui.sidebar import OPTIONAL_SEQUENCE_KEY, default_scan_settings


PERIODS = ("1Y", "3Y", "5Y", "10Y")


def current_settings(session_state: Mapping) -> dict:
    """Use the active saved strategy where available, otherwise app defaults."""
    settings = default_scan_settings()
    settings.update(session_state.get("scan_settings") or session_state.get("backtest_settings") or {})
    for field in tuple(settings):
        widget_value = session_state.get(f"scan_config_{field}")
        if widget_value is not None:
            settings[field] = widget_value
    return settings


def _symbol_from_prompt(prompt: str, symbols: list[str]) -> str | None:
    upper = prompt.upper()
    for symbol in symbols:
        ticker = symbol.split(".", maxsplit=1)[0].upper()
        if symbol.upper() in upper or re.search(rf"\b{re.escape(ticker)}\b", upper):
            return symbol
    return None


def _period_from_prompt(prompt: str) -> str:
    upper = prompt.upper()
    aliases = {
        "ONE YEAR": "1Y", "1 YEAR": "1Y", "THREE YEARS": "3Y", "3 YEARS": "3Y",
        "FIVE YEARS": "5Y", "5 YEARS": "5Y", "TEN YEARS": "10Y", "10 YEARS": "10Y",
    }
    return next((period for phrase, period in aliases.items() if phrase in upper), next((period for period in PERIODS if period in upper), "5Y"))


def propose_action(prompt: str, session_state: Mapping) -> AssistantAction | None:
    """Recognise only safe workflow requests; all executions need confirmation."""
    lower = prompt.lower()
    settings = current_settings(session_state)
    symbols = list(session_state.get("selected_symbols", []))
    requested_symbol = _symbol_from_prompt(prompt, symbols)
    if requested_symbol and "chart" in lower and any(term in lower for term in ("open", "show", "view")):
        return AssistantAction("navigation", f"Open the Results chart for {requested_symbol}.", symbol=requested_symbol, target="4. Results")
    navigation = _navigation_target(lower)
    if navigation:
        return AssistantAction("navigation", f"Open {navigation[1]}.", target=navigation[0])
    if "reset strategy" in lower or "system defaults" in lower:
        return AssistantAction("reset_strategy", "Reset the Strategy page to system defaults.", settings=default_scan_settings())
    changed = _apply_requested_settings(lower, settings)
    if changed:
        try:
            _config(settings).validate()
        except ValueError:
            return None
        return AssistantAction("strategy", f"Apply requested strategy changes: {', '.join(changed)}.", settings=settings)
    if "backtest" in lower or "back test" in lower or "test" in lower and any(period in lower for period in ("year", "1y", "3y", "5y", "10y")):
        symbol = _symbol_from_prompt(prompt, symbols)
        if not symbol:
            return None
        period = _period_from_prompt(prompt)
        return AssistantAction("backtest", f"Run a {period} Backtest for {symbol} using the active strategy.", symbol=symbol, period=period, settings=settings)
    if "run scan" in lower or "scan the market" in lower or "market scan" in lower or "scan all" in lower:
        if not symbols:
            return None
        count = min(int(session_state.get("stock_count", 2000)), len(symbols))
        return AssistantAction("scan", f"Run the active strategy for {count:,} selected stocks.", settings=settings)
    return None


def _apply_requested_settings(prompt: str, settings: dict) -> list[str]:
    """Apply recognised existing Strategy settings to a proposal copy."""
    changed: list[str] = []
    ma_match = re.search(r"\b(\d{2,4})\s*(?:/|and)\s*(\d{2,4})\b", prompt)
    if ma_match and any(term in prompt for term in ("ma", "moving average", "strategy")):
        settings["short_ma"] = int(ma_match.group(1))
        settings["long_ma"] = int(ma_match.group(2))
        changed.append(f"moving averages {settings['short_ma']} / {settings['long_ma']}")
    changes = (
        ("cross_age", r"cross age\s*(?:of|to|under|below)?\s*(\d+)", "cross age"),
        ("max_price_premium", r"(?:premium|price premium)\s*(?:of|to|under|below)?\s*(\d+(?:\.\d+)?)\s*%?", "maximum price premium"),
        ("min_long_ma_decline", r"(?:ma )?decline\s*(?:of|to|above)?\s*(\d+(?:\.\d+)?)\s*%?", "minimum Long MA decline"),
        ("min_long_ma_decline_duration", r"decline duration\s*(?:of|to|above)?\s*(\d+)", "minimum decline duration"),
        ("impending_max_gap_pct", r"(?:impending )?(?:ma )?gap\s*(?:of|to|under|below)?\s*(\d+(?:\.\d+)?)\s*%?", "maximum Impending MA gap"),
        ("pre_cross_validation_sessions", r"pre[- ]?cross(?: validation)?\s*(?:of|to)?\s*(\d+)", "pre-cross validation sessions"),
    )
    for field, pattern, label in changes:
        match = re.search(pattern, prompt)
        if match:
            settings[field] = float(match.group(1)) if "." in match.group(1) else int(match.group(1))
            changed.append(f"{label} {settings[field]}")
    if "include impending" in prompt or "show impending" in prompt:
        settings["include_impending_crosses"] = True
        changed.append("include Impending Golden Cross stocks")
    if "exclude impending" in prompt or "hide impending" in prompt or "no impending" in prompt:
        settings["include_impending_crosses"] = False
        changed.append("exclude Impending Golden Cross stocks")
    if "adjusted price" in prompt:
        settings["adjusted_prices"] = "unadjusted" not in prompt
        changed.append("adjusted prices" if settings["adjusted_prices"] else "unadjusted prices")
    optional = _optional_filter_from_prompt(prompt)
    if optional:
        filters = [value for value in settings.get("optional_filters", []) if value["key"] != optional["key"]]
        filters.append(optional)
        settings["optional_filters"] = filters
        changed.append(f"{optional['key']} filter")
    return list(dict.fromkeys(changed))


def _optional_filter_from_prompt(prompt: str) -> dict | None:
    """Translate a small set of existing optional-filter phrases safely."""
    if "p/e below industry" in prompt or "pe below industry" in prompt:
        return {"key": RELATIVE_INDUSTRY_PE}
    if "p/e below historical" in prompt or "pe below historical" in prompt:
        return {"key": HISTORICAL_STOCK_PE}
    buckets = [bucket for bucket in ("large", "mid", "small", "micro") if f"{bucket} cap" in prompt]
    if buckets:
        return {"key": MARKET_CAP, "market_cap_buckets": buckets}
    patterns = (
        (PEG_RATIO, r"peg(?: ratio)?\s*(?:below|under|at or below|<=)\s*(\d+(?:\.\d+)?)"),
        (RETURN_ON_EQUITY, r"roe\s*(?:above|over|at least|>=)\s*(\d+(?:\.\d+)?)"),
        (DEBT_TO_EQUITY, r"(?:debt(?: to equity)?|d/e)\s*(?:below|under|at or below|<=)\s*(\d+(?:\.\d+)?)"),
        (PROFIT_GROWTH, r"profit growth\s*(?:above|over|at least|>=)\s*(\d+(?:\.\d+)?)\s*%?"),
        (EPS_GROWTH, r"eps growth\s*(?:above|over|at least|>=)\s*(\d+(?:\.\d+)?)\s*%?"),
        (SALES_GROWTH, r"(?:sales|revenue) growth\s*(?:above|over|at least|>=)\s*(\d+(?:\.\d+)?)\s*%?"),
    )
    for key, pattern in patterns:
        match = re.search(pattern, prompt)
        if match:
            return {"key": key, "threshold": float(match.group(1))}
    return None


def _navigation_target(prompt: str) -> tuple[str, str] | None:
    """Map read-only navigation requests to the existing workflow sections."""
    targets = (
        ("setup", "1. Setup", "Setup"),
        ("strategy", "2. Strategy", "Strategy"),
        ("live scan", "3. Live Scan", "Live Scan"),
        ("results", "4. Results", "Results"),
        ("backtester", "5. Backtester", "Backtester"),
    )
    if not any(word in prompt for word in ("open", "go to", "show", "navigate")):
        return None
    for phrase, section, label in targets:
        if phrase in prompt:
            return section, label
    return None


def _config(settings: Mapping) -> ScanConfig:
    return ScanConfig(
        settings["short_ma"], settings["long_ma"], settings["cross_age"],
        settings["min_long_ma_decline_duration"], settings["min_long_ma_decline"],
        settings["max_price_premium"], settings["include_impending_crosses"],
        settings["impending_max_gap_pct"], settings["pre_cross_validation_sessions"],
        adjusted_prices=settings["adjusted_prices"],
    )


def apply_action(action: AssistantAction, session_state: MutableMapping) -> str:
    """Apply one user-confirmed action through the existing app workflow state."""
    settings = action.settings or current_settings(session_state)
    _config(settings).validate()
    if action.kind == "strategy":
        for field, value in settings.items():
            if field != "optional_filters":
                session_state[f"scan_config_{field}"] = value
        session_state[OPTIONAL_SEQUENCE_KEY] = [value["key"] for value in settings.get("optional_filters", [])]
        for values in settings.get("optional_filters", []):
            for field, value in values.items():
                if field != "key":
                    session_state[f"scan_optional_{values['key']}_{field}"] = value
        session_state["_next_app_section"] = "2. Strategy"
        return "Strategy changes were applied."
    if action.kind == "reset_strategy":
        for field, value in settings.items():
            if field != "optional_filters":
                session_state[f"scan_config_{field}"] = value
        session_state[OPTIONAL_SEQUENCE_KEY] = []
        session_state["_next_app_section"] = "2. Strategy"
        return "Strategy settings were reset to system defaults."
    if action.kind == "navigation" and action.target:
        if action.symbol:
            session_state["ticksy_selected_symbol"] = action.symbol
        session_state["_next_app_section"] = action.target
        return f"Opening {action.target.split('. ', maxsplit=1)[1]}."
    if action.kind == "scan":
        symbols = list(session_state.get("selected_symbols", []))
        count = min(int(session_state.get("stock_count", 2000)), len(symbols))
        session_state["pending_scan"] = {
            "symbols": symbols[:count],
            "settings": settings,
            "market_data_source": session_state.get("selected_market_data_source", LIVE_SOURCE),
        }
        session_state["_next_app_section"] = "3. Live Scan"
        return "The confirmed market scan is ready to run."
    if action.kind == "backtest" and action.symbol and action.period:
        session_state["backtest_settings"] = settings
        session_state["ticksy_backtest_request"] = {"symbols": [action.symbol], "period": action.period}
        session_state["_next_app_section"] = "5. Backtester"
        return "The confirmed Backtest is ready to run."
    raise ValueError("Ticksy action is not supported.")
