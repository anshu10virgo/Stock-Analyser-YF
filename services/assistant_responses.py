"""Deterministic local responses for Ticksy capabilities without scan snapshots."""

from __future__ import annotations

from collections.abc import MutableMapping

from services.assistant_tools import (
    backtest_records,
    calculation_trace,
    crossover_window,
    data_dictionary,
    market_condition_summary,
    parameter_help,
    scan_summary,
    stock_status,
    symbols_from_prompt,
    universe_lookup,
)


def local_response(session_state: MutableMapping, prompt: str) -> str | None:
    """Return a deterministic answer for supported local-data questions."""
    lower = prompt.lower()
    symbols = symbols_from_prompt(session_state, prompt)
    symbol = symbols[0] if symbols else None
    if _contains(lower, "crossover", "when will", "when might", "estimated cross") and symbol:
        return _crossover_response(session_state, symbol)
    if _contains(lower, "market condition", "market setup", "market summary", "explain results", "current scan"):
        return _market_response(session_state)
    if "compare" in lower and len(symbols) >= 2:
        return _comparison_response(session_state, symbols)
    if _contains(lower, "what is", "what does", "explain parameter", "slope", "premium", "cross age", "ma decline"):
        return _parameter_response(session_state, prompt, symbol)
    if _contains(lower, "formula", "calculation", "calculate", "trace") and symbol:
        return _trace_response(session_state, symbol)
    if _contains(lower, "source", "provenance", "where does", "where is") and symbol:
        return _provenance_response(session_state, symbol)
    if _contains(lower, "data dictionary", "what do columns", "what does this column"):
        return _dictionary_response()
    if _contains(lower, "scan health", "scan error", "download failure", "coverage"):
        return _health_response(session_state)
    if _contains(lower, "company", "industry", "market cap rank", "universe"):
        return _universe_response(session_state, prompt)
    if _contains(lower, "report", "summary for email", "email summary"):
        return _report_response(session_state)
    if _contains(lower, "historical signal", "previous golden", "past golden", "backtest history"):
        return _history_response(session_state, symbols)
    if _contains(lower, "how do i", "guide me", "help me use", "workflow"):
        return _guide_response()
    if lower.startswith("save note"):
        return _save_note(session_state, prompt, symbol)
    if _contains(lower, "show notes", "find notes"):
        return _notes_response(session_state, symbol)
    return None


def _market_response(session_state: MutableMapping) -> str:
    summary = market_condition_summary(session_state)
    if not summary.get("scan_time"):
        return "No completed local scan is available yet. Run a scan first, then I can summarise the current market setup."
    return (
        f"**Current local scan ({summary['scan_time']})**\n"
        f"- Post Golden Cross: {summary['post_golden_cross_count']}\n"
        f"- Impending Golden Cross: {summary['impending_golden_cross_count']}\n"
        f"- Recent confirmed crosses: {summary['recent_cross_count']}\n"
        f"- Available results above the Long MA: {summary['above_long_ma_count']}\n"
        f"- Failed or unavailable outcomes: {summary['failed_count']}"
    )


def _comparison_response(session_state: MutableMapping, symbols: list[str]) -> str:
    lines = ["**Current local comparison**"]
    for symbol in symbols[:5]:
        status = stock_status(session_state, symbol)
        if not status.get("available"):
            continue
        record = status["record"]
        lines.append(
            f"- **{symbol}** — {status['status']}; Short/Long MA: {_value(record, 'ma_short')} / {_value(record, 'ma_long')}; "
            f"Short-MA slope: {_value(record, 'short_ma_slope')}; P/E: {_value(record, 'pe')}; "
            f"industry: {record.get('industry') or 'not available'}."
        )
    records = backtest_records(session_state, symbols)
    if records:
        lines.append(f"- Local Backtester records available: {len(records)}.")
    return "\n".join(lines) if len(lines) > 1 else "The requested stocks are not available in the current local results."


def _crossover_response(session_state: MutableMapping, symbol: str) -> str:
    estimate = crossover_window(session_state, symbol)
    if not estimate.get("available"):
        return f"I cannot show an illustrative crossover window for {symbol}: {estimate['reason']}"
    return (
        f"**Illustrative crossover window for {symbol}**\n"
        f"- Current MA gap: {estimate['gap']:.2f}\n"
        f"- Positive convergence: {estimate['convergence_per_session']:.4f} per session\n"
        f"- If both current slopes persist, the averages could meet in about {estimate['estimated_sessions']} trading sessions.\n\n"
        "This is an illustrative local slope calculation, not a prediction and not a scan, ranking, alert, or Backtester rule."
    )


def _parameter_response(session_state: MutableMapping, prompt: str, symbol: str | None) -> str:
    values = parameter_help(session_state, prompt, symbol)
    lines = ["**Parameter guide**"]
    for name, details in values.items():
        current = details["current_value"]
        suffix = f" Current local value: {current}." if current is not None else ""
        lines.append(f"- **{name.title()}**: {details['meaning']}{suffix}")
    return "\n".join(lines)


