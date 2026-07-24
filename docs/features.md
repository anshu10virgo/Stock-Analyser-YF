# Features

## Technical Filters

- Rising Short MA
- Separate Post and Impending Golden Cross qualification paths
- Shared rising Short-MA and 52-week Long-MA reversal checks
- Post-Cross Short MA above Long MA and recent crossover validation
- Impending-Cross MA proximity, acceleration, and pre-cross validation
- Configurable Golden Cross age
- 52-week Long-MA high-to-trough-to-positive-slope validation
- Configurable minimum Long-MA decline and high-to-trough duration
- Configurable current-price premium above Long MA
- Optional minimum of 10 post-Golden-Cross sessions

## Dashboard

- Guided desktop workflow: Setup, Strategy, Live Scan, and Results
- Display identity simplified to `Stock Analyser` while the repository name remains unchanged
- Market, universe, data-source, and Top N choices grouped in Setup
- Up to five named scan strategies stored only in the active Streamlit session
- Immutable code-defined scan defaults with an explicit reset action
- Batched live progress with Post-Cross, Impending-Cross, and rejected counts
- Locally derived scan insights without Google or other research requests
- Results and selected-stock details
- Stock Details
- Manifest-controlled, validated NSE stock universe
- Configurable number of symbols to analyse
- Main-screen choice between live Yahoo and the committed Git snapshot
- Adjustable or actual-price market data selection
- Formatted scan results with a scan timestamp
- Clickable result rows with one-year stock charts
- Retried and cached Yahoo fundamental-data retrieval
- Selected-stock weighted and median industry P/E benchmarks with peer count
- Selected-stock historical P/E and TTM EPS chart sourced only from the
  committed Screener snapshot
- Snapshot date, PE/industry coverage, effective source, and fallback metrics
- Colour-accented desktop visual system and reduced interface typography
- Single-row compact workflow navigation on mobile screens

## Charts

- Candlestick
- MA50
- MA200
- Golden Cross Marker
- Historical P/E line, selected-period median P/E, and reported TTM EPS bars
- 1M, 6M, 1Y, 3Y, 5Y, and 10Y valuation periods
- Cached single-symbol history reads without loading the complete snapshot

## Export

- Excel

## Market Data Operations

- Ten-year repository-backed OHLCV history
- Local adjusted/unadjusted price calculation
- Weekday incremental refresh with manual validation mode
- Email notification to the configured recipient when a refresh workflow fails
- New-universe-symbol backfill and inactive-symbol preservation
- Semiannual sector/industry refresh with active-universe change detection
- Committed weighted and median industry P/E benchmarks
- Monthly/manual unified Screener fundamentals refresh with resumable batches
- Backend-only 3Y/5Y/10Y P/E average/median, sales growth, profit growth, EPS
  growth, debt-to-equity, ROE, and latest OPM from Screener
- Backend-only PEG refreshed from daily Yahoo P/E and stored Screener 3-year
  profit growth
