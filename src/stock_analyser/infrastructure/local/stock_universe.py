"""Resolve the explicitly active, versioned stock universe."""

from __future__ import annotations

from pathlib import Path
from stock_analyser.infrastructure.r2.storage import LocalSnapshotStorage


class StockUniverse:
    """Reads the manifest that selects one validated stock snapshot."""

    def __init__(self, universe_root: Path, storage=None) -> None:
        self.universe_root = universe_root
        self.manifest_file = universe_root / "manifest.json"
        self.storage = storage or LocalSnapshotStorage(universe_root)

    def active_file(self) -> Path:
        """Return the validated universe explicitly selected by the manifest."""
        manifest = self.metadata()
        relative_path = manifest.get("active_universe")
        if not relative_path:
            raise ValueError("Stock-universe manifest has no active_universe entry")

        active_file = self.storage.path(relative_path)
        if not active_file.is_file():
            raise ValueError("Stock-universe manifest points to a missing file")
        return active_file

    def metadata(self) -> dict:
        return self.storage.read_json("manifest.json")
