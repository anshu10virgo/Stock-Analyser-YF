"""Scan configuration controls and session-only named presets."""

from __future__ import annotations

from copy import deepcopy

import streamlit as st

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

PRESET_FIELDS = tuple(DEFAULT_SCAN_SETTINGS)
PRESETS_SESSION_KEY = "user_scan_presets"
MAX_USER_PRESETS = 5
OPTIONAL_SEQUENCE_KEY = "scan_config_optional_sequence"

OPTIONAL_FILTER_DEFINITIONS = {
    RELATIVE_INDUSTRY_PE: {
        "label": "Relative Industry P/E",
        "group": "Valuation",
        "rule": "Current stock P/E must be below the median Industry P/E.",
        "description": (
            "Checks whether the stock trades at a discount to its current "
            "industry peers."
        ),
    },
    HISTORICAL_STOCK_PE: {
        "label": "P/E vs. Historical Stock P/E",
        "group": "Valuation",
        "rule": (
            "Current P/E must be below its own 3-year average; available "
            "5-year and 10-year averages must also pass."
        ),
        "description": (
            "Missing individual periods are ignored. If every historical "
            "benchmark is unavailable, the stock is retained and the filter "
            "is marked as not evaluated."
        ),
    },
    PEG_RATIO: {
        "label": "PEG Ratio",
        "group": "Valuation",
        "rule": "PEG Ratio must be at or below the selected maximum.",
        "description": (
            "Adjusts the standard P/E ratio by taking earnings growth into "
            "account to determine if a stock is overpriced relative to its "
            "growth rate."
        ),
        "threshold": 1.0,
    },
    PROFIT_GROWTH: {
        "label": "Multi-Period Profit Growth",
        "group": "Growth",
        "rule": "Every available 3Y, 5Y and 10Y CAGR must exceed the minimum.",
        "description": "Checks for consistent multi-year net-profit compounding.",
        "threshold": 15.0,
    },
    EPS_GROWTH: {
        "label": "Multi-Period EPS Growth",
        "group": "Growth",
        "rule": "Every available 3Y, 5Y and 10Y CAGR must exceed the minimum.",
        "description": (
            "Confirms per-share earnings expansion without penalising a stock "
            "for an unavailable individual period."
        ),
        "threshold": 15.0,
    },
    SALES_GROWTH: {
        "label": "Multi-Period Sales / Revenue Growth",
        "group": "Growth",
        "rule": "Every available 3Y, 5Y and 10Y CAGR must exceed the minimum.",
        "description": "Checks for sustained top-line business growth.",
        "threshold": 15.0,
    },
    RETURN_ON_EQUITY: {
        "label": "Return on Equity (ROE)",
        "group": "Quality and Risk",
        "rule": "ROE must be at or above the selected minimum.",
        "description": (
            "Measures how efficiently management generates profits from every "
            "rupee of shareholders' equity."
        ),
        "threshold": 20.0,
    },
    DEBT_TO_EQUITY: {
        "label": "Debt-to-Equity (D/E) Ratio",
        "group": "Quality and Risk",
        "rule": "Debt-to-Equity must be at or below the selected maximum.",
        "description": (
            "Measures how much debt a company uses to finance its assets "
            "relative to shareholders' capital. The rule is bypassed for "
            "banks and financial companies."
        ),
        "threshold": 0.5,
    },
    MARKET_CAP: {
        "label": "Market Capitalisation Buckets",
        "group": "Company Size",
        "rule": "Market capitalisation must match a selected bucket or custom range.",
        "description": "Groups Indian companies by size using values in ₹ crore.",
        "market_cap_buckets": ["large", "mid"],
        "custom_min_crore": None,
        "custom_max_crore": None,
    },
}

MARKET_CAP_LABELS = {
    "large": "Large Cap — above ₹20,000 Cr",
    "mid": "Mid Cap — ₹5,000 to ₹20,000 Cr",
    "small": "Small Cap — ₹500 to ₹5,000 Cr",
    "micro": "Micro Cap — below ₹500 Cr",
}


def default_scan_settings() -> dict:
    """Return a fresh copy so widget changes cannot mutate system defaults."""
    return deepcopy(DEFAULT_SCAN_SETTINGS)


def _widget_key(field: str) -> str:
    return f"scan_config_{field}"


