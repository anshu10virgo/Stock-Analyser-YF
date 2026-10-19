"""Read-only tools for local scan and snapshot health."""

from stock_analyser.agents.contracts import (
    ApprovalLevel,
    ToolDefinition,
    ToolEffect,
)
from stock_analyser.agents.execution_context import ExecutionContext
from stock_analyser.agents.tool_registry import ToolRegistry
from stock_analyser.application.queries import get_data_health


def _data_health(context: ExecutionContext, _arguments: dict):
    return get_data_health(
        context.as_mapping(), snapshot_identity=context.snapshot_identity
    )


def register_data_health_tools(registry: ToolRegistry) -> None:
    registry.register(
        ToolDefinition(
            "get_data_health",
            "Return scan metrics and immutable snapshot identity.",
            ToolEffect.READ_ONLY,
            ApprovalLevel.NONE,
        ),
        _data_health,
    )


__all__ = ["register_data_health_tools"]
