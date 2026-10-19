"""Validate and apply user-confirmed strategy workflow changes."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from copy import deepcopy

from models.assistant_action import AssistantAction
from stock_analyser.domain.scanning.models import ScanConfig


DEFAULT_SCAN_SETTINGS = {
    "short_ma": 50,
    "long_ma": 200,
    "cross_age": 80,
    "max_price_premium": 10,
    "min_long_ma_decline_duration": 60,
    "min_long_ma_decline": 10,
    "include_impending_crosses": False,
    "impending_max_gap_pct": 10,
    "pre_cross_validation_sessions": 20,
    "optional_filters": [],
    "adjusted_prices": False,
}
OPTIONAL_SEQUENCE_KEY = "scan_config_optional_sequence"
LIVE_MARKET_DATA_SOURCE = "Live Yahoo Finance"


def default_scan_settings() -> dict:
    return deepcopy(DEFAULT_SCAN_SETTINGS)


def current_settings(session_state: Mapping) -> dict:
    settings = default_scan_settings()
    settings.update(
        session_state.get("scan_settings")
        or session_state.get("backtest_settings")
        or {}
    )
    for field in tuple(settings):
        widget_value = session_state.get(f"scan_config_{field}")
        if widget_value is not None:
            settings[field] = widget_value
    return settings


def scan_config_from_settings(settings: Mapping) -> ScanConfig:
    return ScanConfig(
        settings["short_ma"],
        settings["long_ma"],
        settings["cross_age"],
        settings["min_long_ma_decline_duration"],
        settings["min_long_ma_decline"],
        settings["max_price_premium"],
        settings["include_impending_crosses"],
        settings["impending_max_gap_pct"],
        settings["pre_cross_validation_sessions"],
        adjusted_prices=settings["adjusted_prices"],
    )


def apply_action(action: AssistantAction, session_state: MutableMapping) -> str:
    """Apply one confirmed action to session state after validation."""
    settings = action.settings or current_settings(session_state)
    scan_config_from_settings(settings).validate()
    if action.kind == "strategy":
        for field, value in settings.items():
            if field != "optional_filters":
                session_state[f"scan_config_{field}"] = value
        session_state[OPTIONAL_SEQUENCE_KEY] = [
            value["key"] for value in settings.get("optional_filters", [])
        ]
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
            "market_data_source": session_state.get(
                "selected_market_data_source", LIVE_MARKET_DATA_SOURCE
            ),
        }
        session_state["_next_app_section"] = "3. Live Scan"
        return "The confirmed market scan is ready to run."
    if action.kind == "backtest" and action.symbol and action.period:
        session_state["backtest_settings"] = settings
        session_state["ticksy_backtest_request"] = {
            "symbols": [action.symbol],
            "period": action.period,
        }
        session_state["_next_app_section"] = "5. Backtester"
        return "The confirmed Backtest is ready to run."
    raise ValueError("Ticksy action is not supported.")