def _read_widget_settings() -> dict:
    settings = {
        field: st.session_state.get(_widget_key(field), value)
        for field, value in DEFAULT_SCAN_SETTINGS.items()
        if field != "optional_filters"
    }
    settings["optional_filters"] = _read_optional_filters()
    return settings


def _load_settings(settings: dict) -> None:
    for field, default in DEFAULT_SCAN_SETTINGS.items():
        if field == "optional_filters":
            continue
        st.session_state[_widget_key(field)] = settings.get(field, default)
    optional_filters = settings.get("optional_filters", [])
    st.session_state[OPTIONAL_SEQUENCE_KEY] = [
        values["key"] for values in optional_filters
    ]
    for values in optional_filters:
        for field in (
            "threshold",
            "market_cap_buckets",
            "custom_min_crore",
            "custom_max_crore",
        ):
            if field in values:
                st.session_state[_optional_widget_key(values["key"], field)] = (
                    deepcopy(values[field])
                )


def _optional_widget_key(filter_key: str, field: str) -> str:
    return f"scan_optional_{filter_key}_{field}"


def _read_optional_filters() -> list[dict]:
    """Return the ordered optional-filter configuration from session state."""
    selected = st.session_state.get(OPTIONAL_SEQUENCE_KEY, [])
    configured = []
    for filter_key in selected:
        definition = OPTIONAL_FILTER_DEFINITIONS[filter_key]
        values = {"key": filter_key}
        for field in (
            "threshold",
            "market_cap_buckets",
            "custom_min_crore",
            "custom_max_crore",
        ):
            if field in definition:
                values[field] = deepcopy(
                    st.session_state.get(
                        _optional_widget_key(filter_key, field),
                        definition[field],
                    )
                )
        configured.append(values)
    return configured


def _presets() -> dict:
    return st.session_state.setdefault(PRESETS_SESSION_KEY, {})


def _render_presets() -> None:
    """Render preset controls backed only by Streamlit session state."""
    st.subheader("Saved strategies")
    st.caption(
        "Named strategies exist only for this app session. They are not written "
        "to Git and cannot change the system defaults."
    )

    presets = _presets()
    choices = ["System defaults", *presets]
    selected = st.selectbox("Strategy", choices, key="selected_scan_preset")
    load_col, reset_col = st.columns(2)
    if load_col.button("Load strategy", width="stretch"):
        _load_settings(
            DEFAULT_SCAN_SETTINGS if selected == "System defaults" else presets[selected]
        )
        st.rerun()
    if reset_col.button("Reset to system defaults", width="stretch"):
        _load_settings(DEFAULT_SCAN_SETTINGS)
        st.rerun()

    preset_name = st.text_input(
        "Save current settings as",
        key="new_scan_preset_name",
        placeholder="For example: Conservative reversal",
    ).strip()
    save_col, update_col = st.columns(2)
    if save_col.button("Save as new", width="stretch"):
        if not preset_name:
            st.warning("Enter a strategy name before saving.")
        elif preset_name in presets:
            st.warning("That strategy name already exists. Choose Update instead.")
        elif len(presets) >= MAX_USER_PRESETS:
            st.warning("A maximum of five session strategies can be saved.")
        else:
            presets[preset_name] = _read_widget_settings()
            st.rerun()

    can_update = selected != "System defaults"
    if update_col.button(
        "Update selected",
        width="stretch",
        disabled=not can_update,
    ):
        presets[selected] = _read_widget_settings()
        st.success(f"Updated {selected} for this session.")

    st.caption(f"{len(presets)} of {MAX_USER_PRESETS} session strategies saved")


