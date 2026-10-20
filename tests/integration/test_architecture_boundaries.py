"""Executable dependency and compatibility boundaries for the target package."""

from __future__ import annotations

import ast
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


def test_retired_root_compatibility_packages_do_not_return():
    retired = ("agents", "application", "core", "domain", "models", "providers", "services", "ui")
    present = [name for name in retired if (PROJECT_ROOT / name).exists()]
    assert not present, f"Retired root compatibility paths returned: {present}"


def test_root_entrypoint_remains_a_thin_streamlit_bootstrap():
    source = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 25
    assert "from stock_analyser.presentation.streamlit import app" in source
    assert not any(
        token in source
        for token in ("services.", "providers.", "yfinance", "boto3", "smtplib")
    )
