"""Tests for compact scan-result and selected-stock detail calculations."""

import unittest

import pandas as pd

from ui.results_page import _performance, prepare_results


class ResultsPageTests(unittest.TestCase):
    def test_main_results_only_include_total_score(self) -> None:
        """Individual scoring components belong in the selected-stock details."""
        results = prepare_results(
            pd.DataFrame(
                [{
                    "symbol": "TEST.NS",
                    "score": 80,
                    "score_cross": 20,
                    "score_slope": 20,
                    "score_distance": 15,
                }]
            )
        )

        self.assertIn("Score", results.columns)
        self.assertNotIn("Cross Score", results.columns)
        self.assertNotIn("Trend Score", results.columns)
        self.assertNotIn("Price Position Score", results.columns)

    def test_performance_includes_since_cross_return(self) -> None:
        """Selected-stock details report return relative to the Golden Cross close."""
        chart_data = pd.DataFrame({"Close": range(100, 170)})

        performance = dict(_performance(chart_data, 100))

        self.assertAlmostEqual(performance["Since Golden Cross"], 69.0)
        self.assertAlmostEqual(performance["1 Week"], (169 / 164 - 1) * 100)


if __name__ == "__main__":
    unittest.main()
