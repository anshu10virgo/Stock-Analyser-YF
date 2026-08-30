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

## Optional Fundamental Filters

- Empty-by-default dropdown builder with ordered add and remove actions
- Relative Industry P/E using the current median peer benchmark
- Current P/E below the stock's own available 3Y/5Y/10Y average P/E
- Configurable PEG, profit growth, EPS growth, sales growth, ROE, and
  debt-to-equity thresholds
- Large-, mid-, small-, micro-cap, and custom market-cap ranges
- Financial-company debt-to-equity bypass
- Lenient missing-data handling with one filter-level `not evaluated` label
- Confirmed optional-filter rejections without changing technical scoring

## Dashboard

- Guided desktop workflow: Setup, Strategy, Live Scan, Results, and Backtester
- Display identity simplified to `Stock Analyser` while the repository name remains unchanged
- Market, universe, data-source, and Top N choices grouped in Setup
- Up to five named scan strategies stored only in the active Streamlit session
- Optional-filter selections and thresholds included in session-only strategies
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
- Clickable result rows with full retained-history stock charts
- Company overview with market cap in crore, debt-to-equity, ROE, and PEG
- Separate 3Y profit, EPS, and revenue CAGR cards
- Retried and cached Yahoo fundamental-data retrieval
- Selected-stock weighted and median industry P/E benchmarks with peer count
- Selected-stock historical P/E and TTM EPS chart sourced only from the
  committed Screener snapshot
- Filter-level optional-data availability in qualified results and stock details
- Snapshot date, PE/industry coverage, effective source, and fallback metrics
- Colour-accented desktop visual system and reduced interface typography
- Single-row compact workflow navigation on mobile screens
- Multi-recipient scan-report email with a filters-first workbook and
  maximum-period price-chart archives
- Selected-stock Backtester with multiple historical Golden Cross signals,
  next-session entry values, point-in-time P/E, and 1W through 1Y completed
  return horizons

## Ticksy

- Ticksy local-data assistant launcher with a themed icon, session-only chat,
  deterministic stock-status explanations, current-market summaries, stock
  comparisons, historical Backtester reviews, calculation traces, and
  confirmation before scan, Backtester, strategy, or navigation actions
- Ticksy support for local positive-convergence crossover windows, parameter
  help, scan health, data provenance, data dictionary, workflow guidance,
  selected-universe lookup, plain-English local reports, and session notes
- Gemini Flash initial provider with a disabled state when no configured key is
  available and an OpenAI-ready provider setting

## Charts

- Candlestick
- MA50
- MA200
- Golden Cross Marker
- Historical P/E line, selected-period median P/E, and reported TTM EPS bars
- 1M, 6M, 1Y, 3Y, 5Y, and 10Y valuation periods
- 6M, 1Y, 3Y, 5Y, 10Y, and Max price periods with drag zoom, pan, reset,
  hover details, and a full-history range slider
- Cached single-symbol history reads without loading the complete snapshot

## Export

- Excel workbook with Filters, Post Golden Cross, and Impending Golden Cross
  worksheets
- Maximum-period price/MA PNG charts split into size-bounded ZIP attachments
- Session-only multiple-recipient email delivery

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
