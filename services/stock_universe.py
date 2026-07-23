"""Resolve the explicitly active, versioned stock universe."""

from __future__ import annotations

import json
from pathlib import Path


class StockUniverse:
    """Reads the manifest that selects one validated stock snapshot."""

    def __init__(self, universe_root: Path) -> None:
        self.universe_root = universe_root
        self.manifest_file = universe_root / "manifest.json"

    def active_file(self) -> Path:
        """Return the validated universe explicitly selected by the manifest."""
        if not self.manifest_file.exists():
            raise FileNotFoundError("Stock-universe manifest is missing")

        manifest = self.metadata()
        relative_path = manifest.get("active_universe")
        if not relative_path:
            raise ValueError("Stock-universe manifest has no active_universe entry")

        active_file = (self.universe_root / relative_path).resolve()
        if self.universe_root.resolve() not in active_file.parents:
            raise ValueError("Stock-universe manifest points outside its directory")
        if not active_file.is_file():
            raise ValueError("Stock-universe manifest points to a missing file")
        return active_file

    def metadata(self) -> dict:
        if not self.manifest_file.exists():
            raise FileNotFoundError("Stock-universe manifest is missing")
        return json.loads(self.manifest_file.read_text(encoding="utf-8"))
