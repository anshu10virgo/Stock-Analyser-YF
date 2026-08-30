"""Deterministic, local rule explanations for Ticksy."""

from __future__ import annotations

from collections.abc import Mapping

from services.assistant_tools import active_strategy, stock_query_from_prompt, stock_status


def _value(record: dict, key: str, suffix: str = "") -> str:
    value = record.get(key)
    if value is None:
        return "not available"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def explain_stock_prompt(session_state: Mapping, prompt: str) -> str | None:
    """Return an exact local explanation when the prompt requests a known stock."""
    requested = stock_query_from_prompt(session_state, prompt)
    if not requested:
        return None
    status = stock_status(session_state, requested)
    if not status["available"]:
        return None
    record = status["record"]
    strategy = active_strategy(session_state)
    short_ma = strategy.get("short_ma", 50)
    long_ma = strategy.get("long_ma", 200)
    name = record.get("company_name") or record.get("Company") or requested
    if status["status"] == "Failed":
        return (
            f"{requested} — {name} did not qualify in the current local scan. "
            f"It failed at **{record.get('stage', 'an unavailable stage')}**: "
            f"{record.get('reason', 'no failure reason was stored')}"
        )
    base = [
        f"**{requested} — {name}** is in the current local **{status['status']}** results.",
        f"- Short MA {short_ma}: {_value(record, 'ma_short')}; Long MA {long_ma}: {_value(record, 'ma_long')}",
        f"- Short-MA 5-session slope: {_value(record, 'short_ma_slope')}",
        f"- Long-MA decline: {_value(record, 'long_ma_decline_percent', '%')} over {_value(record, 'long_ma_decline_duration')} sessions",
        f"- Price above Long MA: {_value(record, 'price_above_long_ma_percent', '%')} (maximum: {strategy.get('max_price_premium', 10)}%)",
    ]
    if status["status"] == "Impending Golden Cross":
        base.extend(
            [
                f"- Current MA gap: {_value(record, 'impending_gap_percent', '%')} (maximum: {strategy.get('impending_max_gap_pct', 10)}%)",
                f"- Long-MA 5-session slope: {_value(record, 'long_ma_slope')}",
                "- It is not a confirmed Golden Cross yet because the Short MA remains below the Long MA.",
            ]
        )
    else:
        base.extend(
            [
                f"- Golden Cross date: {_value(record, 'cross_date')}; age: {_value(record, 'days_since_cross')} calendar days",
                f"- Long-MA recovery slope: {_value(record, 'long_ma_recovery_slope')}",
            ]
        )
    return "\n".join(base)
