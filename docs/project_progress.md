# Project Progress

Status: Active Development

## Implemented Features

### Data

- Yahoo Finance batch price retrieval
- Configurable adjusted or unadjusted price basis
- Retried and cached fundamental-data retrieval
- Included `stock_symbols.csv` universe and optional file upload

### Technical Analysis

- Moving averages, Golden Cross validation, and Golden Cross price validation
- Golden Cross age and pre-cross validation
- Trough detection, slope calculation, price-distance checks, and ranking

### Dashboard

- Configurable scanner controls and scan-size selection
- Formatted qualified-stock table with latest scan timestamp
- Interactive one-year selected-stock chart
- Golden Cross date marker on charts

## Current Hardening Work

- Full per-symbol failure reporting and failure visibility in the dashboard.
- Enforce every enabled scanner rule consistently.
- Cache historical and chart data with an appropriate expiry policy.
- Add automated tests for scanner rules, provider failures, and UI formatting.

## Current Risks

- Yahoo Finance availability and field coverage vary by symbol.
- No persistent historical market-data store exists yet.
- Large universes require additional caching, throttling, and observability.
