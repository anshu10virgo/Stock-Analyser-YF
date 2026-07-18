from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf


class DataLoader:

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

        end_date = datetime.today()

        start_date = (
            end_date
            - timedelta(days=365 * years)
        )

        data = yf.download(
            tickers=symbols,
            start=start_date,
            end=end_date,
            auto_adjust=adjusted_prices,
            group_by="ticker",
            progress=False,
            threads=True
        )

        return data

    @staticmethod
    def get_symbol_history(
        batch_df,
        symbol
    ):

        try:

            if isinstance(
                batch_df.columns,
                pd.MultiIndex
            ):
                df = batch_df[symbol].copy()
            else:
                df = batch_df.copy()

            df.dropna(inplace=True)

            return df

        except Exception:

            return pd.DataFrame()
