"""OpenAI implementation of the hosted-model application port."""

from __future__ import annotations

import json
from collections.abc import Mapping

import requests

from stock_analyser.agents.models import AssistantRequest
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


class OpenAIProvider:
    """OpenAI Responses adapter using the local-only request contract."""

    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def respond(self, request: AssistantRequest) -> str:
        payload = {
            "model": self.model,
            "instructions": (
                f"{SYSTEM_INSTRUCTION}\n\n"
                f"LOCAL CONTEXT\n{request.local_context}"
            ),
            "input": openai_input(request),
            "max_output_tokens": 700,
        }
        response = self._post(payload)
        try:
            data = response.json()
            text = data.get("output_text") or "".join(
                part.get("text", "")
                for output in data.get("output", [])
                for part in output.get("content", [])
                if part.get("type") == "output_text"
            )
        except (AttributeError, TypeError, ValueError) as error:
            raise ModelProviderResponseError(
                "OpenAI returned an unreadable response."
            ) from error
        if not text.strip():
            raise ModelProviderResponseError("OpenAI returned an empty response.")
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
            "input": openai_input(request),
            "tools": [openai_tool_definition(tool) for tool in tools],
            "tool_choice": "auto",
            "max_output_tokens": 300,
        }
        response = self._post(payload)
        try:
            return tuple(
                openai_tool_call(item)
                for item in response.json().get("output", [])
                if item.get("type") == "function_call"
            )
        except (AttributeError, KeyError, TypeError, ValueError) as error:
            raise ModelProviderResponseError(
                "OpenAI returned an unreadable tool request."
            ) from error

    def _post(self, payload: dict) -> requests.Response:
        try:
            response = requests.post(
                self.endpoint,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
        except requests.HTTPError as error:
            status_code = (
                error.response.status_code if error.response is not None else None
            )
            raise ModelProviderTransportError(
                "OpenAI rejected the request.", status_code=status_code
            ) from error
        except requests.RequestException as error:
            raise ModelProviderTransportError(
                "OpenAI could not be reached."
            ) from error
        return response


def openai_input(request: AssistantRequest) -> list[dict]:
    return [
        {
            "role": "assistant" if message.role == "model" else message.role,
            "content": message.content,
        }
        for message in request.messages
    ]


def openai_tool_definition(tool: ToolDefinition) -> dict:
    return {
        "type": "function",
        "name": tool.name,
        "description": tool.description,
        "parameters": tool_parameters(tool),
        "strict": False,
    }


def openai_arguments(arguments: str | Mapping | None) -> dict:
    if arguments is None:
        return {}
    if isinstance(arguments, str):
        parsed = json.loads(arguments)
    else:
        parsed = dict(arguments)
    if not isinstance(parsed, dict):
        raise ValueError("Function arguments must be an object")
    return parsed


def openai_tool_call(item: Mapping) -> ToolCall:
    arguments = openai_arguments(item.get("arguments"))
    call_id = item.get("call_id") or item.get("id")
    if call_id:
        return ToolCall(str(item["name"]), arguments, call_id=str(call_id))
    return ToolCall(str(item["name"]), arguments)


__all__ = ["OpenAIProvider"]
