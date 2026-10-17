# Storage housekeeping

Policy lives in `config/storage_housekeeping.toml`; it contains no credentials.
Ticksy does not perform maintenance. Financial calculations are unchanged.

## Snapshot retention

Keep the newest 30 catalogs, the newest checkpoint in each of the latest 12
months represented by catalogs, the active catalog, and explicit protected IDs.
Catalog timestamps come from R2 object metadata. Recent catalogs and uploads are
protected for seven days. Catalogs left by failed activations may also be retained;
favoring extra rollback data is intentional.

The original verified cutover snapshot is protected while Git retirement is
pending. Add every persistent deployed snapshot pin to `protected_snapshot_ids`;
the maintenance runner cannot discover another app's private Streamlit Secrets.
Configured local pins are protected for the corresponding market too.

Cleanup validates catalog hashes, market identity, and retained file existence
and sizes. It deletes only expired catalogs and old versioned dataset objects
that no retained catalog references. Shared files, `current.json`, unknown keys,
other markets, and maintenance state are preserved. Do not use age-only R2
lifecycle rules on these dataset folders.
Orphans with versioned filenames must also carry the expected SHA-256 ownership
metadata before becoming eligible for deletion.

Publication, rollback, and retention use the same renewable conditional-write
lease. Source fetching runs outside the lease; publication acquires it for
object writes, verification, and activation. An
expired owner cannot renew or activate. Wait for any jobs using code from before
this lease was introduced to finish before applying the first cloud cleanup.

## Preview and apply

```powershell
python scripts/storage_housekeeping.py
```

The default is a dry run. Review `.snapshot-cache/housekeeping-report.json` for
exact delete candidates, reclaimable bytes, protected catalogs, dataset usage,
cache usage, and the Git-data audit. Unknown files are reported and preserved.
The report contains no credentials.
It also audits workflow targets, declared repository permissions, and direct
Git add/commit/push commands. This is a direct-command check; scripts called by
new or modified workflows still need review for indirect side effects.

```powershell
python scripts/storage_housekeeping.py --apply-cloud-plan <reviewed-cloud-plan-id>
```

Application recomputes the plan under the publisher lease and rejects a changed
inventory, pointer, retention selection, or policy. Deletion is limited to exact
keys from that fresh plan. A partial storage error stops cleanup and requires a
new preview; retained snapshots are never deletion candidates.

GitHub's **R2 storage housekeeping** workflow previews every Sunday at 06:45 IST.
Its manual `apply_plan_id` input can apply a reviewed cloud plan. Scheduled runs
never delete data. It shares `r2-data-refresh` concurrency with both refresh jobs.
Reports are saved as Actions artifacts for 30 days. Daily and monthly refresh
jobs also report usage and retain their reports alongside refresh reports.

## Local cache cleanup

The same report previews obsolete objects in the configured reader cache and old
isolated refresh-run files. Current snapshot objects, catalog files, run reports,
unknown files, and fresh files are preserved. Other reader namespaces are left
alone. Symlinks and Windows junctions are not followed. Prepared migration
packages outside isolated refresh runs are not removed automatically.

Stop the local Streamlit app and local refresh processes before applying:

```powershell
python scripts/storage_housekeeping.py --apply-cache-plan <reviewed-cache-plan-id> --offline
```

This is an offline maintenance command, not a live app-session eviction job.
Exact resolved paths must remain within this project's `.snapshot-cache`, and
each candidate's size and modification time are rechecked before deletion.
Changing the cache budget raises a warning; it does not override the age and
reference protections. GitHub scratch-cache usage is distinct from the hosted
Streamlit app's cache. To clean a hosted cache, run maintenance while its app is
stopped through the hosting platform's supported maintenance mechanism.

## Usage monitoring

Reports measure listed object payload bytes in the selected market prefix,
object/catalog counts, bytes by dataset, retained referenced bytes, reclaimable
bytes, and local cache bytes. Defaults warn at 80% of a configurable 10-billion-
byte market storage budget, or above a 2-billion-byte local cache budget.
These are operational budgets, not billing estimates, monthly average storage,
or API-operation quotas. Use Cloudflare Metrics for account-wide usage and
request statistics. Housekeeping warnings appear in logs and the Actions job
summary; job failures use the existing failure email mechanism.

## Git-backed data retirement

The owner requested Git data retirement in this release. Every committed
production file, including historical universe versions, is archived verbatim at
`markets/IN/archives/git-data/<archive-id>/files/data/`. The archive manifest is
content-addressed, all uploaded bytes are read back and verified, and
`config/git_data_retirement.json` records the source commit and archive identity.
This permanent archive is outside retention deletion candidates.

The current Git tree no longer contains production datasets. Existing local
copies are left on disk and ignored by Git. Tests generate temporary fixtures;
CI also checks that its fresh checkout has no `data/` directory. The active R2
snapshot and the protected cutover baseline are preserved.

Download the current snapshot for development, including every per-symbol file:

```powershell
python scripts/cloud_snapshots.py download
```

Restore the exact old Git datasets, including historical universe versions:

```powershell
python scripts/archive_git_data.py --restore --data-root .snapshot-cache/git-archive-restore
```

Both download paths use read-only Streamlit Secrets, verify hashes, and refuse
to overwrite differing local files without `--overwrite`. For comparisons, run
`scripts/verify_cloud_results.py --data-root <download-root> --app`.

Observing changed-data publication and completing hosted smoke checks remain
operational follow-up. No Git history is rewritten: old commits still contain
their historical data, so checkout retirement does not shrink existing history.
