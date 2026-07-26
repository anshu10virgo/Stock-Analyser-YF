# Business Rules

**Project:** Stock Analyser YF
**Version:** 1.4
**Status:** Active Development

## Purpose

Stock Analyser YF is a production-oriented technical-analysis application for
NSE stocks. It provides configurable scans, transparent data-quality outcomes,
interactive charts, and shareable Streamlit deployment.

## 1. Stock Universe

- A user can select the manifest-controlled, validated NSE stock universe or
  upload CSV or Excel data with a `Symbol` column.
- Symbols must use Yahoo Finance NSE format, for example `RELIANCE.NS`, until
  automatic symbol normalization is implemented.
- The user chooses the number of symbols to scan; the application must report
  the selected universe size and actual number processed.

## 2. Market Data

- Yahoo Finance is the current price, current-fundamentals, classification, and
  industry-valuation provider.
- Screener supplies a separately refreshed committed snapshot for historical
  P/E, historical TTM EPS, and backend-only long-term fundamentals.
- Users can choose adjusted or unadjusted prices. Unadjusted closing prices are
  the default for technical signals.
- Market-data, chart-data, and fundamental-data failures must be observable and
  must not be represented as successful scan results.
- A scan records its timestamp and price basis.

## 3. Historical Data

- A symbol must have enough complete OHLCV history for every enabled indicator.
- The minimum required history must be derived from the configured longest MA
  and rule lookbacks.
- Missing, malformed, or unavailable history rejects the symbol with a data
  failure reason.

## 4. Technical Indicators

- Indicators are calculated from the selected price basis.
- The current indicator set includes short and long moving averages, Post and
  Impending Golden Cross states, Long-MA 52-week
  high-to-trough-to-recovery, and price premium above the Long MA.
- Indicator values used in results and charts must use the same configuration.

## 5. Scanner Qualification

- A stock qualifies only when every enabled rule passes.
- A disabled rule must not affect qualification or score.
- Each rejected or errored symbol must include its symbol, failed stage, and
  one or more human-readable reasons.

## 6. Common Golden Cross Mandatory Rules

- The Short MA must have a positive linear-regression slope across its latest
  five trading sessions.
- Find the highest Long MA in the last 252 trading sessions, then the lowest
  Long MA after that high.
- The Long MA must have declined from that 52-week high to the trough by at
  least the configured percentage (10% by default). The high-to-trough decline
  must take at least the configured number of trading sessions (60 by default).
  The decline is not measured from the high to
  today's Long MA.
- Current Close must be strictly above the Long MA and no more than the
  configured premium above it (10% by default).
- A qualified result retains the Long-MA high value/date/age,
  trough value/date, Long-MA decline, post-trough five-session slope, and
  current price premium for auditability.

## 7. Post Golden Cross Mandatory Rules

- The current Short MA must be strictly greater than the current Long MA.
- The latest Golden Cross must be within the configured age limit (80 calendar
  days by default). A Golden Cross occurs when the Short MA changes from less
  than or equal to the Long MA to greater than the Long MA.
- The current Long MA must be strictly above its post-decline trough and its
  latest five-session post-trough linear-regression slope must be positive.
- Post Golden Cross results retain their cross date, cross age, ranking score,
  and scoring breakdown.

## 8. Impending Golden Cross Mandatory Rules

- Impending evaluation is disabled by default and runs only when selected by
  the user. Its qualified stocks are reported separately from Post Golden
  Cross stocks.
- The current Short MA must be less than or equal to the current Long MA.
- The Short-MA five-session linear-regression slope must be positive and
  strictly greater than the Long-MA five-session slope.
- The gap `(Long MA - Short MA) / Long MA * 100` must not exceed the configured
  threshold (3% by default).
- During every completed session in the configured validation period before
  today (20 trading sessions by default), Short MA must be strictly below Long
  MA.
- Current Long MA must be at or above its post-decline trough and its latest
  five-session linear-regression slope must be non-negative.
- Current Close must be strictly above both moving averages. The common 10%
  maximum premium continues to be measured relative to Long MA.
- Impending results are ordered by the smallest MA gap and then the strongest
  Short-MA slope. They do not receive the Post-Cross scoring model.

## 9. Optional Fundamental Rules

- No optional filter is enabled by default. With an empty optional-filter
  sequence, qualification is identical to the mandatory-only scan.
- Selected filters use AND logic. Their display order controls audit and
  rejection reporting, not the mathematical result.
- The available filters are:
  - current stock P/E below the current median Industry P/E;
  - current stock P/E below its own available 3Y, 5Y, and 10Y average P/E;
  - PEG at or below a configurable maximum (1.0 default, 2.0 ceiling);
  - available 3Y, 5Y, and 10Y profit growth above a configurable minimum;
  - available 3Y, 5Y, and 10Y EPS growth above a configurable minimum;
  - available 3Y, 5Y, and 10Y sales growth above a configurable minimum;
  - ROE at or above a configurable minimum;
  - debt-to-equity at or below a configurable maximum (0.5 default, 2.0
    ceiling);
  - selected Indian market-cap buckets or a custom range in crore.