def _render_filter_controls(filter_key: str) -> None:
    """Render controls belonging to one selected optional filter."""
    definition = OPTIONAL_FILTER_DEFINITIONS[filter_key]
    threshold_key = _optional_widget_key(filter_key, "threshold")
    if filter_key == PEG_RATIO:
        st.slider(
            "Maximum PEG Ratio",
            min_value=0.0,
            max_value=2.0,
            value=float(definition["threshold"]),
            step=0.1,
            key=threshold_key,
        )
    elif filter_key in {PROFIT_GROWTH, EPS_GROWTH, SALES_GROWTH}:
        st.slider(
            "Minimum growth across available periods (%)",
            min_value=0.0,
            max_value=50.0,
            value=float(definition["threshold"]),
            step=0.5,
            key=threshold_key,
        )
    elif filter_key == RETURN_ON_EQUITY:
        st.slider(
            "Minimum ROE (%)",
            min_value=0.0,
            max_value=50.0,
            value=float(definition["threshold"]),
            step=0.5,
            key=threshold_key,
        )
    elif filter_key == DEBT_TO_EQUITY:
        st.slider(
            "Maximum Debt-to-Equity Ratio",
            min_value=0.0,
            max_value=2.0,
            value=float(definition["threshold"]),
            step=0.1,
            key=threshold_key,
        )
    elif filter_key == MARKET_CAP:
        st.multiselect(
            "Market-cap buckets",
            options=list(MARKET_CAP_LABELS),
            default=definition["market_cap_buckets"],
            format_func=MARKET_CAP_LABELS.get,
            key=_optional_widget_key(filter_key, "market_cap_buckets"),
        )
        minimum, maximum = st.columns(2)
        minimum.number_input(
            "Custom minimum (₹ Cr)",
            min_value=0.0,
            value=definition["custom_min_crore"],
            step=100.0,
            placeholder="Optional",
            key=_optional_widget_key(filter_key, "custom_min_crore"),
        )
        maximum.number_input(
            "Custom maximum (₹ Cr)",
            min_value=0.0,
            value=definition["custom_max_crore"],
            step=100.0,
            placeholder="Optional",
            key=_optional_widget_key(filter_key, "custom_max_crore"),
        )


def _render_optional_filter_builder() -> list[dict]:
    """Render the ordered add/remove builder with an empty default sequence."""
    st.subheader("Optional fundamental filters")
    st.caption(
        "No optional filter is applied by default. Selected filters use AND "
        "logic and do not change the technical score."
    )
    selected = st.session_state.setdefault(OPTIONAL_SEQUENCE_KEY, [])
    available = [
        filter_key
        for filter_key in OPTIONAL_FILTER_DEFINITIONS
        if filter_key not in selected
    ]
    picker, action = st.columns((4, 1), vertical_alignment="bottom")
    selected_to_add = picker.selectbox(
        "Choose an optional filter",
        options=available,
        format_func=lambda filter_key: (
            f"{OPTIONAL_FILTER_DEFINITIONS[filter_key]['group']} — "
            f"{OPTIONAL_FILTER_DEFINITIONS[filter_key]['label']}"
        ),
        key="optional_filter_picker",
        disabled=not available,
        placeholder="All filters have been added",
    )
    if action.button(
        "＋ Add filter",
        width="stretch",
        disabled=not available,
        key="add_optional_filter",
    ):
        st.session_state[OPTIONAL_SEQUENCE_KEY] = [
            *selected,
            selected_to_add,
        ]
        st.rerun()

    if not selected:
        st.info("No optional filters added. Only mandatory checks will be applied.")
        return []

    for index, filter_key in enumerate(selected, start=1):
        definition = OPTIONAL_FILTER_DEFINITIONS[filter_key]
        with st.container(border=True):
            heading, remove = st.columns((5, 1), vertical_alignment="center")
            heading.markdown(f"**{index}. {definition['label']}**")
            if remove.button(
                "− Remove",
                key=f"remove_optional_filter_{filter_key}",
                width="stretch",
            ):
                st.session_state[OPTIONAL_SEQUENCE_KEY] = [
                    key for key in selected if key != filter_key
                ]
                st.rerun()
            st.caption(definition["rule"])
            st.caption(definition["description"])
            _render_filter_controls(filter_key)

    st.caption(
        f"{len(selected)} optional filter"
        f"{'' if len(selected) == 1 else 's'} applied with AND logic."
    )
    return _read_optional_filters()


