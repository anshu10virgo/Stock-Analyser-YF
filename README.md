# Stock Analyser YF

Stock Analyser YF is a production-oriented Streamlit application for
configurable NSE technical screening using Yahoo Finance market data.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Current capabilities

- Configurable moving-average and Golden Cross scans.
- Adjustable adjusted/unadjusted price basis.
- Yahoo Finance fundamentals with retries and in-memory caching.
- Formatted results, scan timestamps, and one-year interactive charts.
- GitHub-backed Streamlit Community Cloud deployment.
- Selectable live Yahoo or committed Git-snapshot market data.
- Ten-year Git-backed price history with scheduled incremental refresh support.
- Filtered, cached single-symbol chart reads from symbol-grouped Parquet.
- Semiannual Yahoo sector/industry classifications and committed industry P/E.

## Committed market-data refresh

Build the initial ten-year snapshot once:

```powershell
python scripts/refresh_market_data.py --mode full
```

The workflow `.github/workflows/refresh-market-data.yml` then runs incremental
refreshes on weekdays after market close, validates the snapshot, and commits
changed data to `main`. It is also manually runnable in incremental or
classification, or validation-only mode. Sector/industry classifications are
automatically preserved and refreshed every 180 days. See
[Committed Market Data](docs/market_data.md).

## Manual stock-universe refresh

The app does not refresh its stock list automatically. Approximately every six
months, run the following maintenance command locally:

```powershell
python scripts/refresh_stock_universe.py
```

The command downloads NSE's official listed-equities source, keeps the selected
NSE `EQ` series, converts symbols to Yahoo Finance NSE format (`.NS`),
validates that Yahoo provides usable price history, retrieves Yahoo market caps,
and stores the validated universe in descending market-cap order with a market-cap rank. Therefore, the app's Top N choice scans the largest N ranked companies. It then writes:

```text
data/stock_universe/
  manifest.json
  snapshots/nse_equity_YYYY-MM-DD.csv
  validated/yahoo_nse_YYYY-MM-DD.csv
  refresh_reports/YYYY-MM-DD.json
```

The app reads `manifest.json`, which explicitly identifies the active validated
universe and records the count of symbols with stored market-cap ranks. Review
the generated refresh report before committing all generated
files together in a PR, for example:

```text
Refresh NSE Yahoo stock universe — YYYY-MM-DD
```

The script is intentionally not exposed in Streamlit, so a user cannot change
the production universe accidentally.

## Documentation

- [Architecture](docs/architecture.md)
- [Business rules](docs/business_rules.md)
- [Roadmap](docs/roadmap.md)
- [Current TODO](docs/todo.md)
- [Project rules](docs/project_rules.md)
- [Committed market data](docs/market_data.md)
