"""Tests for Ticksy provider configuration and local-only request construction."""

import unittest
from unittest.mock import Mock, patch

import pandas as pd

from models.assistant import AssistantMessage, AssistantRequest
from services.assistant_context import build_local_context
from services.assistant_actions import apply_action, propose_action
from services.assistant_explanations import explain_stock_prompt
from services.assistant_provider import DisabledProvider, GeminiProvider, OpenAIProvider, build_provider, load_assistant_settings
from services.assistant_responses import local_response
from services.assistant_tools import crossover_window, market_condition_summary, scan_summary, stock_status


class AssistantProviderTests(unittest.TestCase):
    def test_uses_gemini_flash_without_a_configured_provider(self):
        settings = load_assistant_settings({})

        self.assertEqual(settings.provider, "gemini")
        self.assertEqual(settings.model, "gemini-3.7-flash")
        self.assertIsInstance(build_provider(settings), DisabledProvider)

    def test_uses_configured_openai_provider_when_a_key_is_available(self):
        settings = load_assistant_settings({"assistant": {"provider": "openai"}})

        self.assertEqual(settings.model, "gpt-5.6-terra")
        self.assertIsInstance(build_provider(settings), DisabledProvider)
        configured = load_assistant_settings({"assistant": {"provider": "openai"}, "OPENAI_API_KEY": "key"})
        self.assertIsInstance(build_provider(configured), OpenAIProvider)

    @patch("services.assistant_provider.requests.post")
    def test_gemini_request_does_not_enable_external_tools(self, post):
        response = Mock()
        response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Local answer"}]}}]}
        post.return_value = response
        provider = GeminiProvider("key", "gemini-3.7-flash")

        answer = provider.respond(AssistantRequest((AssistantMessage("user", "Explain TCS"),), "LOCAL"))

        self.assertEqual(answer, "Local answer")
        self.assertNotIn("tools", post.call_args.kwargs["json"])
        self.assertIn("Do not browse", post.call_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"])
        self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "key")
        self.assertNotIn("params", post.call_args.kwargs)

    @patch("services.assistant_provider.requests.post")
    def test_openai_request_does_not_enable_external_tools(self, post):
        response = Mock()
        response.json.return_value = {"output_text": "Local answer"}
        post.return_value = response
        provider = OpenAIProvider("key", "gpt-5.6-terra")

        answer = provider.respond(AssistantRequest((AssistantMessage("user", "Explain TCS"),), "LOCAL"))

        self.assertEqual(answer, "Local answer")
        self.assertNotIn("tools", post.call_args.kwargs["json"])
        self.assertIn("Do not browse", post.call_args.kwargs["json"]["instructions"])

    def test_local_tools_return_stock_rule_values_without_network_access(self):
        state = {
            "scan_time": "2026-08-30",
            "scan_results": pd.DataFrame([{"symbol": "TCS.NS", "company_name": "Tata Consultancy Services", "short_ma_slope": 1.2}]),
            "scan_impending_results": pd.DataFrame(),
            "scan_failed_results": pd.DataFrame(),
        }

        self.assertEqual(scan_summary(state)["post_golden_cross_count"], 1)
        status = stock_status(state, "tcs")

        self.assertTrue(status["available"])
        self.assertEqual(status["status"], "Post Golden Cross")
        self.assertIn("TCS.NS", build_local_context(state, "tcs"))

    def test_backtest_action_requires_confirmation_before_state_changes(self):
        state = {"selected_symbols": ["TCS.NS"], "stock_count": 1}

        action = propose_action("Backtest TCS for 5Y", state)

        self.assertEqual(action.kind, "backtest")
        self.assertNotIn("ticksy_backtest_request", state)
        apply_action(action, state)
        self.assertEqual(state["ticksy_backtest_request"]["symbols"], ["TCS.NS"])
        self.assertEqual(state["_next_app_section"], "5. Backtester")

    def test_impending_explanation_uses_local_gap_and_slope_values(self):
        state = {
            "scan_settings": {"short_ma": 50, "long_ma": 200, "max_price_premium": 10, "impending_max_gap_pct": 10},
            "scan_impending_results": pd.DataFrame([{"symbol": "TCS.NS", "company_name": "Tata Consultancy Services", "ma_short": 99.0, "ma_long": 100.0, "short_ma_slope": 0.4, "long_ma_slope": 0.1, "long_ma_decline_percent": 12.0, "long_ma_decline_duration": 70, "price_above_long_ma_percent": 2.0, "impending_gap_percent": 1.0}]),
        }

        explanation = explain_stock_prompt(state, "Why is TCS impending?")

        self.assertIn("Impending Golden Cross", explanation)
        self.assertIn("1.00%", explanation)
        self.assertIn("not a confirmed Golden Cross", explanation)

    def test_crossover_window_requires_positive_local_convergence(self):
        state = {
            "scan_impending_results": pd.DataFrame([
                {"symbol": "TCS.NS", "ma_short": 99.0, "ma_long": 100.0, "short_ma_slope": 0.4, "long_ma_slope": 0.1}
            ])
        }

        estimate = crossover_window(state, "TCS.NS")

        self.assertTrue(estimate["available"])
        self.assertEqual(estimate["estimated_sessions"], 4)
        response = local_response(state, "When might TCS cross?")
        self.assertIn("illustrative", response)
        self.assertIn("not a prediction", response)

    def test_local_market_summary_uses_current_scan_only(self):
        state = {
            "scan_time": "2026-08-30",
            "scan_results": pd.DataFrame([
                {"symbol": "TCS.NS", "days_since_cross": 10, "price_above_long_ma_percent": 2.0}
            ]),
            "scan_impending_results": pd.DataFrame([
                {"symbol": "INFY.NS", "price_above_long_ma_percent": 1.0}
            ]),
            "scan_failed_results": pd.DataFrame([{"symbol": "RELIANCE.NS"}]),
        }

        summary = market_condition_summary(state)

        self.assertEqual(summary["recent_cross_count"], 1)
        self.assertEqual(summary["above_long_ma_count"], 2)
        self.assertIn("Post Golden Cross: 1", local_response(state, "Summarise the current market setup."))

    def test_parameter_trace_and_comparison_use_local_result_values(self):
        state = {
            "scan_results": pd.DataFrame([
                {"symbol": "TCS.NS", "company_name": "TCS", "ma_short": 105.0, "ma_long": 100.0, "close": 103.0, "short_ma_slope": 1.0, "long_ma_slope": 0.2, "price_above_long_ma_percent": 3.0, "pe": 24.0, "industry": "Information Technology"},
                {"symbol": "INFY.NS", "company_name": "Infosys", "ma_short": 102.0, "ma_long": 100.0, "short_ma_slope": 0.6, "pe": 21.0, "industry": "Information Technology"},
            ]),
        }

        self.assertIn("P/E", local_response(state, "What is P/E for TCS?"))
        self.assertIn("Local calculation trace", local_response(state, "Show the calculation trace for TCS."))
        comparison = local_response(state, "Compare TCS and INFY")
        self.assertIn("TCS.NS", comparison)
        self.assertIn("INFY.NS", comparison)

    def test_strategy_filter_and_navigation_actions_require_confirmation(self):
        state = {"selected_symbols": ["TCS.NS"]}

        strategy = propose_action("Use cross age 60, include impending, and ROE above 18", state)
        navigation = propose_action("Open Results", state)

        self.assertEqual(strategy.kind, "strategy")
        self.assertEqual(strategy.settings["cross_age"], 60)
        self.assertTrue(strategy.settings["include_impending_crosses"])
        self.assertEqual(strategy.settings["optional_filters"][0]["key"], "return_on_equity")
        self.assertNotIn("_next_app_section", state)
        self.assertEqual(navigation.kind, "navigation")
        apply_action(navigation, state)
        self.assertEqual(state["_next_app_section"], "4. Results")


if __name__ == "__main__":
    unittest.main()
