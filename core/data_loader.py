from pathlib import Path

import pandas as pd

from providers.yahoo_finance import YahooFinanceHistoryProvider


class DataLoader:

    _history_provider = YahooFinanceHistoryProvider()

    @staticmethod
    def load_symbols(file_source, file_name=None):

        source_name = file_name or str(file_source)
        suffix = Path(source_name).suffix.lower()

        if suffix == ".csv":
            df = pd.read_csv(file_source)
        elif suffix == ".xlsx":
            df = pd.read_excel(file_source)
        else:
            raise ValueError(
                "Stock universe must be a CSV or XLSX file"
            )

        if "Symbol" not in df.columns:
            raise ValueError(
                "Input file must contain Symbol column"
            )

        symbols = (
            df["Symbol"]
            .dropna()
            .astype(str)
            .str.strip()
            .unique()
            .tolist()
        )

        return symbols

    @staticmethod
    def download_batch(symbols, years=3, adjusted_prices=False):
        return DataLoader._history_provider.download_batch(
            symbols,
            years=years,
            adjusted_prices=adjusted_prices,
        )

    @staticmethod
    def get_symbol_history(
        batch_df,
        symbol
    ):

        return DataLoader._history_provider.get_symbol_history(batch_df, symbol)

    @staticmethod
    def market_data_metrics():
        """Return request, cache, retry, and failure counters."""
        return DataLoader._history_provider.metrics()
