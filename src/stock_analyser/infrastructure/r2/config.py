"""Read cloud credentials only from Streamlit Secrets, with session pinning."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from models.market import market_data_root, market_definition

from stock_analyser.infrastructure.r2.storage import (
    CloudSnapshotStorage,
    LocalSnapshotStorage,
    SnapshotStorageError,
)


def market_storage_prefix(configuration, market="IN"):
    market_definition(market)
    prefix = configuration.get("prefix", "").strip("/")
    return f"{prefix}/markets/{market}" if prefix else f"markets/{market}"


def create_storage_client(configuration):
    """Use the common S3 subset supported by both R2 and AWS."""
    import boto3
    from botocore.config import Config

    endpoint = configuration.get("endpoint_url", "")
    if endpoint and not endpoint.startswith("https://"):
        raise SnapshotStorageError("Storage endpoint must use HTTPS")
    return boto3.client(
        "s3", endpoint_url=endpoint or None,
        region_name=configuration.get("region", "auto"),
        aws_access_key_id=configuration["access_key_id"],
        aws_secret_access_key=configuration["secret_access_key"],
        config=Config(
            connect_timeout=10, read_timeout=60,
            max_pool_connections=20,
            retries={"max_attempts": 3, "mode": "standard"},
            request_checksum_calculation="when_required",
            response_checksum_validation="when_required",
        ),
    )


def configured_cloud_storage(configuration, project_root: Path, market="IN"):
    market_definition(market)
    client = create_storage_client(configuration)
    namespace = hashlib.sha256(json.dumps({
        key: configuration.get(key, "")
        for key in ("endpoint_url", "bucket", "prefix")
    }, sort_keys=True).encode()).hexdigest()[:16]
    return CloudSnapshotStorage(
        client, configuration["bucket"], market_storage_prefix(configuration, market),
        Path(project_root) / ".snapshot-cache" / namespace / market,
        configuration.get("snapshot_ids", {}).get(market, ""), market=market,
    )


def application_snapshot_storage(project_root: Path, market="IN"):
    """CLI/tests default to local; Streamlit explicitly enables cloud storage.

    A session stays pinned until restart, so charts and reports cannot silently
    switch snapshots after a refresh publishes new data.
    """
    from streamlit.runtime.scriptrunner import get_script_run_ctx

    local_root = market_data_root(Path(project_root), market)

    if get_script_run_ctx(suppress_warning=True) is None:
        return LocalSnapshotStorage(local_root, market)
    import streamlit as st

    try:
        configuration = dict(st.secrets.get("storage", {}))
        if "snapshot_ids" in configuration:
            configuration["snapshot_ids"] = dict(configuration["snapshot_ids"])
    except FileNotFoundError:
        configuration = {}
    if configuration.get("provider", "local") == "local":
        return LocalSnapshotStorage(local_root, market)
    if configuration.get("provider") not in {"r2", "s3"}:
        raise SnapshotStorageError("Unsupported snapshot storage provider")
    # Include credentials in the fingerprint, never in output or logs.
    fingerprint = hashlib.sha256(json.dumps(configuration, sort_keys=True).encode()).hexdigest()
    session_key = f"_application_snapshot_storage_{market}"
    previous = st.session_state.get(session_key)
    if previous is None or previous[0] != fingerprint:
        try:
            storage = configured_cloud_storage(configuration, project_root, market)
        except (KeyError, ImportError):
            raise SnapshotStorageError("Cloud storage configuration or dependencies are missing") from None
        st.session_state[session_key] = (fingerprint, storage)
    return st.session_state[session_key][1]
