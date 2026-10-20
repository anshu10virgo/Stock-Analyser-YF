"""Run the normal daily India refresh from R2, validate, then publish to R2."""

from __future__ import annotations

import json
import argparse
import subprocess
import sys
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[3]

from stock_analyser.application.workflows.refresh_workflow import RefreshStep, RefreshWorkflow
from services.snapshot_publication import SnapshotPublisher, _references, prepare_snapshot
from stock_analyser.infrastructure.r2.config import (
    configured_cloud_storage,
    create_storage_client,
    market_storage_prefix,
)
from stock_analyser.infrastructure.r2.storage import (
    LocalSnapshotStorage,
    SnapshotStorageError,
    atomic_write,
)
from services.refresh_config import load_refresh_configuration


def stage_source_snapshot(storage, staging):
    """Materialize original source files; omit derived per-stock chart copies."""
    destination = LocalSnapshotStorage(staging)
    count = 0
    for dataset in ("stock_universe", "market_data", "market_data/screener"):
        manifest_name = f"{dataset}/manifest.json"
        manifest = storage.read_json(manifest_name)
        names = [manifest_name] + [f"{dataset}/{entry['path']}" for entry in _references(manifest)]
        for name in names:
            atomic_write(destination.path(f"data/{name}"), storage.path(name).read_bytes())
            count += 1
    return count


def run_daily_refresh(
    project_root,
    configuration,
    publisher_configuration,
    run_command=subprocess.run,
    refresh_universe=False,
    dataset="market",
    mode=None,
    config_source="streamlit",
    retry_failed=False,
    *,
    storage_factory=None,
    storage_client_factory=None,
    publisher_factory=None,
):
    """Stage, validate, and atomically publish one cloud refresh."""
    storage_factory = storage_factory or configured_cloud_storage
    storage_client_factory = storage_client_factory or create_storage_client
    publisher_factory = publisher_factory or SnapshotPublisher
    mode = mode or ("refresh" if dataset == "screener" else "incremental")
    allowed = {"market": {"incremental", "classifications", "validate"},
               "screener": {"refresh", "validate"}}
    if dataset not in allowed or mode not in allowed[dataset] or (refresh_universe and (dataset != "market" or mode != "incremental")):
        raise ValueError("Unsupported cloud refresh combination")
    if retry_failed and (dataset != "screener" or mode != "refresh"):
        raise ValueError("Failed-record retries require a Screener refresh")
    latest_configuration = dict(configuration)
    latest_configuration.pop("snapshot_ids", None)
    source = storage_factory(latest_configuration, project_root)
    publisher = publisher_factory(storage_client_factory(publisher_configuration),
        publisher_configuration["bucket"], market_storage_prefix(publisher_configuration))
    if (configuration["bucket"], market_storage_prefix(configuration), configuration.get("endpoint_url")) != (
        publisher_configuration["bucket"], market_storage_prefix(publisher_configuration),
        publisher_configuration.get("endpoint_url")
    ):
        raise SnapshotStorageError("Reader and publisher must use the same R2 location")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run_type = "universe-refresh" if refresh_universe else f"{dataset}-refresh"
    staging = project_root / ".snapshot-cache" / run_type / "IN" / run_id
    print(f"Starting from R2 snapshot {source.snapshot_id}", flush=True)
    count = stage_source_snapshot(source, staging)
    print(f"Staged {count} source files; Screener history retained", flush=True)
    manifest_path = staging / "data/market_data/manifest.json"
    before = manifest_path.read_bytes()
    universe_root = staging / "data/stock_universe"
    universe_path = universe_root / "manifest.json"
    universe_before = universe_path.read_bytes()
    screener_path = staging / "data/market_data/screener/manifest.json"
    screener_before = screener_path.read_bytes()
    old_universe = json.loads(universe_before)
    old_symbols = set(pd.read_csv(universe_root / old_universe["active_universe"])["Symbol"])
    if refresh_universe:
        run_command([sys.executable, "-u", str(project_root / "scripts/refresh_stock_universe.py"),
                     "--data-root", str(staging)], check=True)
        print("Universe validated; synchronizing price history and supporting data", flush=True)
    if dataset == "screener":
        for screener_mode in (("validate",) if mode == "validate" else ("refresh", "validate")):
            checkpoint_arguments = (["--durable-checkpoint", "--config-source", config_source]
                                    if screener_mode == "refresh" else [])
            if screener_mode == "refresh" and retry_failed:
                checkpoint_arguments.append("--retry-failed")
            run_command([sys.executable, "-u", str(project_root / "scripts/refresh_screener_fundamentals.py"),
                         "--mode", screener_mode, "--data-root", str(staging), *checkpoint_arguments], check=True)
        if mode != "validate":
            previous = json.loads(screener_before).get("successful_symbol_count", 0)
            refreshed = json.loads(screener_path.read_bytes()).get("successful_symbol_count", 0)
            if not refreshed or refreshed < previous * 0.9:
                raise SnapshotStorageError("Screener coverage fell unexpectedly; publication stopped")
    market_modes = (("validate",) if mode == "validate" else
                    (("fundamentals", "validate") if dataset == "screener" else (mode, "validate")))
    for market_mode in market_modes:
        run_command([sys.executable, "-u", str(project_root / "scripts/refresh_market_data.py"),
                     "--mode", market_mode, "--data-root", str(staging)], check=True)
    manifest = json.loads(manifest_path.read_bytes())
    result = {"source_snapshot_id": source.snapshot_id, "dataset": dataset, "mode": mode,
              "last_trading_date": manifest["last_trading_date"], "staged_source_files": count}
    if refresh_universe:
        universe = json.loads(universe_path.read_bytes())
        symbols = set(pd.read_csv(universe_root / universe["active_universe"])["Symbol"])
        result["universe"] = {
            "previous_count": len(old_symbols), "validated_count": len(symbols),
            "ranked_count": universe.get("market_cap_ranked_symbol_count", 0),
            "added": sorted(symbols - old_symbols), "removed": sorted(old_symbols - symbols),
            "refreshed_at": universe["refreshed_at"],
        }
    if mode == "validate":
        source.verify_files()
        result.update(status="validated", snapshot_id=source.snapshot_id)
    elif (manifest_path.read_bytes() == before and universe_path.read_bytes() == universe_before
          and screener_path.read_bytes() == screener_before):
        result.update(status="no_new_data", snapshot_id=source.snapshot_id)
    else:
        prepared = staging / "prepared"
        snapshot_id, _ = prepare_snapshot(staging, prepared)

        def progress(completed, total):
            if completed % 250 == 0 or completed == total:
                print(f"Validated publication objects: {completed}/{total}", flush=True)

        metrics = publisher.publish(prepared, snapshot_id, progress,
                                    expected_snapshot_id=source.snapshot_id)
        verification = dict(configuration)
        verification["snapshot_ids"] = {"IN": snapshot_id}
        verified = storage_factory(verification, project_root)
        verified.verify_files(progress)
        result.update(status="published", snapshot_id=snapshot_id, publication=metrics)
    atomic_write(staging / "refresh_report.json", json.dumps(result, indent=2).encode())
    return result


