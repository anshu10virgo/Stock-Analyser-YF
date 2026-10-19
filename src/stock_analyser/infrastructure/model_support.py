"""Provider-neutral instructions and schemas for hosted model adapters."""

from __future__ import annotations

from stock_analyser.agents.contracts import ArgumentSpec, ToolDefinition
from stock_analyser.agents.prompts import (
    SYSTEM_INSTRUCTION,
    TOOL_SELECTION_INSTRUCTION,
)


def argument_schema(spec: ArgumentSpec) -> dict:
    """Translate one local tool argument into a provider-neutral JSON schema."""
    value_types = (
        spec.value_type if isinstance(spec.value_type, tuple) else (spec.value_type,)
    )
    json_types = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    mapped = [json_types.get(value_type, "string") for value_type in value_types]
    schema = {"type": mapped[0] if len(mapped) == 1 else mapped}
    if spec.description:
        schema["description"] = spec.description
    if "array" in mapped:
        schema["items"] = {"type": "string"}
    return schema


def tool_parameters(tool: ToolDefinition) -> dict:
    """Return the closed JSON-object schema shared by both model providers."""
    return {
        "type": "object",
        "properties": {
            name: argument_schema(spec) for name, spec in tool.arguments.items()
        },
        "required": [name for name, spec in tool.arguments.items() if spec.required],
        "additionalProperties": False,
    }


__all__ = [
    "SYSTEM_INSTRUCTION",
    "TOOL_SELECTION_INSTRUCTION",
    "argument_schema",
    "tool_parameters",
]
