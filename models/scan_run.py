"""Aggregated typed output of a scanner run."""

from dataclasses import dataclass, field

import pandas as pd

from models.failure_result import FailureResult
from models.scan_results import ScanResult


@dataclass
class ScanRun:
    """Qualified and rejected symbols from one requested universe."""

    passed: list[ScanResult] = field(default_factory=list)
    impending: list[ScanResult] = field(default_factory=list)
    failed: list[FailureResult] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def as_dataframes(self) -> dict[str, pd.DataFrame]:
        passed_df = pd.DataFrame([record.as_dict() for record in self.passed])
        impending_df = pd.DataFrame([record.as_dict() for record in self.impending])
        failed_df = pd.DataFrame([record.as_dict() for record in self.failed])

        if not passed_df.empty:
            passed_df.sort_values(by="score", ascending=False, inplace=True)
            passed_df.reset_index(drop=True, inplace=True)

        if not impending_df.empty:
            impending_df.sort_values(
                by=["impending_gap_percent", "short_ma_slope"],
                ascending=[True, False],
                inplace=True,
            )
            impending_df.reset_index(drop=True, inplace=True)

        return {
            "passed": passed_df,
            "impending": impending_df,
            "failed": failed_df,
        }
