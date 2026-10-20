"""Regression tests for packaged operational job entrypoints."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from stock_analyser.jobs import market_refresh, storage_housekeeping


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_legacy_job_modules_alias_canonical_implementations():
    aliases = {
        "scripts.refresh_cloud_market_data": "stock_analyser.jobs.market_refresh",
        "scripts.refresh_market_data": "stock_analyser.jobs._market_snapshot_refresh",
        "scripts.refresh_screener_fundamentals": "stock_analyser.jobs.screener_refresh",
        "scripts.storage_housekeeping": "stock_analyser.jobs.storage_housekeeping",
        "scripts.send_refresh_failure_email": "stock_analyser.jobs.refresh_alert",
    }

    for legacy_name, canonical_name in aliases.items():
        assert importlib.import_module(legacy_name) is importlib.import_module(canonical_name)


def test_github_actions_invoke_only_packaged_operational_jobs():
    workflow_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((PROJECT_ROOT / ".github/workflows").glob("*.y*ml"))
    )

    assert "python -u -m stock_analyser.jobs.market_refresh" in workflow_sources
    assert "python -m stock_analyser.jobs.storage_housekeeping" in workflow_sources
    assert "python -m stock_analyser.jobs.refresh_alert" in workflow_sources
    assert "python -u scripts/refresh_cloud_market_data.py" not in workflow_sources
    assert "python scripts/storage_housekeeping.py" not in workflow_sources
    assert "python scripts/send_refresh_failure_email.py" not in workflow_sources


def test_screener_workflow_has_automatic_next_day_failed_record_retry():
    source = (
        PROJECT_ROOT / ".github/workflows/refresh-screener-fundamentals.yml"
    ).read_text(encoding="utf-8")

    assert 'cron: "0 22 1 * *"' in source
    assert 'cron: "0 22 2 * *"' in source
    assert 'SCHEDULE_EXPRESSION: ${{ github.event.schedule }}' in source
    assert 'if [ "$SCHEDULE_EXPRESSION" = "0 22 2 * *" ]; then' in source
    assert "OPTIONS+=(--retry-failed)" in source


def test_market_job_executes_through_refresh_workflow():
    expected = {"status": "no_new_data", "snapshot_id": "snapshot"}
    with patch.object(market_refresh, "run_daily_refresh", return_value=expected) as refresh:
        result = market_refresh.execute_refresh_job(
            PROJECT_ROOT,
            {"bucket": "bucket"},
            {"bucket": "bucket"},
            dataset="market",
            mode="incremental",
        )

    assert result == expected
    refresh.assert_called_once()


def test_housekeeping_dry_run_never_calls_mutating_adapters(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "storage_housekeeping.toml").write_text("", encoding="utf-8")
    output = tmp_path / "housekeeping.json"
    arguments = SimpleNamespace(
        config_source="github",
        market="IN",
        output=output,
        apply_cloud_plan="",
        apply_cache_plan="",
        offline=False,
    )
    reader = {"bucket": "bucket", "snapshot_ids": {"IN": "snapshot"}}
    writer = {"bucket": "bucket"}
    cloud_plan = {
        "stored_bytes": 100,
        "object_count": 2,
        "retained_snapshot_ids": ["snapshot"],
        "catalog_count": 1,
        "reclaimable_bytes": 0,
        "current_snapshot_id": "snapshot",
        "plan_id": "cloud-plan",
        "usage_warning": False,
    }
    cache_plan = {
        "stored_bytes": 50,
        "reclaimable_bytes": 0,
        "plan_id": "cache-plan",
        "usage_warning": False,
    }
    apply_cloud = Mock()
    apply_cache = Mock()
    write_report = Mock()

    result = storage_housekeeping.execute_housekeeping(
        arguments,
        project_root=tmp_path,
        configuration_loader=lambda *_: (reader, writer),
        storage_client_factory=lambda _: object(),
        storage_factory=lambda *_: SimpleNamespace(root=tmp_path, catalog={}),
        retention_planner=lambda *_, **__: cloud_plan,
        retention_applier=apply_cloud,
        cache_planner=lambda *_: cache_plan,
        cache_applier=apply_cache,
        git_audit=lambda *_: {"tracked_files": 0},
        workflow_audit=lambda *_: [],
        report_writer=write_report,
    )

    assert result["mode"] == "dry_run"
    apply_cloud.assert_not_called()
    apply_cache.assert_not_called()
    write_report.assert_called_once()


def test_legacy_launchers_remain_thin_compatibility_files():
    names = (
        "refresh_cloud_market_data.py",
        "refresh_market_data.py",
        "refresh_screener_fundamentals.py",
        "storage_housekeeping.py",
        "send_refresh_failure_email.py",
    )

    for name in names:
        lines = (PROJECT_ROOT / "scripts" / name).read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 20
        assert "stock_analyser.jobs" in "\n".join(lines)
