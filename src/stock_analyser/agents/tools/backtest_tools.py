"""Read-only tools over completed local Backtester results."""

from stock_analyser.agents.contracts import (
    ApprovalLevel,
    ArgumentSpec,
    ToolDefinition,
    ToolEffect,
)
from stock_analyser.agents.execution_context import ExecutionContext
from stock_analyser.agents.tool_registry import ToolRegistry
from stock_analyser.application.queries import get_backtest_results


def _backtest_results(context: ExecutionContext, arguments: dict):
    symbols = arguments.get("symbols") or None
    return get_backtest_results(context.as_mapping(), symbols)


def register_backtest_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            "get_backtest_results",
            "Return locally completed Backtester records.",
            ToolEffect.READ_ONLY,
            ApprovalLevel.NONE,
            {"symbols": ArgumentSpec(list, required=False, default=[])},
        ),
        _backtest_results,
    )


__all__ = ["register_backtest_tools"]
