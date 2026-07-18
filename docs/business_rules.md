# Business Rules

**Project:** Stock Analyser YF
**Version:** 1.1
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
  Cross, MA slope, troughs, 52-week high/low support, and MA distance.
- Indicator values used in results and charts must use the same configuration.

## 5. Scanner Qualification

- A stock qualifies only when every enabled rule passes.
- A disabled rule must not affect qualification or score.
- Each rejected or errored symbol must include its symbol, failed stage, and
  one or more human-readable reasons.

## 6. Golden Cross

- A Golden Cross occurs when the short MA changes from less than or equal to
  the long MA to greater than the long MA.
- It must be within the configured age limit.
- For the configured pre-cross period, the short MA must remain below the long
  MA.
- A qualified result must retain the actual cross date for reporting and charts.

## 7. Trend and Trough Rules

- Long-MA slope and higher-low/trough criteria are configurable rules.
- When enabled, their result must be enforced, not only displayed or scored.
- Trough detection uses the configured lookback and minimum-trough count.

## 8. Price and 52-Week Rules

- Current close must be greater than or equal to the close on the Golden Cross
  date.
- Current close must be greater than or equal to the short MA.
- Current close must be within the configured distance from the long MA.
- Any 52-week distance filter must be configurable, enforced, and reported in
  the failure reason.

## 9. Fundamentals

- Sector, industry, market capitalization, PE, and EPS are supplemental Yahoo
  Finance fields.
- Fundamental retrieval uses bounded retries and caches successful responses.
- A missing fundamental field remains unavailable; it must not become zero or a
  passing value.
- Fundamental filters are optional and may only run when the required field is
  available.

## 10. Ranking

- Only qualified stocks receive a final ranking score.
- Score inputs include Golden Cross freshness, MA proximity, trend, trough
  quality, and available fundamental context.
- Ranking must not override a failed enabled rule.

## 11. Dashboard and Reporting

- Results show meaningful labels, scan timestamp, symbol, company, sector,
  industry, score, market cap, price, MA values, fundamentals, and cross date.
- Selecting a qualified stock shows one year of price history with short/long
  MAs and a labeled Golden Cross marker when a cross date exists.
- The dashboard must show both qualified and failed stocks with summary counts.
- Exports must include scan settings, timestamps, qualified records, and
  failure reasons.

## 12. Operational Standards

- External errors must be logged with context while avoiding sensitive data.
- Scan duration, symbols processed, provider failures, and cache activity are
  operational metrics.
- The application must be tested before release and deployed from the GitHub
  `main` branch through a controlled release process.

## 13. Data and Investment Disclaimer

- Yahoo Finance is an external provider; availability and field coverage vary
  by symbol and time.
- The system provides analytical information only and does not provide
  investment advice or execution recommendations.
