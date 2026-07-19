# Business Rules

**Project:** Stock Analyser YF
**Version:** 1.2
**Status:** Active Development

## Purpose

Stock Analyser YF is a production-oriented technical-analysis application for
NSE stocks. It provides configurable scans, transparent data-quality outcomes,
interactive charts, and shareable Streamlit deployment.

## 1. Stock Universe

- A user can select the included `stock_symbols.csv` universe or upload CSV or
  Excel data with a `Symbol` column.
- Symbols must use Yahoo Finance NSE format, for example `RELIANCE.NS`, until
  automatic symbol normalization is implemented.
- The user chooses the number of symbols to scan; the application must report
  the selected universe size and actual number processed.

## 2. Market Data

- Yahoo Finance is the current market-data provider.
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
- The current indicator set includes short and long moving averages, Golden
  Cross, Long-MA 52-week high-to-trough-to-recovery, and price premium above
  the Long MA.
- Indicator values used in results and charts must use the same configuration.

## 5. Scanner Qualification

- A stock qualifies only when every enabled rule passes.
- A disabled rule must not affect qualification or score.
- Each rejected or errored symbol must include its symbol, failed stage, and
  one or more human-readable reasons.

## 6. Mandatory Reversal Rules

- The Short MA must have a positive linear-regression slope across its latest
  five trading sessions.
- The current Short MA must be strictly greater than the current Long MA.
- The latest Golden Cross must be within the configured age limit (80 calendar
  days by default). A Golden Cross occurs when the Short MA changes from less
  than or equal to the Long MA to greater than the Long MA.
- Find the highest Long MA in the last 252 trading sessions, then the lowest
  Long MA after that high.
- The Long MA must have declined from that 52-week high to the trough by at
  least the configured percentage (10% by default). The high-to-trough decline
  must take at least the configured number of trading sessions (60 by default),
  then the current Long MA must be above the trough with a positive Long-MA
  slope across five post-trough trading sessions. The decline is not measured
  from the high to today's Long MA.
- Current Close must be strictly above the Long MA and no more than the
  configured premium above it (10% by default).
- A qualified result retains the cross date, Long-MA high value/date/age,
  trough value/date, Long-MA decline, post-trough five-session slope, and
  current price premium for auditability.

## 7. Optional Rule

- Users may require at least ten completed trading sessions after the Golden
  Cross. This is the only optional qualification rule.

## 8. Fundamentals

- Sector, industry, market capitalization, PE, and EPS are supplemental Yahoo
  Finance fields.
- Fundamental retrieval uses bounded retries and caches successful responses.
- A missing fundamental field remains unavailable; it must not become zero or a
  passing value.
- Fundamental filters are optional and may only run when the required field is
  available.
- For qualified stocks, the dataset includes a Yahoo-industry benchmark: a
  market-cap-weighted P/E, median P/E, and qualifying NSE peer count. Peers
  with missing, zero, or negative P/E are excluded. These benchmarks are
  supplemental context and do not change qualification or score.

## 9. Ranking

- Only qualified stocks receive a final ranking score.
- Score inputs include Golden Cross freshness, MA proximity, current trend,
  and available fundamental context.
- Ranking must not override a failed enabled rule.

## 10. Dashboard and Reporting

- Results show meaningful labels, scan timestamp, symbol, company, sector,
  industry, score, market cap, price, MA values, fundamentals, and cross date.
- Selecting a qualified stock shows one year of price history with short/long
  MAs and a labeled Golden Cross marker when a cross date exists.
- When at least one optional rule is selected, users can view stocks rejected
  by optional checks and their rejection reasons.
- The dashboard must show both qualified and failed stocks with summary counts.
- Exports must include scan settings, timestamps, qualified records, and
  failure reasons.

## 11. Operational Standards

- External errors must be logged with context while avoiding sensitive data.
- Scan duration, symbols processed, provider failures, and cache activity are
  operational metrics.
- The application must be tested before release and deployed from the GitHub
  `main` branch through a controlled release process.

## 12. Data and Investment Disclaimer

- Yahoo Finance is an external provider; availability and field coverage vary
  by symbol and time.
- The system provides analytical information only and does not provide
  investment advice or execution recommendations.