def render_scan_configuration() -> dict:
    """Render mandatory and optional scan checks without changing defaults."""
    _render_presets()
    st.divider()
    st.subheader("Golden Cross — Mandatory Checks")
    st.caption("These foundation checks are shared by both result groups.")
    left, right = st.columns(2)

    short_ma = left.number_input(
        "Short-term moving average (days)",
        min_value=10,
        max_value=100,
        value=DEFAULT_SCAN_SETTINGS["short_ma"],
        key=_widget_key("short_ma"),
        help="The five-session slope of this moving average must be positive.",
    )
    long_ma = right.number_input(
        "Long-term moving average (days)",
        min_value=50,
        max_value=2000,
        value=DEFAULT_SCAN_SETTINGS["long_ma"],
        key=_widget_key("long_ma"),
        help="The trend reference used for the Golden Cross and reversal checks.",
    )
    adjusted_prices = left.checkbox(
        "Use adjusted prices",
        value=DEFAULT_SCAN_SETTINGS["adjusted_prices"],
        key=_widget_key("adjusted_prices"),
        help="Adjust history for dividends and splits. Leave off for actual daily closing prices.",
    )
    min_long_ma_decline_duration = left.slider(
        "Minimum high-to-trough decline duration (trading sessions)",
        min_value=1,
        max_value=252,
        value=DEFAULT_SCAN_SETTINGS["min_long_ma_decline_duration"],
        key=_widget_key("min_long_ma_decline_duration"),
        help="The Long MA must take at least this many sessions to fall from its 52-week high to its later trough.",
    )
    min_long_ma_decline = right.slider(
        "Minimum Long MA decline from 52-week high (%)",
        min_value=0,
        max_value=50,
        value=DEFAULT_SCAN_SETTINGS["min_long_ma_decline"],
        key=_widget_key("min_long_ma_decline"),
        help="Minimum fall from the 52-week Long-MA high to the subsequent trough before recovery.",
    )
    max_price_premium = right.slider(
        "Maximum price above Long MA (%)",
        min_value=0,
        max_value=50,
        value=DEFAULT_SCAN_SETTINGS["max_price_premium"],
        key=_widget_key("max_price_premium"),
        help="Current Close must be above the Long MA but no more than this percentage above it.",
    )

    st.divider()
    st.subheader("Post Golden Cross — Mandatory Checks")
    st.caption("These checks qualify stocks whose crossover has already completed.")
    cross_age = st.slider(
        "Golden Cross maximum age (calendar days)",
        min_value=1,
        max_value=180,
        value=DEFAULT_SCAN_SETTINGS["cross_age"],
        key=_widget_key("cross_age"),
        help="The Golden Cross must have occurred within this many calendar days.",
    )
    st.markdown(
        "- Short MA must be strictly above Long MA.\n"
        "- The latest five-session post-trough Long-MA slope must be positive."
    )

    st.divider()
    st.subheader("Impending Golden Cross")
    include_impending_crosses = st.checkbox(
        "Do you want impending stocks?",
        value=DEFAULT_SCAN_SETTINGS["include_impending_crosses"],
        key=_widget_key("include_impending_crosses"),
        help="Adds a separate result list for stocks approaching a fresh crossover.",
    )
    impending_max_gap_pct = DEFAULT_SCAN_SETTINGS["impending_max_gap_pct"]
    pre_cross_validation_sessions = DEFAULT_SCAN_SETTINGS[
        "pre_cross_validation_sessions"
    ]
    if include_impending_crosses:
        st.caption("Configure only the checks unique to an impending crossover.")
        impending_left, impending_right = st.columns(2)
        impending_max_gap_pct = impending_left.slider(
            "Maximum gap between Short MA and Long MA (%)",
            min_value=0.1,
            max_value=20.0,
            value=float(DEFAULT_SCAN_SETTINGS["impending_max_gap_pct"]),
            step=0.1,
            key=_widget_key("impending_max_gap_pct"),
            help="Calculated as (Long MA - Short MA) / Long MA × 100.",
        )
        pre_cross_validation_sessions = impending_right.slider(
            "Pre-cross validation period (trading sessions)",
            min_value=5,
            max_value=60,
            value=DEFAULT_SCAN_SETTINGS["pre_cross_validation_sessions"],
            key=_widget_key("pre_cross_validation_sessions"),
            help="Short MA must remain strictly below Long MA during every prior session in this period.",
        )
        st.markdown(
            "- Short MA must be at or below Long MA and rising faster than it.\n"
            "- Latest five-session Long-MA slope must be non-negative.\n"
            "- Current Close must be above both moving averages."
        )

    st.divider()
    optional_filters = _render_optional_filter_builder()

    return {
        "short_ma": short_ma,
        "long_ma": long_ma,
        "cross_age": cross_age,
        "max_price_premium": max_price_premium,
        "min_long_ma_decline_duration": min_long_ma_decline_duration,
        "min_long_ma_decline": min_long_ma_decline,
        "include_impending_crosses": include_impending_crosses,
        "impending_max_gap_pct": impending_max_gap_pct,
        "pre_cross_validation_sessions": pre_cross_validation_sessions,
        "optional_filters": optional_filters,
        "adjusted_prices": adjusted_prices,
    }
