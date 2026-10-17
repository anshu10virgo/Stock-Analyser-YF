# Cloud storage design — structure approved October 17, 2026

The owner approved migration on October 17, 2026 and subsequently requested
readable dataset folders directly under markets/. Keep Git-backed data until
cloud results and production cutover are verified.

## Current readable-layout status ? October 17, 2026

- Active prefix: `markets/IN/`; both local storage configurations use `prefix = ""`.
- Active schema 2 snapshot: `46d55904266d42c108dfca366d12b78889fd8e6d692d183da3c86c1ea460a3c1`.
- Contains 4,222 logical data files; source data still covers October 16, 2026.
- Copied 4,220 unchanged files internally in R2 and uploaded two revised
  dataset manifests plus the new catalog. Every file passed read-back SHA-256
  verification using the read-only application credentials.
- Local/cloud universe, sample stock data, scanner outputs, Backtest signals,
  and app Setup checks matched. All 125 unit tests passed.
- Restarted the local app with the new prefix; health check passed.
- Removed exactly 4,224 legacy keys under `ticksy/markets/IN/` after verification.
  Final bucket listing contains only `markets/` at the root, with the readable
  dataset folders shown below. Git data and local cached originals remain.
- The original snapshot ID below records the first migration; use the new
  schema 2 ID above when pinning the reorganized cloud data.
- Hosted deployment and scheduled R2 publication remain pending as before.

## Original India migration status — October 17, 2026

- Published snapshot `08e9103fc528c3b157b5bd6ed29c37a72ffbe956ce40fe41434d44320af48730`.
- Source data covers October 16, 2026; stock universe contains 2,287 symbols.
- Uploaded 4,222 data objects plus one catalog, totaling 296,190,917 bytes;
  the active pointer is stored separately.
- Read back and SHA-256-verified all 4,222 data objects using application
  credentials. The verification cache is available to the local app.
- Compared the complete universe and sampled RELIANCE.NS, BHARTIARTL.NS, and
  HDFCBANK.NS price history, fundamentals, valuation history, scanner outputs,
  and Backtest signals against local data; outputs matched.
- App Setup checks passed, including an explicitly pinned version.
- Local Secrets now select `provider = "r2"`; new app sessions default to
  Cloud snapshot. Existing sessions preserve their selected data source.
- Hosted Streamlit code deployment and read-only Secrets configuration remain
  pending. Scheduled R2 workflow changes are prepared; activation requires
  publishing them to the default branch and testing the hosted jobs.
- No Git-backed data has been deleted. US namespaces are reserved only.

## Physical bucket layout

Bucket: `stock-analyser-data` (private, R2 Standard). The user requested this
readable layout on October 17, 2026 to replace `ticksy/markets/.../objects/`.
`<version>` below means a complete SHA-256 hash in the actual filename.

```text
stock-analyser-data/
  markets/
    IN/
      current.json
      snapshots/<catalog-version>.json
      stock_universe/
        manifest--<version>.json
        validated/yahoo_nse_<date>--<version>.csv
        snapshots/nse_equity_<date>--<version>.csv
        refresh_reports/<date>--<version>.json
      market_data/
        manifest--<version>.json
        prices/<year>--<version>.parquet
        symbol_prices/RELIANCE.NS--<version>.parquet
        fundamentals/
          fundamentals--<version>.csv
          classifications--<version>.csv
          classification_metadata--<version>.json
          industry_valuations--<version>.csv
        symbol_coverage--<version>.csv
        screener/
          manifest--<version>.json
          snapshots/<summary-name>--<version>.csv
          snapshots/<history-name>--<version>.parquet
          snapshots/<coverage-name>--<version>.csv
          symbol_history/RELIANCE.NS--<version>.parquet
    US/                         # Reserved; appears when US data is published.
      current.json
      snapshots/<catalog-version>.json
      stock_universe/...
      market_data/...           # SEC history uses sec/ instead of screener/.
```

These are actual R2 object-key folders, visible in the console. There is no
`ticksy/`, extra `data/`, or hash-only `objects/` directory in the new layout.
Per-stock filenames use the provider ticker, safely encoded when necessary.

Every data filename includes its content hash so older snapshots remain
reproducible. A changed file gets a new versioned filename; unchanged files keep
the same key and are reused. Never manually rename a versioned file without
updating and validating its catalog.

`current.json` selects one complete catalog from `snapshots/`. The IN and US
namespaces have independent pointers, catalogs, files, and caches. Catalogs and
manifests identify their market and currency, and readers reject another
market's snapshot. Use country-qualified stock identities such as
`IN:RELIANCE.NS` and `US:AAPL`.

## Logical dataset layout inside each catalog

Logical paths are lookup names in the JSON catalog. They use the same dataset
folders as R2, with the version hash omitted from the filename:

