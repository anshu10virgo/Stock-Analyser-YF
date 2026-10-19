"""Provider-neutral instructions and schemas for hosted model adapters."""

from __future__ import annotations

from agents.contracts import ArgumentSpec, ToolDefinition


SYSTEM_INSTRUCTION = """You are Ticksy, the Stock Analyser assistant.
Use only the supplied local application context. Do not browse, search the web,
use external news, use RAG, request external market data, or invent values.
Python is the source of truth for all calculations and rule outcomes. Explain
facts concisely using supplied values and dates. Do not give buy, sell, target
price, or price-prediction advice. If local data is missing, say it is not
available in the current project data."""

TOOL_SELECTION_INSTRUCTION = f"""{SYSTEM_INSTRUCTION}
Choose only from the supplied local functions when one or more are needed to
answer the latest request. Do not call a function merely to repeat context that
is already sufficient. Never invent a function name or argument."""


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
