"""Tests for optional fundamental filters and missing-data behaviour."""

import unittest

from models.optional_filter import (
    DEBT_TO_EQUITY,
    EPS_GROWTH,
    HISTORICAL_STOCK_PE,
    MARKET_CAP,
    PEG_RATIO,
    PROFIT_GROWTH,
    RELATIVE_INDUSTRY_PE,
    RETURN_ON_EQUITY,
    OptionalFilterConfig,
)
from models.scan_config import ScanConfig
from services.fundamental_filters import (
    EvaluationStatus,
    FundamentalFilterEvaluator,
)


class FundamentalFilterEvaluatorTests(unittest.TestCase):
    def setUp(self):
        self.evaluator = FundamentalFilterEvaluator()
        self.fundamentals = {
            "pe": 15,
            "market_cap": 100_000_000_000,
            "sector": "Industrials",
            "industry": "Engineering",
        }
        self.industry = {"industry_median_pe": 20}
        self.screener = {
            "pe_average_3y": 18,
            "pe_average_5y": 19,
            "pe_average_10y": 21,
            "profit_growth_3y": 20,
            "profit_growth_5y": 18,
            "profit_growth_10y": 16,
            "eps_growth_3y": 20,
            "eps_growth_5y": 18,
            "eps_growth_10y": 16,
            "debt_to_equity": 0.4,
            "roe": 22,
        }

    def evaluate(self, config, *, fundamentals=None, industry=None, screener=None):
        return self.evaluator.evaluate(
            (config,),
            self.fundamentals if fundamentals is None else fundamentals,
            self.industry if industry is None else industry,
            self.screener if screener is None else screener,
        )[0]

    def test_relative_industry_pe_uses_the_median_benchmark(self):
        config = OptionalFilterConfig(RELATIVE_INDUSTRY_PE)

        passed = self.evaluate(config)
        failed = self.evaluate(
            config,
            fundamentals={**self.fundamentals, "pe": 25},
        )

        self.assertEqual(passed.status, EvaluationStatus.PASS)
        self.assertEqual(failed.status, EvaluationStatus.FAIL)

    def test_relative_industry_pe_is_not_evaluated_when_data_is_missing(self):
        result = self.evaluate(
            OptionalFilterConfig(RELATIVE_INDUSTRY_PE),
            industry={"industry_median_pe": None},
        )

        self.assertEqual(result.status, EvaluationStatus.NOT_EVALUATED)

    def test_historical_pe_ignores_missing_individual_periods(self):
        result = self.evaluate(
            OptionalFilterConfig(HISTORICAL_STOCK_PE),
            screener={
                "pe_average_3y": None,
                "pe_average_5y": 20,
                "pe_average_10y": None,
            },
        )

        self.assertEqual(result.status, EvaluationStatus.PASS)
        self.assertNotIn("unavailable", result.reason.lower())

    def test_historical_pe_fails_when_any_available_period_fails(self):
        result = self.evaluate(
            OptionalFilterConfig(HISTORICAL_STOCK_PE),
            screener={
                "pe_average_3y": 20,
                "pe_average_5y": 14,
                "pe_average_10y": None,
            },
        )

        self.assertEqual(result.status, EvaluationStatus.FAIL)
        self.assertIn("5Y", result.reason)

    def test_historical_pe_is_not_evaluated_without_any_benchmark(self):
        result = self.evaluate(
            OptionalFilterConfig(HISTORICAL_STOCK_PE),
            screener={},
        )

        self.assertEqual(result.status, EvaluationStatus.NOT_EVALUATED)

    def test_growth_evaluates_available_periods_and_ignores_missing_ones(self):
        result = self.evaluate(
            OptionalFilterConfig(EPS_GROWTH, threshold=15),
            screener={
                "eps_growth_3y": None,
                "eps_growth_5y": 18,
                "eps_growth_10y": None,
            },
        )

        self.assertEqual(result.status, EvaluationStatus.PASS)

    def test_growth_is_not_evaluated_when_every_period_is_missing(self):
        result = self.evaluate(
            OptionalFilterConfig(PROFIT_GROWTH, threshold=15),
            screener={},
        )

        self.assertEqual(result.status, EvaluationStatus.NOT_EVALUATED)

    def test_peg_uses_current_pe_and_three_year_profit_growth(self):
        config = OptionalFilterConfig(PEG_RATIO, threshold=1)

        passed = self.evaluate(config)
        failed = self.evaluate(
            config,
            fundamentals={**self.fundamentals, "pe": 25},
        )

        self.assertEqual(passed.status, EvaluationStatus.PASS)
        self.assertEqual(failed.status, EvaluationStatus.FAIL)

    def test_roe_uses_an_inclusive_minimum(self):
        result = self.evaluate(
            OptionalFilterConfig(RETURN_ON_EQUITY, threshold=22)
        )

        self.assertEqual(result.status, EvaluationStatus.PASS)

    def test_debt_filter_is_bypassed_for_financial_companies(self):
        result = self.evaluate(
            OptionalFilterConfig(DEBT_TO_EQUITY, threshold=0.5),
            fundamentals={
                **self.fundamentals,
                "sector": "Financial Services",
                "industry": "Banks—Regional",
            },
            screener={"debt_to_equity": 8},
        )

        self.assertEqual(result.status, EvaluationStatus.PASS)
        self.assertIn("not applied", result.reason)

    def test_market_cap_matches_any_selected_bucket(self):
        result = self.evaluate(
            OptionalFilterConfig(
                MARKET_CAP,
                market_cap_buckets=("mid",),
            )
        )

        self.assertEqual(result.status, EvaluationStatus.PASS)

    def test_market_cap_bucket_boundaries_do_not_overlap(self):
        cases = (
            (20_000, "mid", EvaluationStatus.PASS),
            (20_000, "large", EvaluationStatus.FAIL),
            (5_000, "mid", EvaluationStatus.PASS),
            (5_000, "small", EvaluationStatus.FAIL),
            (500, "small", EvaluationStatus.PASS),
            (499, "micro", EvaluationStatus.PASS),
        )
        for crore, bucket, expected in cases:
            with self.subTest(crore=crore, bucket=bucket):
                result = self.evaluate(
                    OptionalFilterConfig(
                        MARKET_CAP,
                        market_cap_buckets=(bucket,),
                    ),
                    fundamentals={
                        **self.fundamentals,
                        "market_cap": crore * 10_000_000,
                    },
                )
                self.assertEqual(result.status, expected)

    def test_scan_config_rejects_duplicate_filters(self):
        with self.assertRaisesRegex(ValueError, "more than once"):
            ScanConfig(
                short_ma=50,
                long_ma=200,
                max_cross_age=80,
                min_long_ma_decline_duration=60,
                min_long_ma_decline=10,
                max_price_premium=10,
                optional_filters=(
                    OptionalFilterConfig(RELATIVE_INDUSTRY_PE),
                    OptionalFilterConfig(RELATIVE_INDUSTRY_PE),
                ),
            ).validate()

    def test_debt_and_peg_thresholds_are_capped_at_two(self):
        for filter_key in (DEBT_TO_EQUITY, PEG_RATIO):
            with self.subTest(filter_key=filter_key):
                with self.assertRaises(ValueError):
                    OptionalFilterConfig(filter_key, threshold=2.1).validate()


if __name__ == "__main__":
    unittest.main()
