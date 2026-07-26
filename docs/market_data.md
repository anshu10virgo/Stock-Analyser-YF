# Committed Market Data

## Purpose

Normal scans and automated tests should be reproducible without repeatedly
calling Yahoo Finance. The application supports two explicit data sources:

- **Live Yahoo Finance**: temporary rollout and comparison mode.
- **Git snapshot**: committed prices and fundamentals, with Yahoo fallback only
  when a required snapshot file or requested symbol is absent.

Snapshot age does not trigger a live request. Its date is shown in the app and
updated by scheduled maintenance.

## Storage Contract

```text
data/market_data/
  manifest.json
  symbol_coverage.csv
  prices/
    YYYY.parquet
  fundamentals/
    fundamentals.csv
    classifications.csv
    classification_metadata.json
    industry_valuations.csv
  screener/
    manifest.json
    snapshots/
      fundamental_metrics_TIMESTAMP.csv
      historical_valuation_TIMESTAMP.parquet
      coverage_TIMESTAMP.csv
```

Retention is ten calendar years. Every year uses compressed Parquet sorted by
symbol and date with bounded row groups. Bulk scans can read the complete
snapshot, while charts use Parquet predicate filtering and load only the
selected symbol. Raw and adjusted close are stored so either price basis can be
applied locally.

Selected-stock history is cached for 15 minutes and keyed by symbol, price
basis, selected source, and snapshot version. Expanding score details does not
rerun the chart data path.

The manifest records schema version, universe hash, file hashes, history range,
latest trading date, coverage, and maximum supported Long MA. It is replaced
only after the data files pass validation.

The Screener directory has its own manifest and lifecycle. Its summary file
stores 3Y/5Y/10Y P/E averages and medians, sales/profit/EPS growth,
debt-to-equity, ROE, and latest OPM. Selected optional filters use the
applicable summary fields. Its
Parquet file stores historical P/E and TTM EPS observations used exclusively
by the selected-stock valuation chart.

## Commands

```powershell
python scripts/refresh_market_data.py --mode full
python scripts/refresh_market_data.py --mode incremental
python scripts/refresh_market_data.py --mode classifications
python scripts/refresh_market_data.py --mode optimize
python scripts/refresh_market_data.py --mode validate
python scripts/refresh_screener_fundamentals.py --mode refresh
python scripts/refresh_screener_fundamentals.py --mode validate
```

The GitHub Actions workflow runs incremental mode at 18:00 IST on weekdays and
can be manually started in incremental, classification, or validation-only
mode. A closed-market run produces no data commit.

The separate Screener workflow runs monthly and can also be started manually.
It uses one unified refresh for all Screener fields. The default batch contains
10 stocks, followed by a five-second pause. Completed batches are checkpointed
under an ignored staging directory, so an interrupted run resumes without
requesting completed symbols again. Versioned output files are activated only
after schema and coverage validation and an atomic manifest replacement.
Both data workflows share one concurrency group, so Yahoo and Screener
refreshes cannot commit simultaneously. The Yahoo workflow stages only its
parent manifest, prices, fundamentals, and symbol-coverage file; the Screener
workflow stages only `data/market_data/screener/`.

## Refresh Failure Email

The workflow attempts to email `anshu10virgo@gmail.com` whenever any refresh,
validation, or commit step fails. The notification includes the repository,
commit, branch, and direct GitHub Actions run link. Notification errors do not
replace or hide the original workflow failure.

Configure this repository-level GitHub Actions secret under **Settings >
Secrets and variables > Actions**:

- `REFRESH_SMTP_APP_PASSWORD`: dedicated Google App Password for the workflow.

The sender and recipient are both `anshu10virgo@gmail.com`; only the App
Password is secret. Do not store it in the repository. Google requires 2-Step
Verification before an App Password can be created. See the official
[Google App Password guide](https://support.google.com/accounts/answer/185833)
and [GitHub Actions secrets reference](https://docs.github.com/en/actions/reference/security/secrets).

If the secrets are absent, the workflow records a warning that email could not
be sent. The failed Actions run remains visible on GitHub.

To verify delivery without downloading or changing market data, manually run
the workflow with mode `notification-test`. An optional failed-run URL can be
included in the test message. The test run fails if the SMTP secret is missing
or Gmail rejects delivery.

## Fundamentals and Industry P/E

Yahoo's India quote screener supplies company name, market cap, trailing PE,
forward PE, and trailing EPS. When trailing PE is missing but price and positive
trailing EPS exist, PE is calculated as current price divided by trailing EPS
and its source is recorded.

Sector and industry mappings are stored independently in
`classifications.csv`. They refresh every 180 days or can be forced with
`--mode classifications`, and daily fundamentals refreshes never overwrite
valid mappings with blanks. A stock-universe change is detected through the
active-symbol hash and triggers a new classification pass.

For every classified industry with positive-PE, positive-market-cap peers, the
refresh calculates:

- market-cap weighted PE as total market cap divided by implied earnings;
- median peer PE;
- eligible peer count.

Coverage counts are recorded in the manifest and displayed in Streamlit.

## Historical Valuation and Long-Term Fundamentals

Screener historical chart observations provide the P/E line and reported TTM
EPS bars for 1M through 10Y selected-stock views. The chart calculates its
median reference from the selected period. No live Screener request occurs
when a user expands stock details.

The unified refresh also stores:

- average and median P/E for 3Y, 5Y, and 10Y;
- compounded sales and profit growth for 3Y, 5Y, and 10Y;
- calculated annual EPS CAGR for 3Y, 5Y, and 10Y;
- debt-to-equity calculated from Screener borrowings and shareholder equity;
- current ROE from Screener's top-ratio cards;
- latest annual/TTM OPM from the Profit & Loss table.

The daily Yahoo fundamentals file stores PEG as refreshed Yahoo P/E divided by
the active Screener snapshot's positive 3-year compounded profit growth. The
P/E uses Yahoo `trailingPE`, with the existing market-price/trailing-EPS
fallback. PEG remains blank until both sources are available.

Selected optional filters use the summary's P/E averages, growth,
debt-to-equity, and ROE. P/E medians and OPM remain backend context. The
scanner loads the summary once when required and never makes a live Screener
request.

Missing individual 3Y, 5Y, or 10Y periods are ignored. If no usable value
exists for a selected filter, the stock remains qualified under its technical
result group with one filter-level `not evaluated` label.

## Universe Reconciliation

New symbols receive all available history up to the ten-year limit. Removed
symbols stop receiving updates and are excluded from scans; historical rows are
retained for reproducibility. Unchanged symbols receive only missing sessions.

## Closed-Market Testing

- Validation mode exercises the committed snapshot without Yahoo.
- Tests replay deterministic rows into a temporary directory and verify
  manifest creation, deduplication, and local-only reads.
- Manual incremental mode on a holiday verifies the no-op path and must not
  commit when Yahoo returns no new session.
