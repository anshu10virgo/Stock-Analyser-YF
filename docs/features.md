# Features

## Technical Filters

- Rising Short MA
- Short MA strictly above Long MA
- Configurable Golden Cross age
- 52-week Long-MA high-to-trough-to-positive-slope validation
- Configurable minimum Long-MA decline and high-to-trough duration
- Configurable current-price premium above Long MA
- Optional minimum of 10 post-Golden-Cross sessions

## Dashboard

- Scanner
- Results
- Stock Details
- Included `stock_symbols.csv` universe
- Configurable number of symbols to analyse
- Main-screen choice between live Yahoo and the committed Git snapshot
- Adjustable or actual-price market data selection
- Formatted scan results with a scan timestamp
- Clickable result rows with one-year stock charts
- Retried and cached Yahoo fundamental-data retrieval
- Selected-stock weighted and median industry P/E benchmarks with peer count
- Snapshot date, PE/industry coverage, effective source, and fallback metrics

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
