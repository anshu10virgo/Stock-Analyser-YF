"""Executable dependency and compatibility boundaries for the target package."""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

from tests.support.paths import PROJECT_ROOT


PACKAGE_ROOT = PROJECT_ROOT / "src" / "stock_analyser"


def _imports_below(root: Path) -> list[tuple[Path, str]]:
    imports: list[tuple[Path, str]] = []
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend((path, alias.name) for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append((path, node.module))
    return imports


def _assert_no_imports(root: Path, forbidden: tuple[str, ...]) -> None:
    violations = [
        f"{path.relative_to(PROJECT_ROOT)} -> {module}"
        for path, module in _imports_below(root)
        if any(module == name or module.startswith(f"{name}.") for name in forbidden)
    ]
    assert not violations, "Forbidden dependency imports:\n" + "\n".join(violations)


def test_domain_is_independent_of_frameworks_and_external_adapters():
    _assert_no_imports(
        PACKAGE_ROOT / "domain",
        (
            "streamlit",
            "stock_analyser.application",
            "stock_analyser.infrastructure",
            "stock_analyser.presentation",
            "boto3",
            "requests",
            "smtplib",
            "yfinance",
        ),
    )


def test_application_does_not_depend_on_presentation_or_concrete_adapters():
    _assert_no_imports(
        PACKAGE_ROOT / "application",
        (
            "streamlit",
            "stock_analyser.infrastructure",
            "stock_analyser.presentation",
            "ui",
            "boto3",
            "requests",
            "smtplib",
            "yfinance",
        ),
    )


def test_agent_runtime_does_not_depend_on_streamlit_or_infrastructure():
    _assert_no_imports(
        PACKAGE_ROOT / "agents",
        (
            "streamlit",
            "stock_analyser.infrastructure",
            "stock_analyser.presentation",
            "ui",
        ),
    )


def test_test_modules_only_share_helpers_through_tests_support():
    violations = []
    for path, module in _imports_below(PROJECT_ROOT / "tests"):
        if module.startswith("tests.") and not module.startswith("tests.support"):
            violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {module}")
    assert not violations, "Cross-test imports must move to tests.support:\n" + "\n".join(violations)


def test_compatibility_exports_resolve_to_canonical_implementations():
    exports = {
        ("models.scan_config", "ScanConfig"): (
            "stock_analyser.domain.scanning.models",
            "ScanConfig",
        ),
        ("providers.yahoo_finance", "YahooFinanceHistoryProvider"): (
            "stock_analyser.infrastructure.yahoo.providers",
            "YahooFinanceHistoryProvider",
        ),
        ("application.assistant_runtime", "AssistantRuntime"): (
            "stock_analyser.agents.orchestrator",
            "AssistantRuntime",
        ),
        ("agents.registry", "ToolRegistry"): (
            "stock_analyser.agents.tool_registry",
            "ToolRegistry",
        ),
    }
    for legacy, canonical in exports.items():
        legacy_value = getattr(importlib.import_module(legacy[0]), legacy[1])
        canonical_value = getattr(importlib.import_module(canonical[0]), canonical[1])
        assert legacy_value is canonical_value


def test_root_entrypoint_remains_a_thin_streamlit_bootstrap():
    source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    assert len(source.splitlines()) <= 20
    assert len(calls) == 2
    assert "from stock_analyser.presentation.streamlit import app" in source
    assert not any(
        token in source
        for token in ("services.", "providers.", "yfinance", "boto3", "smtplib")
    )
