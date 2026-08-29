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

## Completed — Optional Fundamental Filters

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

## Completed — Result Detail and Email Reporting

### Goal

Improve qualified-stock exploration and reproducible sharing without changing
scanner qualification, optional-filter formulas, scoring, or the Historical
P/E and TTM EPS chart.

### Scope

- Show market cap in crore and add debt-to-equity, ROE, and PEG to Company
  Overview while removing P/E Source.
- Present 3Y profit, EPS, and revenue CAGR as separate cards.
- Expand the price/MA chart to all retained history with 6M through Max
  controls, zoom, pan, reset, hover details, and range navigation.
- Email a filters-first workbook containing both result groups to one or more
  session-only recipients.
- Attach maximum-period price/MA charts in size-bounded ZIP parts.

### Acceptance Criteria

- Normal result expansion and report generation make no live Screener request.
- Missing company metrics display as unavailable.
- The workbook sheet order is Filters, Post Golden Cross, then Impending
  Golden Cross.
- SMTP credentials remain in Streamlit Secrets and recipients are not
  persisted.
- Existing technical rules, scoring, and valuation-chart behaviour remain
  unchanged.
- Tests cover display formatting, chart controls, workbook order, recipient
  validation, attachment batching, and SMTP delivery.

## Active Sprint — Historical Golden Cross Backtester

### Goal

Let users replay the active Post Golden Cross strategy against historical
prices for selected Setup-universe stocks, without changing Live Scan results.

**Status: Completed.**

### Scope

- Commit the refreshed ranked stock-universe snapshot and change the Setup
  default from 1,500 to 2,000 stocks, capped by the available universe.
- Add Backtester as the fifth workflow option and rename Results to Golden
  Cross Results.
- Reuse the complete Post Golden Cross rules with point-in-time evaluation:
  actual MA cross, cross age, MA slope, Long-MA decline/recovery, price-above-
  Long-MA, and maximum price premium checks.
- Produce one signal at the first qualifying close after each actual Golden
  Cross; do not repeat it until a new actual cross occurs.
- Enter at the next available trading session's unadjusted Open price.
- Calculate actual historical returns after 1W, 2W, 3W, 1M, 3M, 6M, and 1Y;
  show N/A when the future price history is insufficient.
- Add searchable multi-select stock selection from the Setup universe and 1Y,
  3Y, 5Y, and 10Y test-period controls.
- Show all active strategy parameters, signal-level P/E context, a result row
  for every historical signal, summary metrics, and a selected-stock chart.
- Use the established app theme and Results chart colours: Close navy, Short
  MA teal, and Long MA orange.
- Exclude dividends, fees, slippage, exit rules, re-entry, short positions,
  leverage, and portfolio allocation from this fixed-horizon MVP.

### Acceptance Criteria

- Backtest signals use no data that was unavailable on their signal date.
- Every signal uses the next available Open price as its entry.
- A stock can display multiple historical signals, with no duplicate signal for
  the same actual Golden Cross.
- Historical P/E uses the latest stored observation on or before the signal
  date and does not affect qualification.
- Live Scan session state and results remain independent of Backtester state.
- Results show Signals, Signals with 1Y data, average 1Y return, and median
  1Y return, without a win-rate metric.
- Automated tests cover signal timing, duplicate prevention, entry timing,
  return horizons, historical P/E selection, multi-stock selection, and the
  Setup default handoff.

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

- Filters-first Excel email reports for both qualified result groups.
- Maximum-period chart snapshots with safe attachment batching.
- Saved scan configuration profiles.
- Filters, sorting, and mobile-friendly result exploration.
- Clear scan history and result timestamping.

## Future — Advanced Backtesting

### Goal

Extend the historical Golden Cross backtester from fixed forward-return
measurement into optional trade and portfolio simulation.

### Scope

- Configurable exits: fixed holding period, profit target, stop loss, or a
  Death Cross exit.
- Portfolio allocation: equal allocation, fixed amount per signal, and a
  maximum number of open positions.
- Re-entry: permit a new trade only after the previous trade in that stock has
  exited and a later, new valid Golden Cross signal occurs.
- Keep broker fees, taxes, and slippage out of scope.

### Acceptance Criteria

- Every simulated trade records its entry date, entry price, exit date, exit
  price, exit reason, and realised return.
- Allocation rules never invest more capital than is available.
- Re-entry never duplicates an open trade or reuses the same Golden Cross.
- Fixed-horizon Backtester results remain available independently of this
  optional simulation mode.

## Future — United States Market Expansion

### Goal

Extend Stock Analyser to support a separate United States universe while
preserving the existing NSE workflow and data sets.

### Scope

- Add a market selector for India — NSE and United States — S&P 500.
- Maintain a versioned, market-cap-ranked S&P 500 stock universe with company
  names and exchange tickers.
- Use SEC Company Facts filings for historical annual and quarterly financial
  statements, with bounded retries, fair-use throttling, and auditable refresh
  results.
- Use Yahoo Finance raw historical prices for technical indicators and price-
  based valuation calculations.
- Retain at least ten years of annual history where available and quarterly
  history for the most recent five years where available.
- Calculate US equivalents of the existing fundamental metrics, including
  revenue and profit growth, EPS growth, debt-to-equity, ROE, operating margin,
  P/E, and PEG with clearly documented definitions.
- Keep country-specific field mappings and formula differences explicit rather
  than mixing US and NSE data in one source model.

### Acceptance Criteria

- Users can switch markets without mixing NSE and US symbols, prices, or
  fundamentals.
- The S&P 500 universe and financial snapshots are versioned and reproducible.
- Historical P/E uses raw price and point-in-time trailing EPS, without using
  dividend-adjusted prices.
- Missing, amended, or non-comparable SEC filing data is labelled unavailable
  rather than silently substituted.
- US data refreshes and calculations have automated coverage for mapping,
  point-in-time selection, and formula boundaries.

## Release 1.4 — Production Operations

- Continuous integration for tests and linting.
- Deployment health checks, structured logs, and error monitoring.
- Release tags, changelog, and rollback procedure.
