import streamlit as st


def render_scan_configuration():

    st.subheader("Mandatory checks")
    st.caption("These checks are always applied to every scan.")
    left, right = st.columns(2)

    short_ma = left.number_input(
        "Short-term moving average (days)",
        min_value=10,
        max_value=100,
        value=50,
        help="Short-term moving average used for Golden Cross detection."
    )

    long_ma = right.number_input(
        "Long-term moving average (days)",
        min_value=50,
        max_value=400,
        value=200,
        help="Long-term moving average used as trend reference."
    )

    cross_age = left.slider(
        "Golden Cross must have happened within the last (days)",
        min_value=1,
        max_value=180,
        value=60,
        help=(
            "For example, 60 means the Golden Cross must have occurred in "
            "the last 60 calendar days."
        )
    )

    max_distance = right.slider(
        "Maximum difference between price and long-term average (%)",
        min_value=0,
        max_value=20,
        value=5,
        help=(
            "For example, 5 means the current price can be up to 5% above "
            "or below the long-term moving average."
        )
    )

    pre_cross_days = left.slider(
        "Pre-cross confirmation window (days)",
        min_value=5,
        max_value=100,
        value=20,
        help=(
            "Days Short MA must remain below Long MA before crossover, and "
            "the window in which a trough must occur before the cross."
        )
    )

    adjusted_prices = right.checkbox(
        "Use adjusted prices",
        value=False,
        help=(
            "Adjusts historical prices for dividends and splits. Leave off "
            "to calculate signals from the actual daily closing prices."
        ),
    )

    st.divider()
    st.subheader("Optional checks")
    st.caption("Select only the additional filters you want to enforce.")
    optional_left, optional_right = st.columns(2)

    require_pre_cross_trough = optional_left.checkbox(
        "Require a price trough before the Golden Cross",
        value=False,
        help="Requires a validated local price low in the pre-cross window.",
    )
    require_pre_cross_decline = optional_left.checkbox(
        "Require the long-term trend to decline before the cross",
        value=False,
    )
    require_post_cross_sessions = optional_right.checkbox(
        "Require at least 10 trading sessions after the cross",
        value=False,
    )
    require_post_cross_increase = optional_right.checkbox(
        "Require the long-term trend to rise after the cross",
        value=False,
    )

    slope_lookback = st.number_input(
        "Long-term trend evaluation window (days)",
        min_value=5,
        max_value=100,
        value=20,
        help=(
            "Sessions used to confirm that the Long MA declined before and "
            "rose after the Golden Cross."
        )
    )

    return {
        "short_ma": short_ma,
        "long_ma": long_ma,
        "cross_age": cross_age,
        "max_distance": max_distance,
        "pre_cross_days": pre_cross_days,
        "slope_lookback": slope_lookback,
        "require_pre_cross_trough": require_pre_cross_trough,
        "require_pre_cross_decline": require_pre_cross_decline,
        "require_post_cross_sessions": require_post_cross_sessions,
        "require_post_cross_increase": require_post_cross_increase,
        "adjusted_prices": adjusted_prices,
    }
