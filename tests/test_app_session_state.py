"""Regression tests for Streamlit navigation session state."""

import unittest

from streamlit.testing.v1 import AppTest

from services.data_source import SNAPSHOT_SOURCE


class AppSessionStateTests(unittest.TestCase):
    def test_market_data_source_survives_scan_page_reruns(self):
        app = AppTest.from_file("app.py", default_timeout=20).run()

        app.radio[2].set_value(SNAPSHOT_SOURCE).run()
        app.radio[0].set_value("2. Scan").run()
        app.number_input[0].set_value(100).run()

        self.assertEqual(
            app.session_state["selected_market_data_source"],
            SNAPSHOT_SOURCE,
        )
        self.assertIn("Git snapshot", app.info[0].value)
        self.assertEqual(len(app.exception), 0)


if __name__ == "__main__":
    unittest.main()
