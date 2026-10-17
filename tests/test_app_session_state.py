"""Regression tests for Streamlit navigation session state."""

import unittest
from pathlib import Path
from unittest.mock import patch
from tempfile import TemporaryDirectory

from streamlit.testing.v1 import AppTest

from models.optional_filter import PEG_RATIO
from services.data_source import SNAPSHOT_SOURCE
from services.snapshot_storage import LocalSnapshotStorage
from tests.snapshot_fixtures import create_fixture


class AppSessionStateTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.fixture_root = Path(temporary.name)
        create_fixture(self.fixture_root)
        self.storage = LocalSnapshotStorage(self.fixture_root)
        for name in ("services.storage_config.application_snapshot_storage",
                     "services.data_source.application_snapshot_storage"):
            patched = patch(name, return_value=self.storage)
            patched.start()
            self.addCleanup(patched.stop)

    def test_cloud_strategy_summary_labels_the_configured_storage(self):
        storage = self.storage
        storage.cloud = True
        storage.snapshot_id = "test-snapshot"
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20)
        app.secrets["storage"] = {"provider": "r2"}
        app.secrets["GEMINI_API_KEY"] = ""
        app.secrets["OPENAI_API_KEY"] = ""
        with patch("services.storage_config.application_snapshot_storage", return_value=storage), \
             patch("services.data_source.application_snapshot_storage", return_value=storage):
            app.run()
            app.radio[0].set_value("2. Strategy").run()
        self.assertEqual(len(app.exception), 0)
        source = next(metric for metric in app.metric if metric.label == "Data source")
        self.assertEqual(source.value, "Cloud snapshot")

    def _run_local_app(self):
        """Keep UI regressions independent of real cloud/model credentials."""
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=20)
        app.secrets["storage"] = {"provider": "local"}
        app.secrets["GEMINI_API_KEY"] = ""
        app.secrets["OPENAI_API_KEY"] = ""
        return app.run()

    def test_market_data_source_survives_scan_page_reruns(self):
        app = self._run_local_app()

        app.radio[2].set_value(SNAPSHOT_SOURCE).run()
        app.radio[0].set_value("2. Strategy").run()
        app.number_input[0].set_value(55).run()

        self.assertEqual(
            app.session_state["selected_market_data_source"],
            SNAPSHOT_SOURCE,
        )
        self.assertEqual(len(app.exception), 0)

    def test_optional_filters_start_empty_and_survive_strategy_reruns(self):
        app = self._run_local_app()
        app.button[0].click().run()

        self.assertEqual(app.session_state["scan_config_optional_sequence"], [])
        self.assertNotIn(
            "Require at least 10 trading sessions after the Golden Cross",
            [checkbox.label for checkbox in app.checkbox],
        )

        picker = next(
            widget
            for widget in app.selectbox
            if widget.label == "Choose an optional filter"
        )
        picker.set_value(PEG_RATIO)
        add_button = next(
            button for button in app.button if button.label.endswith("Add filter")
        )
        add_button.click().run()

        self.assertEqual(
            app.session_state["scan_config_optional_sequence"],
            [PEG_RATIO],
        )
        self.assertIn("Maximum PEG Ratio", [slider.label for slider in app.slider])

        app.number_input[0].set_value(55).run()
        self.assertEqual(
            app.session_state["scan_config_optional_sequence"],
            [PEG_RATIO],
        )
        self.assertEqual(len(app.exception), 0)

        next(
            field
            for field in app.text_input
            if field.label == "Save current settings as"
        ).set_value("PEG strategy").run()
        next(
            button for button in app.button if button.label == "Save as new"
        ).click().run()

        saved = app.session_state["user_scan_presets"]["PEG strategy"]
        self.assertEqual(saved["optional_filters"][0]["key"], PEG_RATIO)

        next(
            button for button in app.button if button.label == "− Remove"
        ).click().run()
        self.assertEqual(app.session_state["scan_config_optional_sequence"], [])


if __name__ == "__main__":
    unittest.main()
