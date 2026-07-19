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
        value=80,
        help=(
            "For example, 80 means the Golden Cross must have occurred in "
            "the last 80 calendar days."
        )
    )

    max_price_premium = right.slider(
        "Maximum price above Long MA (%)",
        min_value=0,
        max_value=50,
        value=10,
        help=(
            "For example, 10 means the current price must be above the Long "
            "MA but no more than 10% above it."
        )
    )

    min_long_ma_decline_duration = left.slider(
        "Minimum decline duration from 52-week Long MA high to trough (trading sessions)",
        min_value=1,
        max_value=252,
        value=60,
        help=(
            "The Long MA must take at least this many trading sessions to fall "
            "from its 52-week high to the later trough. 60 sessions is about three months."
        )
    )

    min_long_ma_decline = right.slider(
        "Minimum Long MA decline from 52-week high to trough (%)",
        min_value=0,
        max_value=50,
        value=10,
        help=(
            "The Long MA must have fallen at least this far from its 52-week "
            "high to a trough before its post-trough five-session slope rises."
        ),
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
    st.caption("Select only the additional filter you want to enforce.")
    require_post_cross_sessions = st.checkbox(
        "Require at least 10 trading sessions after the cross",
        value=False,
    )
    return {
        "short_ma": short_ma,
        "long_ma": long_ma,
        "cross_age": cross_age,
        "max_price_premium": max_price_premium,
        "min_long_ma_decline_duration": min_long_ma_decline_duration,
        "min_long_ma_decline": min_long_ma_decline,
        "require_post_cross_sessions": require_post_cross_sessions,
        "adjusted_prices": adjusted_prices,
    }
