"""Registered read-only tools backed by existing Stock Analyser services."""

from __future__ import annotations

from agents.contracts import (
    ApprovalLevel,
    ArgumentSpec,
    ToolDefinition,
    ToolEffect,
)
from agents.registry import ToolRegistry
from application.context import ApplicationContext
from services.assistant_tools import (
    backtest_records,
    calculation_trace,
    market_condition_summary,
    rejection_summary,
    scan_summary,
    stock_status,
)


def _state(context: ApplicationContext):
    return context.as_mapping()


def _scan_summary(context, _arguments):
    return scan_summary(_state(context))


def _stock_status(context, arguments):
    return stock_status(_state(context), arguments["symbol"])


def _market_condition(context, _arguments):
    return market_condition_summary(_state(context))


def _backtest_results(context, arguments):
    symbols = arguments.get("symbols") or None
    return backtest_records(_state(context), symbols)


def _calculation_trace(context, arguments):
    return calculation_trace(_state(context), arguments["symbol"])


def _data_health(context, _arguments):
    summary = scan_summary(_state(context))
    return {
        **summary,
        "metrics": context.get("scan_metrics", {}),
        "snapshot_identity": context.snapshot_identity,
    }


def _rejection_summary(context, arguments):
    limit = max(1, min(10, arguments.get("limit", 5)))
    return rejection_summary(_state(context), limit)


def build_local_tool_registry() -> ToolRegistry:
    """Return the initial allow-list of local, read-only Ticksy tools."""
    registry = ToolRegistry()
    read_only = ApprovalLevel.NONE
    registry.register(
        ToolDefinition(
            "get_scan_summary",
            "Return counts and timestamp from the completed local scan.",
            ToolEffect.READ_ONLY,
            read_only,
        ),
        _scan_summary,
    )
    registry.register(
        ToolDefinition(
            "get_stock_status",
            "Return the stored Post, Impending, or failed result for one stock.",
            ToolEffect.READ_ONLY,
            read_only,
            {
                "symbol": ArgumentSpec(
                    str,
                    description="NSE Yahoo symbol or company query",
                )
            },
        ),
        _stock_status,
    )
    registry.register(
        ToolDefinition(
            "get_market_condition",
            "Summarise only the current completed local scan.",
            ToolEffect.READ_ONLY,
            read_only,
        ),
        _market_condition,
    )
    registry.register(
        ToolDefinition(
            "get_backtest_results",
            "Return locally completed Backtester records.",
            ToolEffect.READ_ONLY,
            read_only,
            {"symbols": ArgumentSpec(list, required=False, default=[])},
        ),
        _backtest_results,
    )
    registry.register(
        ToolDefinition(
            "get_calculation_trace",
            "Return formula inputs already stored for a local stock result.",
            ToolEffect.READ_ONLY,
            read_only,
            {"symbol": ArgumentSpec(str)},
        ),
        _calculation_trace,
    )
    registry.register(
        ToolDefinition(
            "get_data_health",
            "Return scan metrics and immutable snapshot identity.",
            ToolEffect.READ_ONLY,
            read_only,
        ),
        _data_health,
    )
    registry.register(
        ToolDefinition(
            "get_rejection_summary",
            "Return readable counts for the most common local scan rejections.",
            ToolEffect.READ_ONLY,
            read_only,
            {
                "limit": ArgumentSpec(
                    int,
                    required=False,
                    description="Maximum number of rejection reasons, from 1 to 10",
                    default=5,
                )
            },
        ),
        _rejection_summary,
    )
    return registry
