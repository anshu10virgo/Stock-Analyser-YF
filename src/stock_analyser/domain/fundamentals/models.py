"""Typed outcomes for provider-independent fundamental analysis."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class EvaluationStatus(str, Enum):
    """Three-state outcome used when fundamental data may be unavailable."""

    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


@dataclass(frozen=True)
class FilterEvaluation:
    """Auditable outcome for one stock and selected fundamental comparison."""

    key: str
    label: str
    status: EvaluationStatus
    reason: str


@dataclass(frozen=True)
class IndustryValuation:
    """Reusable valuation benchmark derived from profitable industry peers."""

    weighted_pe: float | None
    median_pe: float | None
    peer_count: int

    @classmethod
    def unavailable(cls) -> "IndustryValuation":
        return cls(None, None, 0)

    def as_dict(self) -> dict[str, float | int | None]:
        """Return the established scan and snapshot field contract."""
        return {
            "industry_weighted_pe": self.weighted_pe,
            "industry_median_pe": self.median_pe,
            "industry_peer_count": self.peer_count,
        }


__all__ = ["EvaluationStatus", "FilterEvaluation", "IndustryValuation"]
