"""Regression tests for Streamlit navigation session state."""

import unittest

from streamlit.testing.v1 import AppTest

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


if __name__ == "__main__":
    unittest.main()
