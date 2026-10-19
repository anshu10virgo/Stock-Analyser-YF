"""Small deterministic snapshot datasets generated in temporary test roots."""

import hashlib
import json

import pandas as pd

from stock_analyser.domain.markets import market_definition


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def create_fixture(root, market="IN"):
    universe = root / "data/stock_universe"
    universe.mkdir(parents=True)
    pd.DataFrame({"Symbol": ["TEST.NS", "OTHER.NS"], "Company Name": ["Test", "Other"]}).to_csv(universe / "universe.csv", index=False)
    universe_hash = hashlib.sha256((universe / "universe.csv").read_bytes()).hexdigest()
    write_json(universe / "manifest.json", {"market": market, "active_universe": "universe.csv", "sha256": universe_hash})
    market_root = root / "data/market_data"
    market_root.mkdir()
    dates = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=600)
    closes = [100.0] * 300 + [101.0 + i for i in range(300)]
    prices = pd.DataFrame({"Date": dates, "Symbol": "TEST.NS", "Open": closes,
                           "High": closes, "Low": closes, "Close": closes,
                           "Adj Close": closes, "Volume": 1000})
    other = prices.assign(Symbol="OTHER.NS")
    pd.concat([prices, other]).to_parquet(market_root / "prices.parquet", index=False)
    fundamentals = market_root / "fundamentals"
    fundamentals.mkdir()
    pd.DataFrame([{"symbol": "TEST.NS", "company_name": "Test", "pe": 10, "industry": "Tech"}]).to_csv(fundamentals / "fundamentals.csv", index=False)
    pd.DataFrame([{"industry": "Tech", "industry_median_pe": 20}]).to_csv(fundamentals / "industry_valuations.csv", index=False)
    write_json(market_root / "manifest.json", {
        "market": market, "universe_sha256": universe_hash,
        "price_files": [{"path": "prices.parquet"}],
        "fundamentals_file": {"path": "fundamentals/fundamentals.csv"},
        "industry_valuations_file": {"path": "fundamentals/industry_valuations.csv"},
        "last_trading_date": str(dates[-1].date()),
    })
    screener = market_root / market_definition(market).fundamentals_directory
    screener.mkdir()
    pd.DataFrame([{"symbol": "TEST.NS", "roe": 20}]).to_csv(screener / "summary.csv", index=False)
    pd.DataFrame([{"symbol": "TEST.NS", "date": dates[0], "pe": 10.0, "ttm_eps": 10.0}]).to_parquet(screener / "history.parquet", index=False)
    write_json(screener / "manifest.json", {"market": market, "summary_file": {"path": "summary.csv"}, "history_file": {"path": "history.parquet"}})
