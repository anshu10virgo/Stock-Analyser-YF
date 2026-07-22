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

### Dashboard

- Four-step desktop workflow covering Setup, Strategy, Live Scan, and Results
- Strategy controls grouped into common Golden Cross, Post Golden Cross, and
  opt-in Impending Golden Cross sections
- Session-only named strategies that do not alter committed defaults
- Progressive qualified-stock display and locally derived scan insights
- Branded colour system and bull/bear market artwork
- Configurable scanner controls and scan-size selection
- Formatted qualified-stock table with latest scan timestamp
- Interactive one-year selected-stock chart
- Golden Cross date marker on charts
- Score details that expand without reloading chart history
- Effective source, fallback, timing, and fundamentals coverage diagnostics

## Current Hardening Work

- Full per-symbol failure reporting and failure visibility in the dashboard.
- Enforce every enabled scanner rule consistently.
- Add automated tests for scanner rules, provider failures, and UI formatting.

## Current Sprint

- Impending Golden Cross strategy and separate result presentation.
- Removal of the legacy stock-universe fallback.
- Reduced workflow-navigation footprint and updated rule documentation.
- Scope and acceptance criteria are maintained in the active sprint section of
  `docs/roadmap.md`.

## Current Risks

- Yahoo Finance availability and field coverage vary by symbol.
- Yahoo classifications may not cover every active NSE symbol; coverage is
  reported explicitly and prior valid mappings are preserved on partial runs.
- Binary Parquet changes must be monitored for repository growth over time.
