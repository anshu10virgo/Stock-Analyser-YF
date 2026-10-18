"""Compatibility exports for the canonical scanning-domain optional rules.

New code should import from ``stock_analyser.domain.scanning.optional_rules``.
This module remains temporarily so existing callers keep working during the
package migration.
"""

from stock_analyser.domain.scanning.optional_rules import (
    FILTER_LABELS,
    EvaluationStatus,
    FilterEvaluation,
    FundamentalFilterEvaluator,
)

__all__ = [
    "FILTER_LABELS",
    "EvaluationStatus",
    "FilterEvaluation",
    "FundamentalFilterEvaluator",
]
