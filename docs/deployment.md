# Deployment and storage guide

Use this guide for hosted setup, R2 structure, refreshes, rollback, and storage
maintenance. Run commands from the repository root using the app's Python environment.

- [Deployment and credentials](#deployment-and-credentials)
- [Refresh jobs and verification](#refresh-jobs-and-verification)
- [Physical bucket layout](#physical-bucket-layout)
- [Logical dataset layout inside each catalog](#logical-dataset-layout-inside-each-catalog)
- [Publication and reading](#publication-and-reading)
- [Rollback and local development](#rollback-and-local-development)
- [Storage maintenance](#storage-maintenance)

## Deployment and credentials

Streamlit Community Cloud runs `app.py` from `main` at
https://stock-analyser-yf.streamlit.app/. The app reads the private
`stock-analyser-data` R2 Standard bucket. GitHub Actions refreshes and publishes
data independently. `markets/IN` is active; `markets/US` is reserved for a future
US pipeline. The UI remains NSE-only. Python services calculate financial
results; Ticksy interprets local application results and performs no maintenance.

1. Install dependencies with `python -m pip install -r requirements.txt`.
2. Configure the hosted app's Streamlit Secrets using
   [the template](../.streamlit/secrets.toml.example). Set `[storage]` to
   `provider = "r2"`, the account endpoint without a bucket suffix, bucket name,
   `prefix = ""`, and bucket-scoped Object Read only credentials. Leave snapshot
   pins unset for normal production. Preserve existing model and email settings.
3. Keep `[storage_publisher]` only in local `.streamlit/secrets.toml` for manual
   maintenance, using a separate bucket-scoped Object Read & Write token.
   Never include publisher credentials in the hosted app or commit real Secrets.
4. For scheduled jobs, configure the user-approved GitHub Actions Secret
   `R2_PUBLISHER_CONFIG` as JSON with `endpoint_url`, `bucket`, `region`, `prefix`,
   `access_key_id`, and `secret_access_key`. This is the approved exception to
   keeping credentials in Streamlit Secrets. Do not print the JSON or write it
   into the checkout. Local commands default to Streamlit Secrets; workflows
   explicitly select `--config-source github` and fail on missing configuration.
5. Save hosted settings, reboot, and check Setup shows Cloud snapshot and expected
   dataset dates. Exercise scans, charts, Backtester, Ticksy, and report export.
   Check a fresh cache loads with read-only access and results match staging.

The account endpoint and bucket configuration belong in Secrets; no credentials
belong in this guide. For deployment checks, run relevant tests and
`git diff --check`. GitHub's Application tests workflow runs offline with generated
fixtures and verifies a clean checkout contains no production `data/` directory.

## Refresh jobs and verification

| Workflow | Schedule (IST) | Destination |
|---|---|---|
| Refresh R2 market data | Weekdays 18:00 | R2, only when data changes |
| Refresh R2 Screener fundamentals | Second day of each month 03:30 | R2 |
| R2 storage housekeeping | Sundays 06:45 | Report only; scheduled runs never delete |

Refresh and housekeeping jobs share `r2-data-refresh` concurrency and read-only
repository permissions. They do not commit generated data to Git. Refresh
reports are retained as Actions artifacts for 14 days, housekeeping reports for
30 days. Refreshes also report storage usage. Failures use the existing email
notification mechanism. Application tests run separately without cloud credentials.

Manually dispatch either refresh workflow with `mode=validate` to stage and
validate its dataset and verify cloud objects without publishing. For local
maintenance using configured Secrets:

```powershell
# Normal daily refresh: retain Screener and universe data.
python -u -m stock_analyser.jobs.market_refresh
# Refresh Screener and supporting fundamentals.
python -u -m stock_analyser.jobs.market_refresh --dataset screener --mode refresh
# Rebuild the stock universe and synchronize supporting market data.
python -u -m stock_analyser.jobs.market_refresh --refresh-universe
# Inspect physical R2 folders or verify the active snapshot.
python scripts/cloud_snapshots.py inventory --market IN
python scripts/cloud_snapshots.py verify --market IN
```

Refreshes start from the active R2 snapshot in isolated ignored staging. New
prices trigger the normal daily fundamentals update; no new trading rows means
no replacement publication. A universe rebuild downloads NSE EQ listings,
validates Yahoo history, rebuilds market-cap ranks, and backfills added symbols
before publishing one coherent snapshot. It retains Screener history. Provider
throttling or failed validation stops activation; missing individual quotes are
labelled as retained or unavailable rather than presented as newly observed data.

Each run saves a `refresh_report.json` in its staging directory. Compare a changed
snapshot against that run's staging root, pinning the reported snapshot version
if another refresh could complete concurrently:

```powershell
python scripts/verify_cloud_results.py --data-root <run-staging-root> --snapshot-id <published-id> --app
```

The comparison checks the complete universe and sampled prices, fundamentals,
valuation history, scanner outputs, and Backtest signals. Acceptance also covers
no-change runs, failed refreshes preserving the pointer, competing publishers
being rejected, and dataset dates distinguishing retained from refreshed values.

Screener refreshes save each complete batch to
`markets/IN/maintenance/screener/<checkpoint-id>/` in R2. The ID binds the ordered
universe and source Screener version. Re-run the same refresh command or dispatch
the workflow again after interruption: a fresh runner verifies and restores the
checkpoint, skips completed batches, and continues pending stocks. Progress logs
show separate processed, successful, and failed counts. An interrupted batch may
be fetched again; a completed durable batch is reused.

To retry recorded failures as well as pending stocks while keeping successful
records, dispatch with `retry_failed=true`, or run locally:

```powershell
python -u -m stock_analyser.jobs.market_refresh --dataset screener --mode refresh --retry-failed
```

Each symbol is attempted at most once per invocation. New attempts replace older
failure outcomes in the final coverage audit; successful checkpoint records are
not requested again.

Checkpoint files are maintenance state, not an active data snapshot. The current
catalog changes only after the complete run and supporting fundamentals pass
validation. Exhausted request retries stop the run without converting all
remaining stocks into failures. A different universe or source Screener version
starts a separate checkpoint. The workflow also saves local staging as an
artifact when available; R2 is the primary recovery source, including on timeout.

## Physical bucket layout

Bucket: `stock-analyser-data` (private, R2 Standard). `<version>` below means a complete SHA-256 hash in the actual filename.

```text
stock-analyser-data/
  markets/
    IN/
      current.json
      snapshots/<catalog-version>.json
      maintenance/lease.json
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

These dataset folders are visible in the R2 console. Per-stock filenames use
the provider ticker, safely encoded when necessary.

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
so local development exports and financial calculations use the same readers.

New publications use schema 2 catalogs; readers also support schema 1.

Only manifest-referenced source files enter a snapshot. Per-symbol price and
valuation files are additional derived copies for small chart/Backtest reads;
their values match the original annual/history files. Encoded ticker names avoid
special-character/path problems while the manifest retains actual tickers.
This duplicates some storage deliberately to reduce downloads and chart
latency. The preparation command reports the resulting package size.

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

## Rollback and local development

To activate a retained snapshot, verify it remotely and conditionally replace
the active pointer using local publisher credentials:

```powershell
python scripts/cloud_snapshots.py restore --market IN --snapshot-id <retained-id>
```

Alternatively, pin `[storage.snapshot_ids]` with an `IN` or `US` snapshot ID in
Streamlit Secrets. Add persistent deployed pins to the housekeeping policy's
`protected_snapshot_ids`. Start a fresh app session after rollback or publication.
Never manually rename versioned objects or expire dataset files by age alone.

For local development, download the complete current snapshot using read-only
Streamlit Secrets before selecting `provider = "local"`:

```powershell
python scripts/cloud_snapshots.py download
```

Downloads verify hashes and refuse to overwrite differing local files unless
`--overwrite` is supplied. Local `data/` and future `markets/US/data/` exports
are ignored by Git.

For deliberate publication of locally maintained India source data:

```powershell
python scripts/cloud_snapshots.py prepare --market IN
python scripts/cloud_snapshots.py publish --market IN --snapshot-id <prepared-id>
python scripts/cloud_snapshots.py verify --market IN --snapshot-id <prepared-id>
python scripts/verify_cloud_results.py --snapshot-id <prepared-id> --app
```

Use the ID printed by `prepare`.

## Storage maintenance

Policy is configured in
[storage_housekeeping.toml](../config/storage_housekeeping.toml). It retains the
latest 30 catalogs, 12 monthly checkpoints, the active snapshot, protected IDs,
and uploads less than seven days old. Add persistent app snapshot pins to
`protected_snapshot_ids`. Referenced shared files and permanent archives are
preserved. Do not apply age-only R2 lifecycle expiration to dataset folders.

Weekly housekeeping and per-refresh usage reports show storage and cache usage.
Review `.snapshot-cache/housekeeping-report.json` or the GitHub Actions artifacts:

```powershell
# Preview only; this does not delete files.
python -m stock_analyser.jobs.storage_housekeeping
# Apply only the exact cloud plan already reviewed.
python -m stock_analyser.jobs.storage_housekeeping --apply-cloud-plan <reviewed-cloud-plan-id>
```

Scheduled runs never delete data. Apply recomputes the plan under the same lease
used by publishers and rollback, and rejects changed inventory or policy.
Wait for any jobs using code from before the lease was introduced to finish
before applying cleanup. Unknown files and other markets are preserved.

For local cache cleanup, stop the local app and refresh processes, then apply
the reviewed cache plan:

```powershell
python -m stock_analyser.jobs.storage_housekeeping --apply-cache-plan <reviewed-cache-plan-id> --offline
```

Cleanup is restricted to eligible files within this project's `.snapshot-cache`;
current snapshot files, reports, fresh files, and unknown files are preserved.
This command does not clean a running hosted app's cache.

Defaults warn at 80% of the 10 GB market storage budget or above the 2 GB local
cache budget. These are operational thresholds; Cloudflare Metrics shows
account-wide storage and request usage. Warnings appear in job logs and summaries.