- The historical P/E rule uses the stock's own average P/E benchmarks, not a
  historical industry series. Missing individual periods are ignored. The
  stock fails when any available period fails.
- Growth rules use the same partial-history policy: every available period
  must pass, while unavailable individual periods are ignored.
- Debt-to-equity is not applied to banks and financial companies because
  deposits and borrowing are operating inputs and ordinary corporate D/E is
  not comparable.
- The previous optional requirement for ten completed post-cross sessions has
  been removed.
- Optional filters never alter the technical score.

### Missing Optional Data

- Each selected filter produces `pass`, `fail`, or `not evaluated`.
- A confirmed failure rejects the stock as an optional-check rejection.
- `Not evaluated` retains the stock in its existing Post or Impending result
  group and adds one filter-level availability label.
- Missing 3Y, 5Y, or 10Y periods are not shown as separate tags.
- No third result group is created for incomplete fundamental data.

## 10. Fundamentals

- Sector, industry, market capitalization, PE, and EPS are supplemental Yahoo
  Finance fields.
- Fundamental retrieval uses bounded retries and caches successful responses.
- A missing fundamental field remains unavailable; it must not become zero or a
  passing value.
- Fundamental filters run only when selected. Missing required data produces
  `not evaluated` and retains the stock; it never becomes zero, pass, or fail.
- For qualified stocks, the dataset includes a Yahoo-industry benchmark: a
  market-cap-weighted P/E, median P/E, and qualifying NSE peer count. Peers
  with missing, zero, or negative P/E are excluded. These benchmarks are
  supplemental context and do not change qualification or score.
- Screener-derived P/E averages, sales growth, profit growth, EPS growth,
  debt-to-equity, and ROE support the opt-in filters. P/E medians and latest
  OPM remain stored context and do not currently affect qualification.
- Debt-to-equity is calculated from Screener balance-sheet values as
  `Borrowings / (Equity Capital + Reserves)`. It is a financial-reporting
  metric, not a daily market metric.
- ROE is read from Screener's current top-ratio card. OPM is the latest
  available value in Screener's annual/TTM Profit & Loss table.
- PEG is recalculated in the daily Yahoo snapshot as
  `refreshed Yahoo P/E / stored Screener 3-year compounded profit growth`.
  The P/E uses Yahoo `trailingPE`, with the existing
  `market price / trailing EPS` fallback when necessary.
  It is left blank when the active Screener snapshot has no positive 3-year
  growth value or the refreshed Yahoo P/E is unavailable or non-positive.
- EPS CAGR is unavailable when either endpoint is missing, zero, or negative.

## 11. Ranking

- Only qualified Post Golden Cross stocks receive the current final ranking
  score.
- Score inputs include Golden Cross freshness, MA proximity, current trend,
  and available fundamental context.
- Ranking must not override a failed enabled rule.

## 12. Dashboard and Reporting

- Results show separate Post and Impending Golden Cross sections with
  meaningful labels, scan timestamp, symbol, company, sector,
  industry, score, market cap, price, MA values, fundamentals, and cross date.
- Selecting a qualified stock shows one year of price history with short/long
  MAs and a labeled Golden Cross marker when a cross date exists.
- Selecting a qualified stock also shows committed historical P/E and TTM EPS
  only in the dedicated valuation chart. It does not expose the backend-only
  long-term growth or debt fields.
- When at least one optional rule is selected, users can view stocks rejected
  by optional checks and their rejection reasons. Retained stocks identify
  filters that could not be evaluated without listing missing individual
  historical periods.
- The dashboard must show both qualified and failed stocks with summary counts.
- Exports must include scan settings, timestamps, qualified records, and
  failure reasons.

## 13. Operational Standards

- External errors must be logged with context while avoiding sensitive data.
- The unified Screener refresh processes configurable batches (10 stocks by
  default), waits five seconds between batches, records per-symbol failures,
  and resumes from its latest completed batch.
- Normal scans and chart interactions must not make live Screener requests.
- A scan loads and indexes the committed Screener summary at most once, and
  only when a selected optional filter requires it.
- A failed scheduled market-data refresh must attempt to notify the configured
  operator by email without exposing SMTP credentials in code or logs.
- Scan duration, symbols processed, provider failures, and cache activity are
  operational metrics.
- The application must be tested before release and deployed from the GitHub
  `main` branch through a controlled release process.

## 14. Data and Investment Disclaimer

- Yahoo Finance is an external provider; availability and field coverage vary
  by symbol and time.
- The system provides analytical information only and does not provide
  investment advice or execution recommendations.
