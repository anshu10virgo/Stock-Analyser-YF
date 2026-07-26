"""Regression tests for Streamlit navigation session state."""

import unittest

from streamlit.testing.v1 import AppTest

from models.optional_filter import PEG_RATIO
from services.data_source import SNAPSHOT_SOURCE


class AppSessionStateTests(unittest.TestCase):
    def test_market_data_source_survives_scan_page_reruns(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()

        app.radio[2].set_value(SNAPSHOT_SOURCE).run()
        app.radio[0].set_value("2. Strategy").run()
        app.number_input[0].set_value(55).run()

        self.assertEqual(
            app.session_state["selected_market_data_source"],
            SNAPSHOT_SOURCE,
        )
        self.assertEqual(len(app.exception), 0)

    def test_optional_filters_start_empty_and_survive_strategy_reruns(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()
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
