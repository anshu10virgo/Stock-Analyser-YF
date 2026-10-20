"""Characterization tests for Markets and Fundamentals domain boundaries."""

import unittest
from pathlib import Path

from stock_analyser.domain.fundamentals import (
    EvaluationStatus,
    FilterEvaluation,
    IndustryValuation,
    compound_annual_growth_rate,
    debt_to_equity,
    finite_number,
    industry_valuation,
    is_financial_company,
    peg_ratio,
    price_to_earnings,
)
from stock_analyser.domain.markets import (
    market_data_root,
    market_definition,
    stock_key,
)
from stock_analyser.domain.scanning.optional_rules import (
    EvaluationStatus as ScanningEvaluationStatus,
    FilterEvaluation as ScanningFilterEvaluation,
)


class MarketDomainTests(unittest.TestCase):
    def test_market_identity_and_dataset_roots_preserve_existing_contract(self):
        root = Path("project")

        self.assertEqual(market_definition("IN").currency, "INR")
        self.assertEqual(market_definition("US").timezone, "America/New_York")
        self.assertEqual(stock_key("IN", "TCS.NS"), "IN:TCS.NS")
        self.assertEqual(market_data_root(root, "IN"), root)
        self.assertEqual(market_data_root(root, "US"), root / "markets" / "US")

        with self.assertRaisesRegex(ValueError, "IN or US"):
            market_definition("GB")


class FundamentalsDomainTests(unittest.TestCase):
    def test_scanning_reexports_canonical_comparison_outcomes(self):
        self.assertIs(ScanningEvaluationStatus, EvaluationStatus)
        self.assertIs(ScanningFilterEvaluation, FilterEvaluation)

    def test_growth_pe_and_peg_calculations_preserve_positive_input_rules(self):
        self.assertAlmostEqual(
            compound_annual_growth_rate(10, 20, 10),
            ((20 / 10) ** (1 / 10) - 1) * 100,
        )
        self.assertIsNone(compound_annual_growth_rate(-1, 20, 10))
        self.assertEqual(price_to_earnings(100, 5), 20)
        self.assertIsNone(price_to_earnings(100, 0))
        self.assertEqual(peg_ratio(18, 12), 1.5)
        self.assertIsNone(peg_ratio(18, None))

    def test_debt_to_equity_uses_equity_capital_plus_reserves(self):
        self.assertAlmostEqual(debt_to_equity(400, 100, 800), 400 / 900)
        self.assertIsNone(debt_to_equity(400, -100, 50))

    def test_industry_valuation_ignores_invalid_peers(self):
        result = industry_valuation(
            (
                {"market_cap": 1_000, "pe": 10},
                {"market_cap": 100, "pe": 20},
                {"market_cap": 10_000, "pe": -5},
            )
        )

        self.assertEqual(result.peer_count, 2)
        self.assertAlmostEqual(result.weighted_pe, 10.48)
        self.assertEqual(result.median_pe, 15)
        self.assertEqual(
            IndustryValuation.unavailable().as_dict(),
            {
                "industry_weighted_pe": None,
                "industry_median_pe": None,
                "industry_peer_count": 0,
            },
        )

    def test_fundamental_classification_and_number_normalization_are_shared(self):
        self.assertTrue(is_financial_company({"industry": "Private Bank"}))
        self.assertFalse(is_financial_company({"industry": "Software"}))
        self.assertEqual(finite_number("12.5", positive=True), 12.5)
        self.assertIsNone(finite_number(float("nan")))


if __name__ == "__main__":
    unittest.main()
