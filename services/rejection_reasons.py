"""Compatibility exports for application rejection explanations."""

from stock_analyser.application.queries.explain_failure import (
    REJECTION_LABELS,
    friendly_rejection,
)

__all__ = ["REJECTION_LABELS", "friendly_rejection"]
