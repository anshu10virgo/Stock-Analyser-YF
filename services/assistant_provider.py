"""Hosted-model providers for Ticksy with no external data tools."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Protocol

import requests

from agents.contracts import ArgumentSpec, ToolCall, ToolDefinition
from models.assistant import AssistantRequest, AssistantSettings


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


class AssistantProvider(Protocol):
    """Return a plain-language response from one configured provider."""

    def respond(self, request: AssistantRequest) -> str: ...

    def select_tools(
        self,
        request: AssistantRequest,
        tools: tuple[ToolDefinition, ...],
    ) -> tuple[ToolCall, ...]: ...


class DisabledProvider:
    """Safe provider used when no configured API key is available."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def respond(self, request: AssistantRequest) -> str:
        return (
            f"Ticksy is ready for local analysis, but the {self.provider} API key "
            "is not configured. Add it to Streamlit Secrets to enable chat."
        )

    def select_tools(
        self,
        request: AssistantRequest,
        tools: tuple[ToolDefinition, ...],
    ) -> tuple[ToolCall, ...]:
        return ()


class GeminiProvider:
    """Minimal Gemini REST provider with no provider-hosted tools enabled."""

    endpoint_template = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def respond(self, request: AssistantRequest) -> str:
        contents = [
            {"role": message.role, "parts": [{"text": message.content}]}
            for message in request.messages
        ]
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": f"{SYSTEM_INSTRUCTION}\n\nLOCAL CONTEXT\n{request.local_context}"
                    }
                ]
            },
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 700, "temperature": 0.2},
        }
        response = requests.post(
            self.endpoint_template.format(model=self.model),
            headers={"x-goog-api-key": self.api_key},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Gemini returned an unreadable response.") from error
        if not text:
            raise RuntimeError("Gemini returned an empty response.")
        return text

    def select_tools(
        self,
        request: AssistantRequest,
        tools: tuple[ToolDefinition, ...],
    ) -> tuple[ToolCall, ...]:
        if not tools:
            return ()
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            f"{TOOL_SELECTION_INSTRUCTION}\n\n"
                            f"LOCAL CONTEXT\n{request.local_context}"
                        )
                    }
                ]
            },
            "contents": _gemini_contents(request),
            "tools": [
                {
                    "functionDeclarations": [
                        _gemini_tool_definition(tool) for tool in tools
                    ]
                }
            ],
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0},
        }
        response = requests.post(
            self.endpoint_template.format(model=self.model),
            headers={"x-goog-api-key": self.api_key},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            return tuple(
                _gemini_tool_call(part["functionCall"])
                for part in parts
                if "functionCall" in part
            )
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError("Gemini returned an unreadable tool request.") from error


class OpenAIProvider:
    """OpenAI Responses provider using the same local-only request contract."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def respond(self, request: AssistantRequest) -> str:
        payload = {
            "model": self.model,
            "instructions": f"{SYSTEM_INSTRUCTION}\n\nLOCAL CONTEXT\n{request.local_context}",
            "input": [
                {
                    "role": "assistant" if message.role == "model" else message.role,
                    "content": message.content,
                }
                for message in request.messages
            ],
            "max_output_tokens": 700,
        }
        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        try:
            data = response.json()
            text = data.get("output_text") or "".join(
                part.get("text", "")
                for output in data.get("output", [])
                for part in output.get("content", [])
                if part.get("type") == "output_text"
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise RuntimeError("OpenAI returned an unreadable response.") from error
        if not text.strip():
            raise RuntimeError("OpenAI returned an empty response.")
        return text.strip()

    def select_tools(
        self,
        request: AssistantRequest,
        tools: tuple[ToolDefinition, ...],
    ) -> tuple[ToolCall, ...]:
        if not tools:
            return ()
        payload = {
            "model": self.model,
            "instructions": (
                f"{TOOL_SELECTION_INSTRUCTION}\n\n"
                f"LOCAL CONTEXT\n{request.local_context}"
            ),
            "input": _openai_input(request),
            "tools": [_openai_tool_definition(tool) for tool in tools],
            "tool_choice": "auto",
            "max_output_tokens": 300,
        }
        response = requests.post(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        try:
            return tuple(
                _openai_tool_call(item)
                for item in response.json().get("output", [])
                if item.get("type") == "function_call"
            )
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise RuntimeError("OpenAI returned an unreadable tool request.") from error


def _gemini_contents(request: AssistantRequest) -> list[dict]:
    return [
        {"role": message.role, "parts": [{"text": message.content}]}
        for message in request.messages
    ]


def _openai_input(request: AssistantRequest) -> list[dict]:
    return [
        {
            "role": "assistant" if message.role == "model" else message.role,
            "content": message.content,
        }
        for message in request.messages
    ]


def _argument_schema(spec: ArgumentSpec) -> dict:
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


def _tool_parameters(tool: ToolDefinition) -> dict:
    return {
        "type": "object",
        "properties": {
            name: _argument_schema(spec) for name, spec in tool.arguments.items()
        },
        "required": [name for name, spec in tool.arguments.items() if spec.required],
        "additionalProperties": False,
    }


def _gemini_tool_definition(tool: ToolDefinition) -> dict:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": _tool_parameters(tool),
    }


def _gemini_tool_call(function_call: Mapping) -> ToolCall:
    arguments = dict(function_call.get("args") or {})
    call_id = function_call.get("id")
    if call_id:
        return ToolCall(
            str(function_call["name"]),
            arguments,
            call_id=str(call_id),
        )
    return ToolCall(str(function_call["name"]), arguments)


def _openai_tool_definition(tool: ToolDefinition) -> dict:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": _tool_parameters(tool),
        "strict": False,
    }


def _openai_arguments(arguments: str | Mapping | None) -> dict:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        parsed = json.loads(arguments)
    else:
        parsed = dict(arguments)
    if not isinstance(parsed, dict):
        raise ValueError("Function arguments must be an object")
    return parsed


def _openai_tool_call(item: Mapping) -> ToolCall:
    arguments = _openai_arguments(item.get("arguments"))
    call_id = item.get("call_id") or item.get("id")
    if call_id:
        return ToolCall(str(item["name"]), arguments, call_id=str(call_id))
    return ToolCall(str(item["name"]), arguments)


def load_assistant_settings(secrets: Mapping | None = None) -> AssistantSettings:
    """Load provider settings without exposing credentials to the interface."""
    configured = secrets or {}
    assistant = configured.get("assistant", {})
    provider = str(
        assistant.get("provider", os.getenv("ASSISTANT_PROVIDER", "gemini"))
    ).lower()
    gemini_model = str(
        assistant.get("gemini_model", os.getenv("GEMINI_MODEL", "gemini-3.7-flash"))
    )
    openai_model = str(
        assistant.get("openai_model", os.getenv("OPENAI_MODEL", "gpt-5.6-terra"))
    )
    api_key_name = "GEMINI_API_KEY" if provider == "gemini" else "OPENAI_API_KEY"
    api_key = configured.get(api_key_name) or os.getenv(api_key_name)
    model = gemini_model if provider == "gemini" else openai_model
    return AssistantSettings(provider=provider, model=model, api_key=api_key)


def build_provider(settings: AssistantSettings) -> AssistantProvider:
    """Return the selected provider or a safe no-key fallback."""
    if not settings.api_key:
        return DisabledProvider(settings.provider)
    if settings.provider == "gemini":
        return GeminiProvider(settings.api_key, settings.model)
    if settings.provider == "openai":
        return OpenAIProvider(settings.api_key, settings.model)
    return DisabledProvider(settings.provider)
