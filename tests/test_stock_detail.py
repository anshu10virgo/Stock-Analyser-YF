"""Tests for the interactive full-history price chart."""

import unittest

import pandas as pd

from ui.stock_detail import build_stock_detail_figure


class StockDetailTests(unittest.TestCase):
    def test_price_chart_has_period_buttons_slider_and_zoom(self):
        index = pd.date_range("2020-01-01", periods=300, freq="B")
        values = pd.Series(range(100, 400), index=index, dtype=float)
        chart = pd.DataFrame(
            {
                "Open": values - 1,
                "High": values + 1,
                "Low": values - 2,
                "Close": values,
                "MA_SHORT": values.rolling(5).mean(),
                "MA_LONG": values.rolling(20).mean(),
            }
        )

        figure = build_stock_detail_figure("TEST.NS", chart, index[200])
        labels = [
            button.label for button in figure.layout.xaxis.rangeselector.buttons
        ]

        self.assertEqual(labels, ["6M", "1Y", "3Y", "5Y", "10Y", "Max"])
        self.assertTrue(figure.layout.xaxis.rangeslider.visible)
        self.assertEqual(figure.layout.dragmode, "zoom")


if __name__ == "__main__":
    unittest.main()
