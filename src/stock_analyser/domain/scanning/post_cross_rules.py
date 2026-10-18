"""Pure rules unique to a confirmed Post Golden Cross setup."""

from __future__ import annotations

from datetime import date

import pandas as pd

from stock_analyser.domain.scanning.indicators import GoldenCrossDetector
from stock_analyser.domain.scanning.models import CrossSetup, RuleFailure


def evaluate_post_cross(
    history: pd.DataFrame,
    max_cross_age: int,
    evaluation_date: date,
) -> tuple[CrossSetup | None, RuleFailure | None]:
    cross = GoldenCrossDetector.find_cross(
        history,
        max_cross_age,
        evaluation_date=evaluation_date,
    )
    if not cross["valid"]:
        return None, RuleFailure(
            "Post Golden Cross Validation",
            "No Golden Cross within the configured age",
        )
    return (
        CrossSetup(
            strategy="Post Golden Cross",
            is_post_cross=True,
            cross=cross,
            cross_date=cross["cross_date"],
        ),
        None,
    )
