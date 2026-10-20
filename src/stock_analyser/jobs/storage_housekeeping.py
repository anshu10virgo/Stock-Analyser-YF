"""Preview R2 retention, cache cleanup, and Git-data retirement readiness."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

from stock_analyser.application.workflows.refresh_workflow import RefreshStep, RefreshWorkflow
from services.cache_housekeeping import cache_cleanup_plan, apply_cache_cleanup
from services.refresh_config import load_refresh_configuration
from stock_analyser.infrastructure.r2.config import (
    configured_cloud_storage,
    create_storage_client,
    market_storage_prefix,
)
from stock_analyser.infrastructure.r2.storage import SnapshotStorageError, atomic_write
from services.storage_housekeeping import retention_plan, apply_retention


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def git_data_audit(root, cloud_plan, policy):
    result = subprocess.run(["git", "ls-files", "-z", "--", "data"], cwd=root,
                            check=True, capture_output=True)
    paths = [path.decode("utf-8") for path in result.stdout.split(b"\0") if path]
    record_file = root / "config/git_data_retirement.json"
    record = json.loads(record_file.read_text(encoding="utf-8")) if record_file.is_file() else None
    retired = not paths and record is not None and record.get("status") == "archived_and_verified"
    return {"tracked_files": len(paths),
            "tracked_bytes": sum((root / path).stat().st_size for path in paths if (root / path).is_file()),
            "baseline_snapshot_protected": policy["git_baseline_snapshot_id"] in cloud_plan["retained_snapshot_ids"],
            "changed_snapshot_active": cloud_plan["current_snapshot_id"] != policy["git_baseline_snapshot_id"],
            "removal_performed": retired, "archive_record": record,
            "follow_up_checks": ["Observe the next scheduled changed-data publication",
                                 "Complete remaining hosted functional smoke checks"] if retired else [],
            "remaining_gates": [] if retired else ["Observe a successful changed-data publication and verify rollback",
                                "Complete hosted scan, charts, Backtester, Ticksy, and export smoke checks",
                                "Move local-mode tests and bootstrap workflows off production Git files"],
            "paths": paths}


def workflow_write_audit(root):
    """Expose direct Git write commands and repository permission declarations."""
    reports = []
    for path in sorted((root / ".github/workflows").glob("*.y*ml")):
        source = "\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                           if not line.lstrip().startswith("#"))
        permission = re.search(r"\bcontents:\s*([^\s#]+)", source)
        reports.append({"workflow": path.name,
            "repository_contents_permission": permission[1].strip("\"'") if permission else "not declared",
            "direct_git_write_commands": re.findall(r"\bgit\s+(?:add|commit|push)\b", source),
            "data_target": ("R2" if any(entrypoint in source for entrypoint in
                ("refresh_cloud_market_data.py", "storage_housekeeping.py",
                 "stock_analyser.jobs.market_refresh",
                 "stock_analyser.jobs.storage_housekeeping")) else
                "No data publication" if path.name == "tests.yml" else "review required")})
    return reports


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-source", choices=("streamlit", "github"), default="streamlit")
    parser.add_argument("--market", choices=("IN", "US"), default="IN")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".snapshot-cache/housekeeping-report.json")
    parser.add_argument("--apply-cloud-plan", default="", metavar="PLAN_ID")
    parser.add_argument("--apply-cache-plan", default="", metavar="PLAN_ID")
    parser.add_argument("--offline", action="store_true", help="Confirm apps/maintenance are stopped for local cache cleanup")
    return parser.parse_args()


def execute_housekeeping(
    args,
    *,
    project_root=PROJECT_ROOT,
    configuration_loader=load_refresh_configuration,
    storage_client_factory=create_storage_client,
    storage_factory=configured_cloud_storage,
    retention_planner=retention_plan,
    retention_applier=apply_retention,
    cache_planner=cache_cleanup_plan,
    cache_applier=apply_cache_cleanup,
    git_audit=git_data_audit,
    workflow_audit=workflow_write_audit,
    report_writer=atomic_write,
):
    """Build a plan first, then apply only explicitly requested plan IDs."""
    with (project_root / "config/storage_housekeeping.toml").open("rb") as stream:
        policy = tomllib.load(stream)
    reader, writer = configuration_loader(project_root, args.config_source)
    client = storage_client_factory(writer if args.apply_cloud_plan else reader)
    configuration = writer if args.apply_cloud_plan else reader
    bucket = configuration["bucket"]
    prefix = market_storage_prefix(configuration, args.market)
    pins = {reader.get("snapshot_ids", {}).get(args.market, "")} - {""}
    if args.apply_cloud_plan and any(reader.get(key, "") != writer.get(key, "")
                                    for key in ("endpoint_url", "bucket", "prefix")):
        raise SnapshotStorageError("Reader and publisher locations must match")
    # The cutover baseline and configured pins are India-only unless a US
    # catalog/policy is explicitly introduced in the future.
    if args.market == "US":
        policy = {**policy, "protected_snapshot_ids": []}
        pins = {reader.get("snapshot_ids", {}).get("US", "")} - {""}
    cloud = retention_planner(client, bucket, prefix, policy, protected_ids=pins)
    latest = dict(reader)
    latest["snapshot_ids"] = {args.market: cloud["current_snapshot_id"]}
    storage = storage_factory(latest, project_root, args.market)
    cache = cache_planner(project_root, storage.root, storage.catalog, policy)
    result = {"mode": "dry_run", "cloud": cloud, "cache": cache,
              "git_data": git_audit(project_root, cloud, policy),
              "workflow_write_audit": workflow_audit(project_root)}
    if args.apply_cloud_plan:
        result["cloud_application"] = retention_applier(
            client, bucket, prefix, policy, args.apply_cloud_plan, pins
        )
        result["mode"] = "cloud_cleanup"
    if args.apply_cache_plan:
        result["cache_application"] = cache_applier(
            project_root,
            storage.root,
            storage.catalog,
            policy,
            args.apply_cache_plan,
            offline=args.offline,
        )
        result["mode"] = "cache_cleanup"
    report_writer(args.output, json.dumps(result, indent=2).encode())
    summary = (f"R2: {cloud['stored_bytes']:,} bytes, {cloud['object_count']:,} objects; "
               f"retain {len(cloud['retained_snapshot_ids'])}/{cloud['catalog_count']} snapshots; "
               f"reclaimable {cloud['reclaimable_bytes']:,} bytes.\n"
               f"Local cache: {cache['stored_bytes']:,} bytes; reclaimable {cache['reclaimable_bytes']:,} bytes.\n"
               f"Git production data still tracked: {result['git_data']['tracked_files']} files.\n")
    print(summary)
    print(f"Cloud plan: {cloud['plan_id']}\nCache plan: {cache['plan_id']}\nReport: {args.output}")
    for name, report in (("R2", cloud), ("Cache", cache)):
        if report["usage_warning"]:
            print(f"::warning::{name} storage usage reached the configured warning threshold.")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write("### Storage housekeeping\n\n" + summary.replace("\n", "\n\n"))
    return result


def main():
    args = parse_arguments()
    workflow = RefreshWorkflow(
        (RefreshStep("storage_housekeeping", lambda: execute_housekeeping(args)),)
    )
    return workflow.execute()["storage_housekeeping"]


def cli() -> int:
    """Run housekeeping without exposing credentials in failure output."""
    try:
        main()
    except Exception:
        print("Housekeeping failed; inspect configuration and rerun a dry-run preview. Credentials were not logged.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
