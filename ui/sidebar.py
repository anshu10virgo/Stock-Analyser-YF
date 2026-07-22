"""Scan configuration controls and session-only named presets."""

from __future__ import annotations

from copy import deepcopy

import streamlit as st


DEFAULT_SCAN_SETTINGS = {
    "short_ma": 50,
    "long_ma": 200,
    "cross_age": 80,
    "max_price_premium": 10,
    "min_long_ma_decline_duration": 60,
    "min_long_ma_decline": 10,
    "include_impending_crosses": False,
    "impending_max_gap_pct": 3,
    "pre_cross_validation_sessions": 20,
    "require_post_cross_sessions": False,
    "adjusted_prices": False,
}

PRESET_FIELDS = tuple(DEFAULT_SCAN_SETTINGS)
PRESETS_SESSION_KEY = "user_scan_presets"
MAX_USER_PRESETS = 5


def default_scan_settings() -> dict:
    """Return a fresh copy so widget changes cannot mutate system defaults."""
    return deepcopy(DEFAULT_SCAN_SETTINGS)


def _widget_key(field: str) -> str:
    return f"scan_config_{field}"


def _read_widget_settings() -> dict:
    return {
        field: st.session_state.get(_widget_key(field), value)
        for field, value in DEFAULT_SCAN_SETTINGS.items()
    }


def _load_settings(settings: dict) -> None:
    for field, default in DEFAULT_SCAN_SETTINGS.items():
        st.session_state[_widget_key(field)] = settings.get(field, default)


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
    max_price_premium = right.slider(
        "Maximum price above Long MA (%)",
        min_value=0,
        max_value=50,
        value=DEFAULT_SCAN_SETTINGS["max_price_premium"],
        key=_widget_key("max_price_premium"),
        help="Current Close must be above the Long MA but no more than this percentage above it.",
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
    adjusted_prices = right.checkbox(
        "Use adjusted prices",
        value=DEFAULT_SCAN_SETTINGS["adjusted_prices"],
        key=_widget_key("adjusted_prices"),
        help="Adjust history for dividends and splits. Leave off for actual daily closing prices.",
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
        "Do you want stocks for an Impending Golden Cross?",
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
    st.subheader("Optional confirmations")
    st.caption("Only selected optional checks are enforced.")
    require_post_cross_sessions = st.checkbox(
        "Require at least 10 trading sessions after the Golden Cross",
        value=DEFAULT_SCAN_SETTINGS["require_post_cross_sessions"],
        key=_widget_key("require_post_cross_sessions"),
    )
    with st.expander("Planned valuation filters"):
        st.caption("UI preview only — these filters do not affect calculations yet.")
        st.checkbox("PE below Industry PE", disabled=True)
        st.checkbox("PE below three-year Historical PE", disabled=True)
        st.checkbox("EPS compared with three-year history", disabled=True)

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
        "require_post_cross_sessions": require_post_cross_sessions,
        "adjusted_prices": adjusted_prices,
    }