def execute_refresh_job(
    project_root,
    configuration,
    publisher_configuration,
    **refresh_options,
):
    """Execute the operational refresh through the application workflow boundary."""
    dataset = refresh_options.get("dataset", "market")
    mode = refresh_options.get("mode") or (
        "refresh" if dataset == "screener" else "incremental"
    )
    step_name = f"{dataset}_{mode}"
    workflow = RefreshWorkflow(
        (
            RefreshStep(
                step_name,
                lambda: run_daily_refresh(
                    project_root,
                    configuration,
                    publisher_configuration,
                    **refresh_options,
                ),
            ),
        )
    )
    return workflow.execute()[step_name]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-source", choices=("streamlit", "github"), default="streamlit")
    parser.add_argument("--dataset", choices=("market", "screener"), default="market")
    parser.add_argument("--mode", choices=("incremental", "classifications", "refresh", "validate"))
    parser.add_argument("--refresh-universe", action="store_true",
                        help="Rebuild NSE universe and synchronize its market data before publication")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry failed Screener checkpoint records as well as pending stocks")
    arguments = parser.parse_args()
    configuration, publisher = load_refresh_configuration(PROJECT_ROOT, arguments.config_source)
    result = execute_refresh_job(
        PROJECT_ROOT,
        configuration,
        publisher,
        refresh_universe=arguments.refresh_universe,
        dataset=arguments.dataset,
        mode=arguments.mode,
        config_source=arguments.config_source,
        retry_failed=arguments.retry_failed,
        storage_factory=configured_cloud_storage,
        storage_client_factory=create_storage_client,
        publisher_factory=SnapshotPublisher,
    )
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
            stream.write(f"### R2 {result['dataset']} refresh\n\n"
                         f"- Status: {result['status']}\n"
                         f"- Price date: {result['last_trading_date']}\n"
                         f"- Snapshot: `{result['snapshot_id']}`\n")
    print(json.dumps(result, indent=2), flush=True)
    return result


def cli() -> int:
    """Run the command-line job and emit a sanitized failure artifact."""
    try:
        main()
    except Exception:
        atomic_write(PROJECT_ROOT / ".snapshot-cache/refresh_failure.json", json.dumps({
            "status": "failed", "reported_at": datetime.now(timezone.utc).isoformat(),
            "message": "Cloud refresh failed; inspect the workflow provider diagnostics.",
        }, indent=2).encode())
        print("Cloud refresh failed. Check provider diagnostics; no Git data was changed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
