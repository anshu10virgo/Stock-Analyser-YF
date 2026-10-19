"""Pure reusable calculations for fundamental metrics and benchmarks."""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from statistics import median

from stock_analyser.domain.fundamentals.models import IndustryValuation


def finite_number(
    value,
    *,
    positive: bool = False,
    non_negative: bool = False,
) -> float | None:
    """Normalize one finite number while applying optional sign constraints."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    if positive and number <= 0:
        return None
    if non_negative and number < 0:
        return None
    return number


def compound_annual_growth_rate(start, end, years: int) -> float | None:
    """Return conventional CAGR when both endpoints and the period are valid."""
    start_value = finite_number(start, positive=True)
    end_value = finite_number(end, positive=True)
    if start_value is None or end_value is None or years <= 0:
        return None
    return ((end_value / start_value) ** (1 / years) - 1) * 100


def price_to_earnings(price, earnings_per_share) -> float | None:
    """Return P/E only for a usable price and positive trailing EPS."""
    price_value = finite_number(price)
    eps_value = finite_number(earnings_per_share, positive=True)
    if price_value is None or eps_value is None:
        return None
    return price_value / eps_value


def peg_ratio(price_earnings, growth_percent) -> float | None:
    """Return PEG using P/E divided by a positive percentage growth value."""
    pe_value = finite_number(price_earnings, positive=True)
    growth_value = finite_number(growth_percent, positive=True)
    if pe_value is None or growth_value is None:
        return None
    return pe_value / growth_value


def debt_to_equity(borrowings, equity_capital, reserves) -> float | None:
    """Return debt divided by equity capital plus reserves when equity is positive."""
    debt_value = finite_number(borrowings)
    capital_value = finite_number(equity_capital) or 0.0
    reserve_value = finite_number(reserves) or 0.0
    equity = capital_value + reserve_value
    if debt_value is None or equity <= 0:
        return None
    return debt_value / equity


def industry_valuation(
    peers: Iterable[Mapping],
    *,
    market_cap_key: str = "market_cap",
    pe_key: str = "pe",
) -> IndustryValuation:
    """Calculate market-cap weighted and median P/E from eligible peers."""
    eligible: list[tuple[float, float]] = []
    for peer in peers:
        market_cap = finite_number(peer.get(market_cap_key), positive=True)
        pe = finite_number(peer.get(pe_key), positive=True)
        if market_cap is not None and pe is not None:
            eligible.append((market_cap, pe))
    if not eligible:
        return IndustryValuation.unavailable()
    total_market_cap = sum(market_cap for market_cap, _pe in eligible)
    implied_earnings = sum(market_cap / pe for market_cap, pe in eligible)
    return IndustryValuation(
        weighted_pe=round(total_market_cap / implied_earnings, 2),
        median_pe=round(median(pe for _market_cap, pe in eligible), 2),
        peer_count=len(eligible),
    )


__all__ = [
    "compound_annual_growth_rate",
    "debt_to_equity",
    "finite_number",
    "industry_valuation",
    "peg_ratio",
    "price_to_earnings",
]