```text
stock_universe/
  manifest.json
  validated/<active-universe>.csv
  snapshots/<source-universe>.csv
  refresh_reports/<report>.json
market_data/
  manifest.json
  prices/<year>.parquet
  symbol_prices/RELIANCE.NS.parquet
  fundamentals/
    fundamentals.csv
    classifications.csv
    classification_metadata.json
    industry_valuations.csv
  symbol_coverage.csv
  screener/
    manifest.json
    snapshots/<summary>.csv
    snapshots/<history>.parquet
    snapshots/<coverage>.csv
    symbol_history/RELIANCE.NS.parquet
```

For example, catalog path `market_data/prices/2026.parquet` resolves to actual
R2 key `markets/IN/market_data/prices/2026--<sha256>.parquet`. The catalog stores
that exact key, SHA-256 hash, and size. The reader adds the market prefix. It
still accepts the app's existing local `data/...` paths at its storage boundary,
so local repository files and financial calculations remain unchanged.

Schema 2 catalogs implement this layout. Schema 1 readers remain supported for
cutover from the earlier hash-only layout; new publications use schema 2.

Only manifest-referenced source files enter a snapshot. Per-symbol price and
valuation files are additional derived copies for small chart/Backtest reads;
their values match the original annual/history files. Encoded ticker names avoid
special-character/path problems while the manifest retains actual tickers.
This duplicates some storage deliberately to reduce downloads and chart
latency. The preparation command reports the resulting package size.

The locally prepared India snapshot through October 16, 2026 contains 4,222
logical files totaling 294,975,726 bytes (about 295 MB). Thirty independent full
copies would be about 8.85 GB before additional snapshots or US data. Actual
retained storage reuses unchanged objects, but the free-tier budget must be
measured as history grows; the original 104 MB source-only estimate does not
include these per-symbol copies.

Existing India files remain under the repository's `data/` directory. Future
US refreshes use `markets/US/data/` and must supply explicit `market = "US"`
manifests, with `sec/` for financial history instead of India's `screener/`.
The current UI remains NSE-only. This is storage preparation for US
support, not delivery of the S&P 500 universe, SEC parser, or US financial rules.

## Publication and reading

1. Refresh and validate local source data using the existing maintenance scripts.
2. Prepare the package locally and validate source file hashes. Windows line
   endings are normalized only if that reproduces the exact manifest hash.
3. Upload new immutable objects, validating size/hash metadata before activation.
4. Upload the complete immutable catalog and read back every referenced object
   to verify size and SHA-256 before activation.
5. Replace `current.json` with an ETag conditional write. A competing publisher
   causes failure rather than overwriting its active pointer.
6. Pin the app session to that catalog. Download required objects into a
   hash-checked local cache and reuse them for scans, charts, and reports.

Cloud snapshot mode has no Yahoo fallback. Explicit Live Yahoo mode remains
available. Backtester uses the Setup-selected source. Python retains all
financial calculations; Ticksy gets no cloud client or retrieval tool.

Cached explicit snapshot IDs support offline verification. An unpinned new
session needs cloud access to resolve `current.json`; it does not silently
select stale cached data. Restart the app session to pick up a newly published
snapshot. Rollback can pin a retained snapshot ID or restore a verified pointer.

## Credentials and rollout

- Use one bucket-scoped **Object Read only** token for application reads.
- Use a separate bucket-scoped **Object Read & Write** token for maintenance.
- Store app keys in Streamlit Secrets. The user approved `R2_PUBLISHER_CONFIG`
  in GitHub Actions Secrets for scheduled publishers. Never paste keys into
  chat or CLI arguments. The local publisher reads `.streamlit/secrets.toml`.
- Copy the `[storage]` template from `.streamlit/secrets.toml.example` into local
  and deployed Streamlit Secrets; keep `provider = "local"` during preparation.
- Set `prefix = ""` in both storage sections to use `markets/` at bucket root.
- Put `[storage_publisher]` only in local Secrets, never deployed application
  Secrets. The endpoint excludes the trailing bucket name.

The maintenance commands below install the application's Python packages,
prepare a local upload package, upload it, and read it back for verification.
Run them with the same Python environment used by Stock Analyser.

```powershell
python -m pip install -r requirements.txt
python scripts/cloud_snapshots.py prepare --market IN
python scripts/cloud_snapshots.py publish --market IN --snapshot-id <prepared-id>
python scripts/cloud_snapshots.py verify --market IN --snapshot-id <prepared-id>
python scripts/verify_cloud_results.py
```

Replace `<prepared-id>` with the `snapshot_id` printed by `prepare`. The compare
script checks the complete universe and samples three stocks' prices,
fundamentals, valuation history, scanner outputs, and Backtest signals. Upload
and full-file verification use at most sixteen parallel requests and report
progress every 250 objects. Unchanged objects are reused on later uploads.

Only after comparing the uploaded snapshot with the local results, change
`[storage].provider` to `"r2"`, restart the app, and select Cloud snapshot.
Use `[storage.snapshot_ids]` with an `IN` or `US` entry for a fixed version.

```powershell
python scripts/cloud_snapshots.py restore --market IN --snapshot-id <retained-id>
```

