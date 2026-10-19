"""Immutable snapshot storage contract."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class StoragePort(Protocol):
    market: str
    cloud: bool

    def path(self, relative_path: str) -> Path: ...

    def read_json(self, relative_path: str) -> dict: ...
