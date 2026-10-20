"""Characterization tests for the extracted scanning domain."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from core.golden_cross import GoldenCrossDetector as LegacyGoldenCrossDetector
from core.indicators import Indicators as LegacyIndicators
from core.scoring import ScoringEngine as LegacyScoringEngine
from core.slope_analyzer import SlopeAnalyzer as LegacySlopeAnalyzer
from models.scan_config import ScanConfig as LegacyScanConfig
from services.fundamental_filters import (
    FundamentalFilterEvaluator as LegacyFilterEvaluator,
)
from stock_analyser.domain.scanning.impending_cross_rules import (
    evaluate_impending_cross,
)
from stock_analyser.domain.scanning.indicators import (
    GoldenCrossDetector,
    Indicators,
    SlopeAnalyzer,
)
from stock_analyser.domain.scanning.models import ScanConfig
from stock_analyser.domain.scanning.optional_rules import FundamentalFilterEvaluator
from stock_analyser.domain.scanning.post_cross_rules import evaluate_post_cross
from stock_analyser.domain.scanning.reversal_rules import evaluate_long_ma_reversal
from stock_analyser.domain.scanning.scoring import ScoringEngine


class ScanningDomainTests(unittest.TestCase):
    def test_legacy_imports_resolve_to_canonical_domain_types(self):
        self.assertIs(LegacyScanConfig, ScanConfig)
        self.assertIs(LegacyIndicators, Indicators)
        self.assertIs(LegacySlopeAnalyzer, SlopeAnalyzer)
        self.assertIs(LegacyGoldenCrossDetector, GoldenCrossDetector)
        self.assertIs(LegacyScoringEngine, ScoringEngine)
        self.assertIs(LegacyFilterEvaluator, FundamentalFilterEvaluator)

    def test_reversal_rule_returns_typed_high_trough_and_recovery(self):
        index = pd.bdate_range("2025-01-01", periods=12)
        history = pd.DataFrame(
            {"MA_LONG": [100, 99, 97, 94, 90, 88, 88.2, 88.5, 89, 90, 91, 92]},
            index=index,
        )

        result = evaluate_long_ma_reversal(
            history,
            high_window_sessions=12,
            recovery_slope_sessions=5,
        )

        self.assertEqual(result.peak_value, 100)
        self.assertEqual(result.trough_value, 88)
        self.assertEqual(result.decline_duration, 5)
        self.assertAlmostEqual(result.decline_percent, 12)
        self.assertTrue(result.recovering)

    def test_post_cross_rule_preserves_detector_outcome(self):
        expected = {
            "valid": True,
            "cross_date": pd.Timestamp("2026-10-01"),
            "days_since_cross": 18,
        }
        with patch.object(GoldenCrossDetector, "find_cross", return_value=expected):
            setup, failure = evaluate_post_cross(
                pd.DataFrame(),
                80,
                pd.Timestamp("2026-10-19").date(),
            )

        self.assertIsNone(failure)
        self.assertTrue(setup.is_post_cross)
        self.assertEqual(setup.cross, expected)

    def test_impending_rule_preserves_gap_and_validation_boundaries(self):
        index = pd.bdate_range("2026-09-01", periods=21)
        long_ma = pd.Series([100.0] * 21, index=index)
        short_ma = pd.Series([98.0] * 16 + [98.0, 98.4, 98.8, 99.2, 99.6], index=index)
        history = pd.DataFrame({"MA_SHORT": short_ma, "MA_LONG": long_ma})

        setup, failure = evaluate_impending_cross(
            history,
            short_ma_slope=0.4,
            long_ma_slope=0,
            maximum_gap_percent=3,
            validation_sessions=20,
        )

        self.assertIsNone(failure)
        self.assertFalse(setup.is_post_cross)
        self.assertAlmostEqual(setup.gap_percent, 0.4)


if __name__ == "__main__":
    unittest.main()
