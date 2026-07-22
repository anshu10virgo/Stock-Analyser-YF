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
- Snapshot date, PE/industry coverage, effective source, and fallback metrics
- Colour-accented desktop visual system and reduced interface typography

## Charts

- Candlestick
- MA50
- MA200
- Golden Cross Marker
- Cached single-symbol history reads without loading the complete snapshot

## Export

- Excel

## Market Data Operations

- Ten-year repository-backed OHLCV history
- Local adjusted/unadjusted price calculation
- Weekday incremental refresh with manual validation mode
- New-universe-symbol backfill and inactive-symbol preservation
- Semiannual sector/industry refresh with active-universe change detection
- Committed weighted and median industry P/E benchmarks
