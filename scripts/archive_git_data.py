"""Back up all committed production data to immutable R2 objects before retirement."""

import json
import argparse
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.data_retirement import archive_git_data, restore_git_archive
from services.refresh_config import load_refresh_configuration
from stock_analyser.infrastructure.r2.config import (
    create_storage_client,
    market_storage_prefix,
)
from stock_analyser.infrastructure.r2.storage import atomic_write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restore", action="store_true", help="Restore the recorded archive into a local development root")
    parser.add_argument("--data-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.restore:
        with (PROJECT_ROOT / ".streamlit/secrets.toml").open("rb") as stream:
            reader = tomllib.load(stream)["storage"]
        record = json.loads((PROJECT_ROOT / "config/git_data_retirement.json").read_text(encoding="utf-8"))
        print(json.dumps(restore_git_archive(create_storage_client(reader), reader["bucket"], record,
                                            args.data_root, args.overwrite), indent=2))
        return
    _, configuration = load_refresh_configuration(PROJECT_ROOT)
    with (PROJECT_ROOT / "config/storage_housekeeping.toml").open("rb") as stream:
        policy = tomllib.load(stream)
    record = archive_git_data(PROJECT_ROOT, create_storage_client(configuration),
        configuration["bucket"], market_storage_prefix(configuration), policy["git_baseline_snapshot_id"])
    atomic_write(PROJECT_ROOT / "config/git_data_retirement.json", json.dumps(record, indent=2).encode())
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("Git archive failed; no Git data was removed. Verify storage access and retry.", file=sys.stderr)
        sys.exit(1)
