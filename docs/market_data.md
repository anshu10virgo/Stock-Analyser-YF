# Committed Market Data

## Purpose

Normal scans and automated tests should be reproducible without repeatedly
calling Yahoo Finance. The application supports two explicit data sources:

- **Live Yahoo Finance**: temporary rollout and comparison mode.
- **Git snapshot**: committed prices and fundamentals, with Yahoo fallback only
  when a required snapshot file or requested symbol is absent.

Snapshot age does not trigger a live request. Its date is shown in the app and
updated by scheduled maintenance.

## Storage Contract

```text
data/market_data/
  manifest.json
  symbol_coverage.csv
  prices/
    YYYY.parquet   # completed years
    YYYY.csv       # current year
  fundamentals/
    fundamentals.csv
    industry_valuations.csv
```

Retention is ten calendar years. Completed years use immutable compressed
Parquet; the current year remains CSV so incremental Git commits stay efficient.
Raw and adjusted close are stored so either price basis can be applied locally.

The manifest records schema version, universe hash, file hashes, history range,
latest trading date, coverage, and maximum supported Long MA. It is replaced
only after the data files pass validation.

## Commands

```powershell
python scripts/refresh_market_data.py --mode full
python scripts/refresh_market_data.py --mode incremental
python scripts/refresh_market_data.py --mode validate
```

The GitHub Actions workflow runs incremental mode at 18:00 IST on weekdays and
can be manually started in incremental or validation-only mode. A closed-market
run produces no data commit.

## Universe Reconciliation

New symbols receive all available history up to the ten-year limit. Removed
symbols stop receiving updates and are excluded from scans; historical rows are
retained for reproducibility. Unchanged symbols receive only missing sessions.

## Closed-Market Testing

- Validation mode exercises the committed snapshot without Yahoo.
- Tests replay deterministic rows into a temporary directory and verify
  manifest creation, deduplication, and local-only reads.
- Manual incremental mode on a holiday verifies the no-op path and must not
  commit when Yahoo returns no new session.
