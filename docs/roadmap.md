# Roadmap

## Active Sprint — Historical Valuation Foundation

### Goal

Add reproducible historical valuation and long-term fundamental data without
changing current scan qualification or result columns.

### Scope

- Add one bounded-retry Screener provider.
- Add one resumable refresh for historical P/E/TTM EPS, long-term growth,
  P/E averages/medians, debt-to-equity, ROE, and OPM.
- Calculate PEG in the daily Yahoo refresh using stored Screener 3-year profit
  growth.
- Process 10 stocks per batch and wait five seconds between batches by default.
- Publish Git-backed, versioned Screener snapshots through an atomic manifest.
- Show historical P/E and TTM EPS only in the selected-stock chart.
- Keep growth, debt, ROE, OPM, daily PEG, and historical P/E summary fields
  backend-only.
- Preserve all existing mandatory/optional rules, ranking, and result columns.

### Acceptance Criteria

- Normal scans and chart expansion make no live Screener requests.
- Every universe symbol ends as a successful record or an audited failure.
- Interrupted refreshes resume after the last completed batch.
- The chart supports 1M, 6M, 1Y, 3Y, 5Y, and 10Y periods.
- No new Screener field affects qualification, score, exports, or main results.
- Automated tests cover parsing, calculations, throttling, retry, resume,
  storage validation, repository reads, and chart layers.

## Next Sprint — Optional Fundamental Filters

- Add opt-in filters backed by the committed Screener summary dataset.
- Candidate filters include current P/E below historical average/median,
  minimum sales/profit/EPS growth, and maximum debt-to-equity.
- Define missing-data behaviour and UI labels before changing scanner rules.

## Release 1.1 — Reliability and Auditability

- Structured failure results for every symbol and scanner stage.
- Dashboard view for failed stocks and aggregated failure counts.
- Enforce any future optional scanner rules consistently and expose structured
  rejection reasons.
- Derive minimum history requirements from the configured moving averages.
- Automated tests for data loading, scanner rules, and failure handling.

## Release 1.2 — Performance and Data Resilience

- TTL caching for price history, chart data, and fundamentals.
- Batch-level download diagnostics and controlled retry/throttling.
- Data-provider abstraction to support an alternative provider or local store.
- Scan execution metrics: duration, symbols processed, data failures, and
  cache usage.

## Release 1.3 — Reporting and User Experience

- Excel and CSV exports for qualified and rejected stocks.
- Saved scan configuration profiles.
- Filters, sorting, and mobile-friendly result exploration.
- Clear scan history and result timestamping.

## Release 1.4 — Production Operations

- Continuous integration for tests and linting.
- Deployment health checks, structured logs, and error monitoring.
- Release tags, changelog, and rollback procedure.
