"""Explicit credential sources for local maintenance and GitHub Actions."""

import json
import os
import tomllib

from stock_analyser.infrastructure.r2.storage import SnapshotStorageError


def load_refresh_configuration(project_root, source="streamlit", environment=None):
    if source == "streamlit":
        with (project_root / ".streamlit/secrets.toml").open("rb") as stream:
            settings = tomllib.load(stream)
        return settings["storage"], settings["storage_publisher"]
    if source != "github":
        raise SnapshotStorageError("Unsupported refresh credential source")

    environment = os.environ if environment is None else environment
    try:
        configuration = json.loads(environment.get("R2_PUBLISHER_CONFIG", ""))
        required = ("endpoint_url", "bucket", "access_key_id", "secret_access_key")
        if not isinstance(configuration, dict) or any(
            not isinstance(configuration.get(key), str) or not configuration[key].strip()
            for key in required
        ):
            raise ValueError
        if not configuration["endpoint_url"].startswith("https://"):
            raise ValueError
    except (ValueError, TypeError):
        raise SnapshotStorageError("R2_PUBLISHER_CONFIG is missing or invalid; configure the GitHub Actions Secret") from None
    configuration = {key: configuration[key] for key in
                     (*required, "region", "prefix") if key in configuration}
    configuration.setdefault("region", "auto")
    configuration.setdefault("prefix", "")
    # The publisher token can read the source; the deployed app uses a separate
    # read-only token. Never materialize this configuration in the checkout.
    return dict(configuration), dict(configuration)