def _trace_response(session_state: MutableMapping, symbol: str) -> str:
    trace = calculation_trace(session_state, symbol)
    if not trace.get("available"):
        return f"No local calculation trace is available for {symbol}: {trace.get('reason', 'unknown reason')}"
    premium = trace["price_premium"]
    gap = trace["ma_gap"]
    slope = trace["slope"]
    pe = trace["pe"]
    return (
        f"**Local calculation trace for {symbol}**\n"
        f"- Price premium: `{premium['formula']}` using Close {premium['inputs']['close']} and Long MA {premium['inputs']['long_ma']}; stored value {premium['value']}.\n"
        f"- MA gap: `{gap['formula']}` using Short MA {gap['inputs']['short_ma']} and Long MA {gap['inputs']['long_ma']}; stored value {gap['value']}.\n"
        f"- Slope: {slope['formula']}; Short {slope['inputs']['short_ma_slope']}, Long {slope['inputs']['long_ma_slope']}.\n"
        f"- P/E: `{pe['formula']}`; stored value {pe['value']} from {pe['source'] or 'the local result record'}."
    )


def _provenance_response(session_state: MutableMapping, symbol: str) -> str:
    status = stock_status(session_state, symbol)
    if not status.get("available"):
        return f"No local result record is available for {symbol}."
    record = status["record"]
    return (
        f"**Local data provenance for {symbol}**\n"
        f"- Technical values come from the completed local scan using its active strategy.\n"
        f"- Scan timestamp: {scan_summary(session_state).get('scan_time') or 'not available'}.\n"
        f"- P/E: {record.get('pe') if record.get('pe') is not None else 'not available'}; source: {record.get('pe_source') or 'not available'}.\n"
        f"- Industry: {record.get('industry') or 'not available'}."
    )


def _dictionary_response() -> str:
    lines = ["**Data dictionary**"]
    for name, meaning in data_dictionary().items():
        lines.append(f"- **{name}**: {meaning}")
    return "\n".join(lines)


def _health_response(session_state: MutableMapping) -> str:
    summary = scan_summary(session_state)
    if not summary.get("scan_time"):
        return "No completed local scan is available, so scan health cannot be assessed yet."
    return (
        f"**Local scan health**\n- Completed scan: {summary['scan_time']}\n"
        f"- Qualified: {summary['post_golden_cross_count'] + summary['impending_golden_cross_count']}\n"
        f"- Failed or unavailable outcomes: {summary['failed_count']}\n"
        "For a specific failed stock, ask why it failed to see its stored local reason."
    )


def _universe_response(session_state: MutableMapping, prompt: str) -> str:
    lookup = universe_lookup(session_state, prompt)
    if not lookup.get("available"):
        return lookup["reason"]
    details = [
        f"**{lookup['symbol']}** — {lookup.get('company_name') or 'company name not available'}.",
        f"- Market-cap rank: {lookup.get('market_cap_rank') or 'not available'}.",
    ]
    if lookup.get("industry"):
        details.append(f"- Industry in the current local scan: {lookup['industry']}.")
    if lookup.get("current_scan_status"):
        details.append(f"- Current scan status: {lookup['current_scan_status']}.")
    return "\n".join(details)


def _report_response(session_state: MutableMapping) -> str:
    summary = market_condition_summary(session_state)
    if not summary.get("scan_time"):
        return "No completed local scan is available to summarise into a report."
    return (
        f"**Local scan summary — {summary['scan_time']}**\n"
        f"The scan found {summary['post_golden_cross_count']} Post Golden Cross and "
        f"{summary['impending_golden_cross_count']} Impending Golden Cross stocks. "
        f"{summary['recent_cross_count']} confirmed crosses are within 20 calendar days. "
        f"There are {summary['failed_count']} failed or unavailable outcomes."
    )


def _history_response(session_state: MutableMapping, symbols: list[str]) -> str:
    records = backtest_records(session_state, symbols or None)
    if not records:
        return "No local Backtester records are available for that request. Run a Backtest first."
    lines = ["**Local Backtester signal history**"]
    for record in records[:10]:
        lines.append(
            f"- {record.get('Stock')}: cross {record.get('Cross date')}, entry {record.get('Entry')}, "
            f"P/E {record.get('P/E')}, 1Y return {record.get('1Y')}%."
        )
    return "\n".join(lines)


def _guide_response() -> str:
    return (
        "**Workflow guide**\n"
        "1. Setup: choose the universe, market-data source, and stock count.\n"
        "2. Strategy: set the technical and optional filters.\n"
        "3. Live Scan: run the selected universe.\n"
        "4. Results: inspect qualified stocks and charts.\n"
        "5. Backtester: review historical Golden Cross outcomes for selected stocks."
    )


def _save_note(session_state: MutableMapping, prompt: str, symbol: str | None) -> str:
    note = prompt.partition(":")[2].strip()
    if not note:
        return "Add a note after a colon, for example: `Save note TCS: review after the next results scan`."
    notes = session_state.setdefault("ticksy_notes", [])
    notes.append({"symbol": symbol or "General", "note": note})
    return f"Saved a session-only Ticksy note for {symbol or 'the project'}: {note}"


def _notes_response(session_state: MutableMapping, symbol: str | None) -> str:
    notes = session_state.get("ticksy_notes", [])
    selected = [note for note in notes if not symbol or note["symbol"] == symbol]
    if not selected:
        return "No matching Ticksy session notes are saved."
    return "\n".join(f"- **{note['symbol']}**: {note['note']}" for note in selected)


def _contains(text: str, *terms: str) -> bool:
    return any(term in text for term in terms)


def _value(record: dict, key: str) -> str:
    value = record.get(key)
    return f"{value:.2f}" if isinstance(value, float) else str(value if value is not None else "not available")
