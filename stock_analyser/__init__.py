"""Temporary source-checkout shim for the incremental src-layout migration.

Installed environments load ``src/stock_analyser`` directly. Existing jobs that
run from a repository checkout can continue importing ``stock_analyser`` before
all entrypoints have moved into the package.
"""

from pathlib import Path


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_SOURCE_PACKAGE = _PROJECT_ROOT / "src" / "stock_analyser"
if str(_SOURCE_PACKAGE) not in __path__:
    __path__.append(str(_SOURCE_PACKAGE))

PROJECT_ROOT = _PROJECT_ROOT
