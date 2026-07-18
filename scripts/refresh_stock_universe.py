"""Manually refresh the validated NSE universe used by Stock Analyser YF.

Run this maintenance command roughly every six months. It is intentionally not
called by Streamlit and never changes the active universe until validation has
completed successfully.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from providers.yahoo_finance import YahooFinanceHistoryProvider


NSE_EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"
UNIVERSE_ROOT = PROJECT_ROOT / "data" / "stock_universe"


def parse_arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-url", default=NSE_EQUITY_URL)
    parser.add_argument("--series", default="EQ", help="NSE series to include")
    parser.add_argument("--chunk-size", type=int, default=100)
    return parser.parse_args()


def download_nse_source(source_url: str) -> bytes:
    request = Request(source_url, headers={"User-Agent": "Stock-Analyser-YF/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def build_candidates(raw_source: bytes, series: str) -> pd.DataFrame:
    source = pd.read_csv(BytesIO(raw_source))
    source.columns = source.columns.astype(str).str.strip()
    required = {"SYMBOL", "SERIES"}
    if not required.issubset(source.columns):
        raise ValueError("NSE source does not contain SYMBOL and SERIES columns")

    equities = source.loc[
        source["SERIES"].astype(str).str.upper().eq(series.upper())
    ].copy()
    equities["Symbol"] = equities["SYMBOL"].astype(str).str.strip() + ".NS"
    equities["NSE Symbol"] = equities["SYMBOL"].astype(str).str.strip()
    equities["Company Name"] = equities.get("NAME OF COMPANY")
    equities["ISIN"] = equities.get("ISIN NUMBER")
    return equities[["Symbol", "NSE Symbol", "Company Name", "ISIN", "SERIES"]]


def validate_candidates(candidates: pd.DataFrame, chunk_size: int):
    provider = YahooFinanceHistoryProvider()
    accepted = []
    rejected = []
    for start in range(0, len(candidates), chunk_size):
        chunk = candidates.iloc[start:start + chunk_size]
        symbols = chunk["Symbol"].tolist()
        try:
            batch_data = provider.download_batch(symbols, years=1)
        except RuntimeError as error:
            rejected.extend(
                {"symbol": symbol, "reason": str(error)} for symbol in symbols
            )
            continue

        for _, candidate in chunk.iterrows():
            history = provider.get_symbol_history(batch_data, candidate["Symbol"])
            if history.empty:
                rejected.append(
                    {"symbol": candidate["Symbol"], "reason": "No Yahoo price history"}
                )
            else:
                accepted.append(candidate.to_dict())
    return pd.DataFrame(accepted), rejected, provider.metrics()


def write_refresh_artifacts(
    raw_source,
    candidate_count,
    validated,
    rejected,
    metrics,
    source_url,
):
    refreshed_at = datetime.now(timezone.utc).date().isoformat()
    for directory in ("snapshots", "validated", "refresh_reports"):
        (UNIVERSE_ROOT / directory).mkdir(parents=True, exist_ok=True)

    snapshot_name = f"nse_equity_{refreshed_at}.csv"
    validated_name = f"yahoo_nse_{refreshed_at}.csv"
    snapshot_file = UNIVERSE_ROOT / "snapshots" / snapshot_name
    validated_file = UNIVERSE_ROOT / "validated" / validated_name
    report_file = UNIVERSE_ROOT / "refresh_reports" / f"{refreshed_at}.json"
    snapshot_file.write_bytes(raw_source)
    validated.to_csv(validated_file, index=False)

    report = {
        "refreshed_at": refreshed_at,
        "source_url": source_url,
        "candidate_symbol_count": candidate_count,
        "validated_symbol_count": len(validated),
        "rejected_symbol_count": len(rejected),
        "provider_metrics": metrics,
        "rejected_symbols": rejected,
    }
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")

    manifest = {
        "active_universe": f"validated/{validated_name}",
        "source_snapshot": f"snapshots/{snapshot_name}",
        "refresh_report": f"refresh_reports/{refreshed_at}.json",
        "refreshed_at": refreshed_at,
        "validated_symbol_count": len(validated),
        "sha256": hashlib.sha256(validated_file.read_bytes()).hexdigest(),
    }
    manifest_file = UNIVERSE_ROOT / "manifest.json"
    temporary_file = manifest_file.with_suffix(".json.tmp")
    temporary_file.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    temporary_file.replace(manifest_file)
    return manifest


def main():
    arguments = parse_arguments()
    raw_source = download_nse_source(arguments.source_url)
    candidates = build_candidates(raw_source, arguments.series)
    validated, rejected, metrics = validate_candidates(candidates, arguments.chunk_size)
    if validated.empty:
        raise RuntimeError("No Yahoo symbols validated; manifest was not updated")

    manifest = write_refresh_artifacts(
        raw_source,
        len(candidates),
        validated,
        rejected,
        metrics,
        arguments.source_url,
    )
    print(
        f"Activated {manifest['validated_symbol_count']} Yahoo NSE symbols "
        f"from {manifest['active_universe']}"
    )


if __name__ == "__main__":
    main()
