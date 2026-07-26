# Project Progress

Status: Active Development

## Implemented Features

### Data

- Yahoo Finance batch price retrieval
- Configurable adjusted or unadjusted price basis
- Retried and cached fundamental-data retrieval
- Manifest-controlled validated NSE universe and optional file upload
- Selectable Git-snapshot and live Yahoo provider sets
- Ten-year partitioned market-data snapshot and manifest contract
- Scheduled/manual incremental refresh workflow
- Symbol-filtered Parquet chart access and selected-history caching
- Semiannual sector/industry classification snapshot
- Committed weighted/median industry PE and coverage metadata
- GitHub Actions refresh-failure email notification with secret-managed Gmail
  authentication
- Unified, resumable Screener fundamentals refresh with batch throttling
- Git-backed Screener summary and historical valuation snapshot contracts
- Three-state optional fundamental-filter evaluation backed by committed data

### Technical Analysis

- Moving averages, Golden Cross validation (including Death Cross
  invalidation), Golden Cross price validation, and short-MA price validation
- Golden Cross age and pre-cross validation
- Optional long-MA decline-to-rise filters and targeted pre-cross trough,
  mandatory price-distance checks, and ranking
- Typed scan configuration, typed scan outcomes, and a dedicated scan service
  with structured market-data and processing failures
- Yahoo historical-price provider with bounded retry, 15-minute batch caching,
  and provider metrics
- Separate Post Golden Cross and opt-in Impending Golden Cross qualification
  paths with shared reversal calculations and distinct results
- Nine opt-in fundamental filters that run after mandatory technical checks
  without changing technical scores

### Dashboard

- Four-step desktop workflow covering Setup, Strategy, Live Scan, and Results
- Strategy controls grouped into common Golden Cross, Post Golden Cross, and
  opt-in Impending Golden Cross sections
- Session-only named strategies that do not alter committed defaults
- Empty-by-default optional-filter builder with add/remove sequencing
- Progressive qualified-stock display and locally derived scan insights
- Plain-language most-common rejection insights based on the exact failed rule
- Branded colour system and bull/bear market artwork
- Configurable scanner controls and scan-size selection
- Formatted qualified-stock table with latest scan timestamp
- Interactive one-year selected-stock chart
- Golden Cross date marker on charts
- Score details that expand without reloading chart history
- Effective source, fallback, timing, and fundamentals coverage diagnostics
- Selected-stock historical P/E and TTM EPS chart with six time periods
- Filter-level missing-data labels without an additional result split

## Current Hardening Work

- Full per-symbol failure reporting and failure visibility in the dashboard.
- Enforce every enabled scanner rule consistently.
- Add automated tests for scanner rules, provider failures, and UI formatting.

## Current Sprint

- Nine optional valuation, growth, quality, leverage, and market-cap filters.
- Ordered dropdown builder with no filters selected by default.
- Current P/E compared with median Industry P/E and the stock's own available
  historical average P/E.
- Lenient missing-data handling with filter-level availability labels.
- One-load committed Screener summary access and no live scan scraping.
- Removal of the legacy ten-post-cross-session optional check.

## Current Risks

- Yahoo Finance availability and field coverage vary by symbol.
- Yahoo classifications may not cover every active NSE symbol; coverage is
  reported explicitly and prior valid mappings are preserved on partial runs.
- Binary Parquet changes must be monitored for repository growth over time.
- Screener's public page/chart contracts are external and may change; schema
  validation and audited failures protect the active snapshot.
