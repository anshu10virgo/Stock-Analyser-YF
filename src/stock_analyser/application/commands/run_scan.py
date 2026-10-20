"""Run the scanner through an explicit application command."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from stock_analyser.application.scanning import ScanService
from stock_analyser.domain.scanning.models import ScanConfig, ScanRun


@dataclass(frozen=True)
class RunScanCommand:
    symbols: tuple[str, ...]
    config: ScanConfig

    @classmethod
    def create(
        cls, symbols: Iterable[str], config: ScanConfig
    ) -> "RunScanCommand":
        return cls(tuple(symbols), config)


class RunScan:
    """Application boundary around the temporary ``ScanService`` facade."""

    def __init__(
        self,
        market_data,
        fundamentals,
        industry_valuation,
        screener,
        *,
        service_type=ScanService,
    ) -> None:
        self._market_data = market_data
        self._fundamentals = fundamentals
        self._industry_valuation = industry_valuation
        self._screener = screener
        self._service_type = service_type

    def execute(
        self,
        command: RunScanCommand,
        *,
        progress_callback: Callable[[int, int], None] | None = None,
        result_callback: Callable[[int, int, ScanRun], None] | None = None,
    ) -> ScanRun:
        service = self._service_type(
            command.config,
            data_provider=self._market_data,
            fundamentals_provider=self._fundamentals,
            industry_valuation_service=self._industry_valuation,
            screener_provider=self._screener,
        )
        return service.scan(
            command.symbols,
            progress_callback=progress_callback,
            result_callback=result_callback,
        )
