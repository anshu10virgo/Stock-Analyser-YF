"""Tests for Ticksy's bounded context and controlled tool runtime."""

from __future__ import annotations

import unittest
from json import loads

import pandas as pd

from stock_analyser.agents.audit_log import InMemoryAuditLog, sanitized_arguments
from stock_analyser.agents.contracts import (
    ApprovalLevel,
    ToolCall,
    ToolDefinition,
    ToolEffect,
    ToolStatus,
)
from stock_analyser.agents.execution_context import (
    ExecutionContext,
    build_local_context,
)
from stock_analyser.agents.orchestrator import AssistantRuntime
from stock_analyser.agents.tool_registry import ToolRegistry
from stock_analyser.agents.tools import build_local_tool_registry
from stock_analyser.application.context import ApplicationContext


class AgenticFoundationTests(unittest.TestCase):
    def setUp(self):
        self.state = {
            "scan_time": "2026-10-18T12:00:00",
            "scan_results": pd.DataFrame(
                [
                    {
                        "symbol": "TCS.NS",
                        "company_name": "Tata Consultancy Services",
                        "close": 100.0,
                        "ma_short": 98.0,
                        "ma_long": 95.0,
                    }
                ]
            ),
            "scan_impending_results": pd.DataFrame(),
            "scan_failed_results": pd.DataFrame(
                [
                    {
                        "symbol": "FAIL.NS",
                        "stage": "Price Validation",
                        "reason": "Close price is too far above Long MA",
                    }
                ]
            ),
            "scan_settings": {
                "short_ma": 50,
                "market_data_snapshot": {"snapshot_id": "snapshot-123"},
            },
            "scan_metrics": {"timing": {"total_seconds": 2.5}},
            "selected_symbols": ["TCS.NS", "FAIL.NS"],
            "GEMINI_API_KEY": "must-never-enter-context",
            "ticksy_pending_action": object(),
        }

    def test_context_copies_only_allow_listed_application_state(self):
        application_context = ApplicationContext.from_session_state(self.state)
        context = ExecutionContext.from_application_context(application_context)

        self.assertEqual(context.snapshot_identity, "snapshot-123")
        self.assertNotIn("GEMINI_API_KEY", context.as_mapping())
        self.assertNotIn("ticksy_pending_action", context.as_mapping())
        context.get("scan_results").loc[0, "symbol"] = "CHANGED.NS"
        self.assertEqual(self.state["scan_results"].loc[0, "symbol"], "TCS.NS")

    def test_provider_context_is_built_from_the_bounded_snapshot(self):
        content = build_local_context(self.state, "TCS")

        self.assertIn("TCS.NS", content)
        self.assertNotIn("must-never-enter-context", content)

    def test_registered_read_only_tool_returns_structured_result_and_audit(self):
        registry = build_local_tool_registry()
        context = ExecutionContext.from_application_state(self.state)

        result = registry.execute(
            ToolCall("get_stock_status", {"symbol": "TCS"}),
            context,
        )

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertTrue(result.data["available"])
        self.assertEqual(result.data["status"], "Post Golden Cross")
        event = registry.audit_log.events()[0]
        self.assertEqual(event.snapshot_identity, "snapshot-123")
        self.assertEqual(event.status, ToolStatus.SUCCESS)

    def test_rejection_tool_uses_readable_shared_labels(self):
        registry = build_local_tool_registry()

        result = registry.execute(
            ToolCall("get_rejection_summary", {"limit": 3}),
            ExecutionContext.from_application_state(self.state),
        )

        self.assertEqual(result.status, ToolStatus.SUCCESS)
        self.assertEqual(
            result.data["reasons"][0],
            {
                "reason": "Current price is too far above Long MA",
                "count": 1,
            },
        )

    def test_registry_rejects_invalid_arguments_without_calling_handler(self):
        registry = build_local_tool_registry()
        result = registry.execute(
            ToolCall("get_stock_status", {"unexpected": "TCS"}),
            ExecutionContext.from_application_state(self.state),
        )

        self.assertEqual(result.status, ToolStatus.ERROR)
        self.assertIn("Unexpected argument", result.error)

    def test_mutating_tool_requires_confirmation(self):
        calls = []
        registry = ToolRegistry(InMemoryAuditLog())
        registry.register(
            ToolDefinition(
                "update_strategy",
                "Test-only state-changing tool.",
                ToolEffect.SESSION_MUTATION,
                ApprovalLevel.USER_CONFIRMATION,
            ),
            lambda _context, _arguments: calls.append("executed"),
        )
        context = ExecutionContext.from_application_state(self.state)
        call = ToolCall("update_strategy")

        pending = registry.execute(call, context)
        executed = registry.execute(call, context, approved=True)

        self.assertEqual(pending.status, ToolStatus.APPROVAL_REQUIRED)
        self.assertEqual(executed.status, ToolStatus.SUCCESS)
        self.assertEqual(calls, ["executed"])

    def test_registry_rejects_a_weakened_external_side_effect_policy(self):
        registry = ToolRegistry()

        with self.assertRaisesRegex(ValueError, "require at least"):
            registry.register(
                ToolDefinition(
                    "send_email",
                    "Unsafe test definition.",
                    ToolEffect.EXTERNAL_SIDE_EFFECT,
                    ApprovalLevel.NONE,
                ),
                lambda _context, _arguments: None,
            )

    def test_audit_redacts_credential_like_arguments(self):
        redacted = sanitized_arguments(
            {
                "symbol": "TCS.NS",
                "api_key": "secret-value",
                "refresh_token": "secret-token",
                "options": {"smtp_password": "nested-secret"},
            }
        )

        self.assertEqual(redacted["symbol"], "TCS.NS")
        self.assertEqual(redacted["api_key"], "[REDACTED]")
        self.assertEqual(redacted["refresh_token"], "[REDACTED]")
        self.assertEqual(redacted["options"]["smtp_password"], "[REDACTED]")

    def test_runtime_exposes_the_initial_read_only_tool_catalogue(self):
        runtime = AssistantRuntime()
        definitions = runtime.registry.definitions()

        self.assertEqual(
            tuple(definition.name for definition in definitions),
            (
                "get_scan_summary",
                "get_stock_status",
                "get_market_condition",
                "get_backtest_results",
                "get_calculation_trace",
                "get_data_health",
                "get_rejection_summary",
            ),
        )
        self.assertTrue(
            all(definition.effect == ToolEffect.READ_ONLY for definition in definitions)
        )
        self.assertTrue(
            all(
                definition.approval == ApprovalLevel.NONE
                for definition in definitions
            )
        )

    def test_runtime_executes_selected_tools_and_grounds_the_final_request(self):
        class Provider:
            def __init__(self):
                self.final_request = None

            def select_tools(self, request, tools):
                return (ToolCall("get_stock_status", {"symbol": "TCS"}),)

            def respond(self, request):
                self.final_request = request
                return "TCS qualified using the stored scan result."

        provider = Provider()
        answer = AssistantRuntime().answer(
            provider,
            self.state,
            (),
            "TCS",
        )

        grounded = loads(provider.final_request.local_context)
        self.assertEqual(answer.tools, ("get_stock_status",))
        self.assertTrue(grounded["tool_results"][0]["data"]["available"])
        self.assertIn("snapshot-123", answer.render())

    def test_runtime_returns_not_available_without_asking_model_to_guess(self):
        class Provider:
            def select_tools(self, request, tools):
                return (ToolCall("get_stock_status", {"symbol": "UNKNOWN"}),)

            def respond(self, request):
                raise AssertionError("Provider must not invent unavailable data")

        answer = AssistantRuntime().answer(Provider(), self.state, (), "UNKNOWN")

        self.assertIn("not available", answer.text)

    def test_runtime_limits_provider_selected_tool_calls(self):
        class Provider:
            def select_tools(self, request, tools):
                return tuple(ToolCall("get_scan_summary") for _ in range(5))

            def respond(self, request):
                return "Grounded summary"

        runtime = AssistantRuntime(max_tool_calls=3)
        answer = runtime.answer(Provider(), self.state, ())

        self.assertEqual(len(answer.tools), 3)
        self.assertEqual(len(runtime.registry.audit_log.events()), 3)


if __name__ == "__main__":
    unittest.main()