Keep the Git-backed data until cutover is validated. The converted daily and
monthly workflows publish to R2 once their changes reach the default branch.
The user-approved `R2_PUBLISHER_CONFIG` GitHub Actions Secret is configured.
Hosted validation and refresh runs remain rollout checks. See [deployment.md](deployment.md).

## Retention and future features

The implemented policy keeps the latest 30 catalogs, 12 monthly checkpoints,
the active catalog, and protected snapshot IDs, with a seven-day upload grace
period. Weekly housekeeping previews and per-refresh usage reports are enabled;
deletion requires an exact reviewed plan ID. Shared referenced files are
preserved. See [storage housekeeping](storage_housekeeping.md) for offline cache
cleanup and Git-data retirement gates. Do not use age-only dataset expiration.

Reserve separate namespaces for scan history, reports, and approved notes when
those features are implemented. Persist market, strategy, schema, and snapshot
identity with every saved result. A multi-user account/strategy/notes database
remains separate work; no password or login data belongs in market snapshots.

## Approval checklist

- One private bucket, separate `IN` and `US` namespaces.
- Readable, immutable dataset files plus versioned catalogs and an active pointer per market.
- Annual files for bulk scans and per-symbol files for chart reads.
- Credentials separated between application reads and maintenance writes.
- Thirty latest catalogs, twelve monthly checkpoints, active/pinned preservation;
  scheduled dry runs and explicit reviewed cleanup.
- First migration includes India only; Git data stays until cutover checks pass.

## Inspecting and relocating storage

For a normal daily refresh directly from the active R2 snapshot:

```powershell
python -u scripts/refresh_cloud_market_data.py
```

This stages the original India source files in an ignored temporary run
directory, checks Yahoo for incremental price rows, and validates the result.
Screener history and the stock universe are retained. The existing refresh
rules update Yahoo fundamentals when new prices trigger a snapshot update.
If no new rows are available, the active snapshot is retained without a new
publication. Changed data is prepared, published with a parent-version guard,
and read back using the application credentials. Local Git data is untouched.
Each completed run saves `refresh_report.json` in its staging directory.
App sessions remain pinned; restart a session to use a newly published version.
This command is also used by the converted daily workflow with
`--config-source github`. The monthly workflow adds `--dataset screener`.

The existing Yahoo maintenance script also accepts `--data-root` for isolated
refreshes and defaults to the repository root for existing Git workflows.

For the semiannual stock-universe refresh against R2:

```powershell
python -u scripts/refresh_cloud_market_data.py --refresh-universe
```

If Yahoo's bulk market-cap screener returns no matching stocks, the universe
refresh requests fresh market caps directly for the validated tickers using
bounded concurrency. Unavailable caps remain unranked; previous caps are not
reused. A run with no usable caps stops before activation.
Yahoo rate-limit responses abort the direct fallback before later batches are
requested, so throttling cannot silently publish a partially ranked universe.
When individual Yahoo quotes are missing during supporting-data synchronization,
existing fundamentals are retained with `quote_status=retained_previous_snapshot`.
New symbols without quotes use `quote_status=unavailable` and empty valuation
fields. Retained values keep their previous observation age.

After a cloud refresh changes the universe, compare R2 against that run's staging
root rather than the older Git data:

```powershell
python scripts/verify_cloud_results.py --data-root .snapshot-cache/universe-refresh/IN/<run-id> --app
```

This downloads the NSE EQ list, validates one year of Yahoo history, and rebuilds
market-cap ranks in staging. It then runs the incremental market-data refresh
to backfill newly added symbols and align fundamentals, classification coverage,
and universe hashes before publishing one coherent snapshot. Screener history
retains its original provenance and is not refreshed by this command. The run
report records added/removed symbols, counts, and the universe refresh date.
If validation or synchronization fails, no replacement snapshot is published.
Concurrent publications are rejected using the starting snapshot version.

```powershell
python scripts/cloud_snapshots.py inventory --market IN
```

The inventory reads actual R2 folder prefixes. Catalog aliases are not
presented as if they were physical folders. For a planned relocation, publish
with `--root-layout --copy-from-prefix <old-market-prefix>`, verify the result,
run `python scripts/verify_cloud_results.py --root-layout --app`, update both
Secrets prefixes, and restart the app. The initial `ticksy/markets/IN` copy has
already been retired; it must not be used as a source for future publications.

The one-time `retire-legacy` maintenance mode is limited to the initial
`ticksy/markets/<market>` namespace. It verifies the destination, checks the
expected old snapshot and exact file list, and refuses unexpected files.
It never recursively deletes the bucket or unrelated prefixes.

## First normal daily refresh ? October 17, 2026

Ran the manual cloud refresh from snapshot
`46d55904266d42c108dfca366d12b78889fd8e6d692d183da3c86c1ea460a3c1`.
Staged 25 source files, checked all 2,287 selected-universe symbols for newer
Yahoo rows, and validated 3,939,371 stored price rows through October 16, 2026.
No new trading rows were returned, so the active R2 snapshot was retained and
no replacement publication was created. Screener and stock-universe data were
retained, and tracked Git data was not changed. The refresh workflow tests,
including no-change and parent-version protection, passed (129 tests total).
