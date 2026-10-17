# R2 deployment runbook

## Target

- Streamlit Community Cloud runs `app.py` from this repository's `main` branch.
- The app reads the private `stock-analyser-data` bucket using read-only credentials.
- GitHub Actions refreshes and publishes India snapshots independently of the app.
- `markets/IN` is active; `markets/US` remains reserved until its pipeline exists.
- Ticksy interprets local application results. Python services perform calculations.

## Current readiness

- R2 reader, immutable datasets, catalog pinning, and rollback commands exist.
- The manual daily R2 refresh command exists.
- Daily and monthly workflows are active on `main` and publish to R2 instead of Git.
- The user approved a GitHub Actions Secrets exception for scheduled R2 jobs.
  `R2_PUBLISHER_CONFIG` has been configured securely in the repository. App and
  model credentials remain in Streamlit Secrets.
- Candidates now pass full remote hash verification before pointer activation.
- The latest universe refresh did not publish because Yahoo rate-limited market
  caps. Retain the existing valid universe until a complete refresh succeeds.
- [PR #19](https://github.com/anshu10virgo/Stock-Analyser-YF/pull/19) was merged to
  `main` on October 17, 2026 (`72e1835`). Both R2 refresh schedules are configured
  on the default branch.
- Both GitHub-hosted validation-only jobs passed, as did 146 local unit tests and
  local/R2 universe, sample stock, scanner, Backtester, and Setup comparisons.
- The first [normal production refresh](https://github.com/anshu10virgo/Stock-Analyser-YF/actions/runs/39027024667)
  passed on October 17. It validated 3,939,371 stored price rows through October
  16 and returned `no_new_data`, retaining the active snapshot. No rate-limit
  messages were reported. A changed-data publication still needs observation.
- Hosted app: https://stock-analyser-yf.streamlit.app/. On October 17, the owner
  confirmed saving read-only `[storage]` settings and rebooting. The public page
  responds with HTTP 200. R2 still contains a matching universe/market-data pair,
  2,287 symbols, and prices through October 16. The owner also confirmed that the
  rebooted Setup page shows Cloud snapshot through October 16. Hosted R2 read
  cutover is confirmed; observing the first scheduled changed-data publication
  remains the next operational check.
- Production datasets are retired from the current Git tree in this release.
  The exact old Git files have a verified permanent R2 archive, recorded in
  `config/git_data_retirement.json`. Tests generate fixtures and CI checks a
  data-free checkout. Download commands support offline local development.

## Implementation and rollout order

1. Resolve runner credentials. Never commit Secrets or include publisher keys in
   the deployed app. Limit app access to reads and publisher access to the bucket.
2. Convert daily market-data and monthly Screener jobs to stage the latest R2
   snapshot, refresh, validate, and publish. Keep universe rebuilds manual.
3. Serialize publishers with one workflow concurrency group and retain the
   existing starting-snapshot and conditional-pointer guards. Remove Git data
   commits from the converted workflows and reduce repository permissions to read.
4. Validate freshness, coverage, universe references, hashes, and sample application
   results before activating a candidate. Verify uploaded files before changing
   `current.json`; preserve the previous pointer on failure.
5. Keep bounded provider retries and fail on throttling. Include failures, stale
   data, and unexpectedly empty responses in run reports and notifications.
6. Expose dataset dates and a deliberate way to load a newly published snapshot
   without mixing it into an existing scan or Backtest.
7. Review deployment dependencies and test in the chosen hosted Python version.
   Exclude Secrets, local previews, generated caches, and wireframe artifacts.
8. Publish reviewed code. Configure hosted Streamlit Secrets with `[storage]`,
   `provider = "r2"`, the account endpoint, bucket, empty prefix, and read-only keys.
   Leave snapshot pins unset for normal production. Configure Ticksy and report
   email credentials only when enabling those features. Omit `[storage_publisher]`.
9. Manually exercise both converted refresh jobs, then check Setup, scans, charts,
   Backtester, Ticksy, and report export against the active R2 snapshot.
10. Rehearse rollback, verify failure notifications, and observe a scheduled daily
    run. The permanent R2 Git-data archive and protected cutover snapshot support rollback.

## Acceptance checks

- Relevant tests and `git diff --check` pass.
- A changed-data refresh and a no-change run both behave correctly.
- A failed refresh leaves the active snapshot unchanged.
- A competing publisher cannot overwrite a newer snapshot.
- Sample prices, fundamentals, scanner results, and Backtest signals match staging.
- A read-only deployed app loads on an empty cache and cannot publish data.
- Dataset dates distinguish retained fundamentals from newly refreshed values.
- Rollback restores a verified catalog and a fresh app session loads it.

## Operations

The existing daily schedule is weekdays at 12:30 UTC (18:00 Asia/Kolkata).
The existing Screener schedule is 22:00 UTC on the first day of each month
(03:30 Asia/Kolkata on the second). The converted workflows are now on `main`.

## Scheduled credentials

`R2_PUBLISHER_CONFIG` is one GitHub Actions Secret containing JSON with these
fields: `endpoint_url`, `bucket`, `region`, `prefix`, `access_key_id`, and
`secret_access_key`. Use a bucket-scoped Object Read & Write token. Do not print
the JSON, add it to repository files, or copy it to hosted Streamlit Secrets.

The workflows select `--config-source github` explicitly and fail if the Secret
is missing or malformed. Local commands default to Streamlit Secrets. Each job
uploads only its sanitized refresh report, retained for 14 days, and preserves
the existing failure email step. Both use the `r2-data-refresh` concurrency group
and read-only repository permissions.

For a safe first test, manually dispatch each workflow with `mode=validate`.
That mode stages the current R2 source, checks the corresponding dataset and
market data, and verifies every cloud object without publishing.

Keep immutable files referenced by every retained catalog. Retention previews,
offline cache cleanup, and usage reports are implemented in the
[housekeeping workflow](storage_housekeeping.md). Scheduled housekeeping only
reports; deletion requires the exact reviewed plan ID. The exact old Git
datasets are archived separately in R2; see that document for restore commands.

For current commands and the physical dataset layout, see [cloud_storage.md](cloud_storage.md).
