"""Confirmation-required actions proposed by Ticksy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AssistantAction:
    """One validated intent that must be confirmed before execution."""

    kind: str
    summary: str
    symbol: str | None = None
    period: str | None = None
    settings: dict | None = None
    target: str | None = None
