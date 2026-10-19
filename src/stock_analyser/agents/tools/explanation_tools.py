"""Read-only tools that explain stored deterministic calculations."""

from stock_analyser.agents.contracts import (
    ApprovalLevel,
    ArgumentSpec,
    ToolDefinition,
    ToolEffect,
)
from stock_analyser.agents.execution_context import ExecutionContext
from stock_analyser.agents.tool_registry import ToolRegistry
from stock_analyser.application.queries import get_calculation_trace


def _calculation_trace(context: ExecutionContext, arguments: dict):
    return get_calculation_trace(context.as_mapping(), arguments["symbol"])


def register_explanation_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            "get_calculation_trace",
            "Return formula inputs already stored for a local stock result.",
            ToolEffect.READ_ONLY,
            ApprovalLevel.NONE,
            {"symbol": ArgumentSpec(str)},
        ),
        _calculation_trace,
    )


__all__ = ["register_explanation_tools"]
