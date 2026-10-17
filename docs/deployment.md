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
- Daily and monthly workflows are prepared to publish to R2 instead of Git.
- The user approved a GitHub Actions Secrets exception for scheduled R2 jobs.
  `R2_PUBLISHER_CONFIG` has been configured securely in the repository. App and
  model credentials remain in Streamlit Secrets.
- Candidates now pass full remote hash verification before pointer activation.
- The latest universe refresh did not publish because Yahoo rate-limited market
  caps. Retain the existing valid universe until a complete refresh succeeds.
- Migration changes are published on `deploy/r2-scheduled-refresh` for review in
  [PR #19](https://github.com/anshu10virgo/Stock-Analyser-YF/pull/19). The production
  schedule changes only after merge to `main`.

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
    run. Retain Git-backed data until the cutover checks pass.

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
(03:30 Asia/Kolkata on the second). The converted schedules take effect only
after the workflow changes reach the default branch.

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

Keep immutable files referenced by every retained catalog. Do not apply age-only
deletion to shared dataset objects. Add bounded local-cache cleanup and storage
usage reporting as operational follow-up.

For current commands and the physical dataset layout, see [cloud_storage.md](cloud_storage.md).
