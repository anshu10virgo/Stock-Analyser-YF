import streamlit as st


def render_sidebar():

    st.sidebar.header("Scanner Configuration")

    short_ma = st.sidebar.number_input(
        "Short MA",
        min_value=10,
        max_value=100,
        value=50,
        help="Short-term moving average used for Golden Cross detection."
    )

    long_ma = st.sidebar.number_input(
        "Long MA",
        min_value=50,
        max_value=400,
        value=200,
        help="Long-term moving average used as trend reference."
    )

    cross_age = st.sidebar.slider(
        "Golden Cross Age",
        min_value=1,
        max_value=180,
        value=60,
        help="Maximum age of Golden Cross signal in days."
    )

    max_distance = st.sidebar.slider(
        "Price Distance %",
        min_value=0,
        max_value=20,
        value=5,
        help="Maximum distance of current price from Long MA."
    )

    pre_cross_days = st.sidebar.slider(
        "Pre-Cross Validation Days",
        min_value=5,
        max_value=100,
        value=20,
        help="Days Short MA must remain below Long MA before crossover."
    )

    trough_lookback = st.sidebar.slider(
        "Trough Lookback",
        min_value=30,
        max_value=250,
        value=120,
        help="Historical window used for trough detection."
    )

    min_troughs = st.sidebar.slider(
        "Minimum Trough Count",
        min_value=1,
        max_value=10,
        value=2,
        help="Minimum trough count required to qualify."
    )

    slope_lookback = st.sidebar.slider(
        "MA Slope Lookback",
        min_value=5,
        max_value=100,
        value=20,
        help="Days used to calculate Long MA trend slope."
    )

    require_higher_low = st.sidebar.checkbox(
        "Require Higher Low",
        value=True,
        help="Latest trough must be higher than previous trough."
    )

    adjusted_prices = st.sidebar.checkbox(
        "Use adjusted prices",
        value=False,
        help=(
            "Adjusts historical prices for dividends and splits. Leave off "
            "to calculate signals from the actual daily closing prices."
        ),
    )

    return {
        "short_ma": short_ma,
        "long_ma": long_ma,
        "cross_age": cross_age,
        "max_distance": max_distance,
        "pre_cross_days": pre_cross_days,
        "trough_lookback": trough_lookback,
        "min_troughs": min_troughs,
        "slope_lookback": slope_lookback,
        "require_higher_low": require_higher_low,
        "adjusted_prices": adjusted_prices,
    }
