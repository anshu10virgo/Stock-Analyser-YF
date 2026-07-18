import logging
import time

import yfinance as yf


logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1


class Fundamentals:

    _cache = {}

    @staticmethod
    def empty_result():
        """Return the default result for unavailable Yahoo fundamentals."""
        return {
            "company_name": None,
            "market_cap": None,
            "pe": None,
            "forward_pe": None,
            "eps": None,
            "sector": None,
            "industry": None,
            "revenue_growth": None,
            "earnings_growth": None,
        }

    @staticmethod
    def get_fundamentals(
        symbol
    ):

        if symbol in Fundamentals._cache:
            return Fundamentals._cache[symbol]

        for attempt in range(MAX_RETRIES):
            try:
                ticker = yf.Ticker(symbol)
                info = ticker.get_info()
                if not info:
                    raise ValueError("Yahoo Finance returned no fundamental data")

                market_cap = info.get("marketCap")
                if market_cap is None:
                    try:
                        market_cap = ticker.fast_info.get("market_cap")
                    except Exception as error:
                        logger.debug(
                            "Market-cap fallback failed for %s: %s",
                            symbol,
                            error,
                        )

                result = {
                    "company_name": info.get("longName") or info.get("shortName"),
                    "market_cap": market_cap,
                    "pe": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "eps": info.get("trailingEps"),
                    "sector": info.get("sector"),
                    "industry": info.get("industry"),
                    "revenue_growth": info.get("revenueGrowth"),
                    "earnings_growth": info.get("earningsGrowth"),
                }
                Fundamentals._cache[symbol] = result
                return result
            except Exception as error:
                logger.warning(
                    "Fundamentals request failed for %s (attempt %s/%s): %s",
                    symbol,
                    attempt + 1,
                    MAX_RETRIES,
                    error,
                )

                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

        logger.error("Fundamentals unavailable for %s after retries.", symbol)
        return Fundamentals.empty_result()
