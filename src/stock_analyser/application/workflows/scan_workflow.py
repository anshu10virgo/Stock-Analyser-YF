"""Coordinate one scan across an injected provider bundle."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from stock_analyser.application.commands.run_scan import RunScan, RunScanCommand
from stock_analyser.domain.scanning.models import ScanRun


@dataclass(frozen=True)
class ScanWorkflowResult:
    run: ScanRun
    provider_metadata: dict


class ScanWorkflow:
    def __init__(self, providers, *, runner_type=RunScan) -> None:
        self._providers = providers
        self._runner_type = runner_type

    def execute(
        self,
        command: RunScanCommand,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        result_callback: Callable[[int, int, ScanRun], None] | None = None,
    ) -> ScanWorkflowResult:
        run = self._runner_type(
            self._providers.history,
            self._providers.fundamentals,
            self._providers.industry_valuation,
            self._providers.screener,
        ).execute(
            command,
            progress_callback=progress_callback,
            result_callback=result_callback,
        )
        return ScanWorkflowResult(run, dict(self._providers.metadata))
