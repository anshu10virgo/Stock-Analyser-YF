"""Pure historical replay models, rules, and calculations."""

from stock_analyser.domain.backtesting.calculations import forward_returns, summarize_returns, valuation_at, within_cross_age
from stock_analyser.domain.backtesting.horizons import HORIZON_SESSIONS
from stock_analyser.domain.backtesting.models import BacktestRun, BacktestSignal, ReturnSummary
from stock_analyser.domain.backtesting.replay import BacktestReplay
from stock_analyser.domain.backtesting.rules import qualifies_post_cross

__all__ = [
    "BacktestReplay", "BacktestRun", "BacktestSignal", "HORIZON_SESSIONS",
    "ReturnSummary", "forward_returns", "qualifies_post_cross",
    "summarize_returns", "valuation_at", "within_cross_age",
]
