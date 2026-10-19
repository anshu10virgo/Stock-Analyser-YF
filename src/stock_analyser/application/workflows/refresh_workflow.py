"""Provider-independent sequencing for future refresh job adapters."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RefreshStep:
    name: str
    execute: Callable[[], Any]


class RefreshWorkflow:
    """Run named refresh stages in order and stop on the first failure."""

    def __init__(self, steps: tuple[RefreshStep, ...]) -> None:
        self._steps = steps

    def execute(self) -> dict[str, Any]:
        return {step.name: step.execute() for step in self._steps}
