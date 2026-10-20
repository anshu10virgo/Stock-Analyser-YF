"""Architecture and compatibility tests for packaged Streamlit presentation."""

from __future__ import annotations

import unittest

import ui.results_page as legacy_results
import ui.sidebar as legacy_strategy
from stock_analyser.presentation.streamlit.components import results
from stock_analyser.presentation.streamlit.components import strategy_configuration
from stock_analyser.presentation.streamlit.session_adapter import StreamlitSessionAdapter
from tests.support.paths import PROJECT_ROOT


PRESENTATION_ROOT = (
    PROJECT_ROOT
    / "src"
    / "stock_analyser"
    / "presentation"
    / "streamlit"
)


class StreamlitPresentationTests(unittest.TestCase):
    def test_session_adapter_wraps_state_and_navigation(self):
        state = {}
        reruns = []
        session = StreamlitSessionAdapter(state, lambda: reruns.append(True))

        session["selected_symbols"] = ["A.NS"]
        session.request_navigation("2. Strategy")

        self.assertEqual(state["selected_symbols"], ["A.NS"])
        self.assertEqual(state["_next_app_section"], "2. Strategy")
        self.assertEqual(reruns, [True])

    def test_root_ui_modules_alias_canonical_components(self):
        self.assertIs(legacy_results, results)
        self.assertIs(legacy_strategy, strategy_configuration)

    def test_only_session_adapter_accesses_raw_streamlit_session_state(self):
        offenders = []
        for path in PRESENTATION_ROOT.rglob("*.py"):
            if path.name == "session_adapter.py":
                continue
            if "st.session_state" in path.read_text(encoding="utf-8"):
                offenders.append(path.relative_to(PRESENTATION_ROOT).as_posix())
        self.assertEqual(offenders, [])

    def test_presentation_does_not_import_concrete_providers(self):
        forbidden = (
            "stock_analyser.infrastructure",
            "from providers",
            "import providers",
            "import yfinance",
            "import boto3",
            "import smtplib",
        )
        offenders = []
        for path in PRESENTATION_ROOT.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            if any(value in source for value in forbidden):
                offenders.append(path.relative_to(PRESENTATION_ROOT).as_posix())
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
