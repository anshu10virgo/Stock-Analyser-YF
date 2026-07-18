# Business Rules

**Project:** Stock Analyser YF  
**Version:** 1.0  
**Status:** Completed (Proof of Concept)

---

# Purpose

This document defines the business rules implemented in Stock Analyser YF.

The objective of this project was to validate the stock screening logic and user interface before developing the production-grade NSE Bhavcopy platform.

Unlike Project 2, this project does **not** maintain a local database. Historical data is downloaded from Yahoo Finance whenever a scan is executed.

---

# 1. Stock Universe

## Business Rules

- The stock universe is provided by the user through a CSV or Excel file.
- Each record must contain a valid NSE stock symbol.
- Symbols are automatically converted to Yahoo Finance format (e.g., `RELIANCE` → `RELIANCE.NS`).
- Invalid or unavailable symbols are skipped and reported in the failure log.

---

# 2. Market Data

## Business Rules

- Yahoo Finance is the primary market data provider.
- Historical data is downloaded on demand for each stock.
- The user can choose adjusted or unadjusted Yahoo closing prices. Unadjusted
  prices are the default for technical signals.
- No market data is stored locally.
- Every scan retrieves the latest available data from Yahoo Finance.
- Historical data exists only during the execution of the scan.

---

# 3. Historical Data

## Business Rules

- Sufficient historical data must be available to calculate all configured moving averages.
- If the downloaded history is insufficient, the stock is rejected.
- Missing or incomplete historical data results in the stock being excluded from the analysis.

---

# 4. Technical Indicator Rules

## Business Rules

Technical indicators are calculated dynamically using downloaded historical data.

The scanner currently supports:

- Short Moving Average
- Long Moving Average
- Golden Cross Detection
- Long Moving Average Trend
- Trough Detection
- 52 Week High
- 52 Week Low

No technical indicators are stored permanently.

---

# 5. Scanner Rules

## Business Rules

A stock qualifies only if all enabled rules are satisfied.

The scanner is fully configurable through the Streamlit dashboard.

Supported configurable parameters include:

- Short Moving Average Period
- Long Moving Average Period
- Golden Cross Age
- Price Distance from Long MA
- Pre-Cross Validation Days
- Long MA Slope Lookback
- Trough Lookback
- Minimum Trough Count

---

# 6. Golden Cross Rules

## Business Rules

Golden Cross is identified when:

- Short Moving Average crosses above the Long Moving Average.

Validation Rules:

- The Golden Cross must occur within the configured number of days.
- Before crossing, the Short MA should remain below the Long MA.
- After crossing, the Short MA should remain above the Long MA.

---

# 7. Pre-Golden Cross Validation

## Business Rules

Before the Golden Cross:

- Short Moving Average must remain below the Long Moving Average for the configured validation period.
- Stocks violating this rule are rejected.

---

# 8. Long Moving Average Trend Rule

## Business Rules

Before the Golden Cross:

- Long Moving Average should be declining.

After the Golden Cross:

- Long Moving Average should begin rising.

The slope calculation period is configurable.

---

# 9. Trough Detection Rule

## Business Rules

Before the Golden Cross:

- Price should form the configured minimum number of troughs.
- Troughs are detected within the configurable lookback period.

---

# 10. Price Validation Rules

## Business Rules

The current market price must satisfy all of the following:

- Close Price > Long Moving Average
- Current Price must remain within the configured percentage distance from the Long Moving Average

Stocks violating either condition are rejected.

---

# 11. 52 Week High Rule

## Business Rules

The scanner calculates:

- 52 Week High
- 52 Week Low

The current price may be filtered based on its distance from the 52 Week High.

This filter is optional and configurable.

---

# 12. Fundamental Rules

## Business Rules

Limited fundamental information is retrieved from Yahoo Finance.

Supported fields include:

- PE Ratio
- EPS
- Market Capitalization (where available)

Fundamental filters are optional.

Availability of these values depends on Yahoo Finance.

---

# 13. Ranking Rules

## Business Rules

Each stock passing all validations receives a ranking score.

Ranking considers:

- Freshness of Golden Cross
- Distance from Long Moving Average
- Long Moving Average Trend
- Trough Quality

Higher scores indicate stronger technical setups.

---

# 14. Failure Reason Rules

## Business Rules

Every rejected stock records one or more failure reasons.

Typical failure reasons include:

- Insufficient Historical Data
- Golden Cross Not Found
- Golden Cross Older Than Configured Limit
- Pre-Golden Cross Validation Failed
- Long Moving Average Trend Validation Failed
- Price Below Long Moving Average
- Price Too Far From Long Moving Average
- Trough Validation Failed
- 52 Week High Filter Failed
- Data Download Failed
- Invalid Stock Symbol

Failure reasons are displayed within the Streamlit application to assist users in understanding why a stock was rejected.

---

# 15. Reporting Rules

## Business Rules

The scanner supports exporting results to Microsoft Excel.

The report includes:

- Stock Symbol
- Current Price
- Moving Averages
- Golden Cross Date
- Ranking Score
- PE Ratio
- EPS
- Failure Reason (Rejected Stocks)

---

# 16. Dashboard Rules

## Business Rules

The Streamlit application consists of three primary pages.

### Scanner

- Upload Stock List
- Configure Scanner Parameters
- Execute Stock Scan

### Results

- Display Qualified Stocks
- Display Technical Metrics
- Export Results

### Stock Detail

- Candlestick Chart
- Short Moving Average
- Long Moving Average
- Golden Cross Marker

---

# 17. Known Limitations

This project was intentionally designed as a Proof of Concept.

Current limitations include:

- Dependency on Yahoo Finance availability.
- No persistent historical database.
- Historical data downloaded for every execution.
- Performance decreases for very large stock universes.
- Fundamental data availability depends on Yahoo Finance.
- Historical data quality cannot be independently verified.

These limitations motivated the development of **Project 2 – NSE Bhavcopy Platform**, which introduces a local market data warehouse, persistent storage, scheduled updates, and a production-grade architecture.
