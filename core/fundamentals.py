import yfinance as yf


class Fundamentals:

    @staticmethod
    def get_fundamentals(
        symbol
    ):

        try:

            ticker = yf.Ticker(symbol)

            info = ticker.info

            return {

                "market_cap":
                    info.get("marketCap"),

                "pe":
                    info.get("trailingPE"),

                "forward_pe":
                    info.get("forwardPE"),

                "eps":
                    info.get("trailingEps"),

                "sector":
                    info.get("sector"),

                "industry":
                    info.get("industry"),

                "revenue_growth":
                    info.get("revenueGrowth"),

                "earnings_growth":
                    info.get("earningsGrowth")

            }

        except Exception:

            return {
                "market_cap": None,
                "pe": None,
                "forward_pe": None,
                "eps": None,
                "sector": None,
                "industry": None,
                "revenue_growth": None,
                "earnings_growth": None
            }