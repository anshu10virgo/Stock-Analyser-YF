"""Compatibility launcher for the packaged storage-housekeeping job."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from stock_analyser.jobs import storage_housekeeping as _implementation


if __name__ == "__main__":
    raise SystemExit(_implementation.cli())
else:
    sys.modules[__name__] = _implementation
