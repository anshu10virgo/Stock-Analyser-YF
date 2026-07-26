# Roadmap

## Completed — Historical Valuation Foundation

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

## Active Sprint — Optional Fundamental Filters

### Goal

Add empty-by-default fundamental screening without changing mandatory
technical qualification, technical scoring, or the two result groups.

### Scope

- Add an ordered dropdown builder for nine valuation, growth, quality, and
  company-size filters.
- Use the current median Industry P/E for the relative valuation rule.
- Compare current P/E with the stock's own available 3Y/5Y/10Y average P/E.
- Apply three-state evaluation with lenient missing-data handling.
- Load the committed Screener summary once only when selected filters need it.
- Retain incomplete-data stocks with filter-level availability labels.
- Remove the legacy optional ten-post-cross-session rule.
- Persist optional settings only in active Streamlit session strategies.

### Acceptance Criteria

- No selected filters produces the same results as the existing scan.
- Confirmed failures reject with readable optional-check reasons.
- Missing individual historical periods do not create tags.
- Completely unavailable filter data retains the stock with one filter-level
  label.
- Post and Impending Golden Cross remain the only result groups.
- Optional filters do not affect score.
- Normal scans make no live Screener requests.
- Automated tests cover rule boundaries, partial history, missing snapshots,
  session reruns, and result formatting.

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
