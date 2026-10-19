"""Gemini implementation of the hosted-model application port."""

from __future__ import annotations

from collections.abc import Mapping

import requests

from models.assistant import AssistantRequest
from stock_analyser.agents.contracts import ToolCall, ToolDefinition
from stock_analyser.application.ports.model_provider import (
    ModelProviderResponseError,
    ModelProviderTransportError,
)
from stock_analyser.infrastructure.model_support import (
    SYSTEM_INSTRUCTION,
    TOOL_SELECTION_INSTRUCTION,
    tool_parameters,
)


class GeminiProvider:
    """Minimal Gemini REST adapter with no provider-hosted tools enabled."""

    endpoint_template = (
        "https://generativelanguage.googleapis.com/"
        "v1beta/models/{model}:generateContent"
    )

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def respond(self, request: AssistantRequest) -> str:
        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            f"{SYSTEM_INSTRUCTION}\n\n"
                            f"LOCAL CONTEXT\n{request.local_context}"
                        )
                    }
                ]
            },
            "contents": gemini_contents(request),
            "generationConfig": {"maxOutputTokens": 700, "temperature": 0.2},
        }
        response = self._post(payload)
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts).strip()
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise ModelProviderResponseError(
                "Gemini returned an unreadable response."
            ) from error
        if not text:
            raise ModelProviderResponseError("Gemini returned an empty response.")
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
            "contents": gemini_contents(request),
            "tools": [
                {
                    "functionDeclarations": [
                        gemini_tool_definition(tool) for tool in tools
                    ]
                }
            ],
            "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}},
            "generationConfig": {"maxOutputTokens": 300, "temperature": 0},
        }
        response = self._post(payload)
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            return tuple(
                gemini_tool_call(part["functionCall"])
                for part in parts
                if "functionCall" in part
            )
        except (IndexError, KeyError, TypeError, ValueError) as error:
            raise ModelProviderResponseError(
                "Gemini returned an unreadable tool request."
            ) from error

    def _post(self, payload: dict) -> requests.Response:
        try:
            response = requests.post(
                self.endpoint_template.format(model=self.model),
                headers={"x-goog-api-key": self.api_key},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = (
                error.response.status_code if error.response is not None else None
            )
            raise ModelProviderTransportError(
                "Gemini rejected the request.", status_code=status_code
            ) from error
        except requests.RequestException as error:
            raise ModelProviderTransportError(
                "Gemini could not be reached."
            ) from error
        return response


def gemini_contents(request: AssistantRequest) -> list[dict]:
    return [
        {"role": message.role, "parts": [{"text": message.content}]}
        for message in request.messages
    ]


def gemini_tool_definition(tool: ToolDefinition) -> dict:
    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": tool_parameters(tool),
    }


def gemini_tool_call(function_call: Mapping) -> ToolCall:
    arguments = dict(function_call.get("args") or {})
    call_id = function_call.get("id")
    if call_id:
        return ToolCall(
            str(function_call["name"]),
            arguments,
            call_id=str(call_id),
        )
    return ToolCall(str(function_call["name"]), arguments)


__all__ = ["GeminiProvider"]
