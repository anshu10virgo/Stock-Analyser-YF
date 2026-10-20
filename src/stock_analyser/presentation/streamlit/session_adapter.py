"""Single boundary for Streamlit session state and rerun requests."""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any, Callable

import streamlit as st


class StreamlitSessionAdapter(MutableMapping[str, Any]):
    """Expose session state as an explicit application-presentation boundary."""

    def __init__(
        self,
        state: MutableMapping[str, Any],
        rerun: Callable[[], None] | None = None,
    ) -> None:
        self._state = state
        self._rerun = rerun

    def __getitem__(self, key: str) -> Any:
        return self._state[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._state[key] = value

    def __delitem__(self, key: str) -> None:
        del self._state[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._state)

    def __len__(self) -> int:
        return len(self._state)

    def rerun(self) -> None:
        if self._rerun is None:
            raise RuntimeError("No Streamlit rerun callback is configured")
        self._rerun()

    def request_navigation(self, section: str) -> None:
        self["_next_app_section"] = section
        self.rerun()


def current_session() -> StreamlitSessionAdapter:
    """Return an adapter for the active Streamlit session."""
    return StreamlitSessionAdapter(st.session_state, st.rerun)


__all__ = ["StreamlitSessionAdapter", "current_session"]
