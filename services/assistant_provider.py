"""Hosted-model providers for Ticksy with no external data tools."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Protocol

import requests

from models.assistant import AssistantRequest, AssistantSettings


SYSTEM_INSTRUCTION = """You are Ticksy, the Stock Analyser assistant.
Use only the supplied local application context. Do not browse, search the web,
use external news, use RAG, request external market data, or invent values.
Python is the source of truth for all calculations and rule outcomes. Explain
facts concisely using supplied values and dates. Do not give buy, sell, target
price, or price-prediction advice. If local data is missing, say it is not
available in the current project data."""


class AssistantProvider(Protocol):
    """Return a plain-language response from one configured provider."""

    def respond(self, request: AssistantRequest) -> str: ...


class DisabledProvider:
    """Safe provider used when no configured API key is available."""

    def __init__(self, provider: str) -> None:
        self.provider = provider

    def respond(self, request: AssistantRequest) -> str:
        return (
            f"Ticksy is ready for local analysis, but the {self.provider} API key "
            "is not configured. Add it to Streamlit Secrets to enable chat."
        )


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
            "system_instruction": {
                "parts": [{"text": f"{SYSTEM_INSTRUCTION}\n\nLOCAL CONTEXT\n{request.local_context}"}]
            },
            "contents": contents,
            "generationConfig": {"maxOutputTokens": 700, "temperature": 0.2},
        }
        response = requests.post(
            self.endpoint_template.format(model=self.model),
            params={"key": self.api_key},
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
                {"role": "assistant" if message.role == "model" else message.role, "content": message.content}
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


def load_assistant_settings(secrets: Mapping | None = None) -> AssistantSettings:
    """Load provider settings without exposing credentials to the interface."""
    configured = secrets or {}
    assistant = configured.get("assistant", {})
    provider = str(assistant.get("provider", os.getenv("ASSISTANT_PROVIDER", "gemini"))).lower()
    gemini_model = str(assistant.get("gemini_model", os.getenv("GEMINI_MODEL", "gemini-3.7-flash")))
    openai_model = str(assistant.get("openai_model", os.getenv("OPENAI_MODEL", "gpt-5.6-terra")))
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
