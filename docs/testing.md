# Testing and Quality Gates

All automated tests are deterministic and run without live Yahoo Finance,
Screener, R2, SMTP, Gemini, or OpenAI access. Test fixtures and fake adapters
live in `tests/support`; production datasets remain outside Git.

## Test layout

```text
tests/
|-- domain/                     Pure rules and calculations
|-- application/                Commands, queries, workflows, and ports
|-- agents/                     Ticksy policies, tools, and orchestration
|-- infrastructure/             Offline adapter and storage contracts
|-- integration/
|   |-- presentation/           Streamlit AppTest smoke coverage
|   `-- test_*.py               Scanner, Backtester, report, job, and boundary tests
`-- support/                    Shared deterministic fixtures and fakes
```

## Local commands

Install development-only quality tools without adding them to the application
runtime dependencies:

```powershell
python -m pip install -r requirements-dev.txt
```

Run the same gates used in GitHub Actions:

```powershell
python -m ruff check src/stock_analyser tests scripts
python -m pytest tests/domain tests/application tests/agents
python -m pytest tests/infrastructure tests/integration/test_operational_jobs.py
python -m pytest tests/integration/test_scanner.py tests/integration/test_backtest_service.py tests/integration/test_scan_report.py
python -m pytest tests/integration/presentation
python -m pytest --cov=src/stock_analyser --cov-report=term-missing --cov-fail-under=70
```

The complete suite is:

```powershell
python -m pytest
```

## Full scanner parity

The 1,500-symbol parity check compares the application workflow with the
pre-refactor scanner using the same ranked symbols, configuration, and pinned
local snapshot. Download a complete snapshot first, then run:

```powershell
python scripts/cloud_snapshots.py download
python scripts/compare_scan_refactor.py --stock-count 1500
```

This is a deliberate release regression rather than a normal CI test because
the production snapshot and R2 credentials are intentionally absent from pull
request checkouts. Run it whenever scanner rules, fundamentals, market-data
composition, or provider composition could affect scan output.

## Hosted Streamlit smoke test

After a release that changes presentation, composition, dependencies, or data
access, verify the hosted application against its read-only R2 configuration:

1. Confirm Setup loads, reports the expected market and snapshot date, and can
   continue to Strategy.
2. Confirm strategy defaults and optional-filter state survive navigation.
3. Run a small snapshot-backed scan and confirm progress reaches Results.
4. Confirm Post-Cross and Impending results, rejection summaries, stock detail,
   maximum-period price/MA chart zoom, and historical P/E/TTM EPS chart render.
5. Open Backtester and Ticksy; verify each loads without exposing secrets or
   making an unapproved external-data request.
6. If report code changed, send a test report to an approved address and verify
   workbook sheets and chart attachments.

Record the deployed commit, snapshot identity, scan configuration, browser,
and outcome in the pull request or release notes. Never place credentials or
recipient addresses in the record.
