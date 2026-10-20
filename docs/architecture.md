# Architecture

Stock Analyser is a production-oriented layered application. All maintained
Python code lives in the installable `src/stock_analyser` package. The root
`app.py` is only the Streamlit Cloud bootstrap. Production and manual operator
commands are packaged under `jobs/`; manual regression tools live under
`tests/manual/`. There is no root `scripts/` implementation boundary.

```text
Streamlit presentation and packaged jobs
                 |
Application commands, queries, and workflows
                 |
Provider-independent domain rules
                 |
Application ports
                 |
Yahoo, Screener, local/R2, SMTP, Gemini, and OpenAI adapters
```

## Package Structure

```text
app.py                              Thin Streamlit Cloud entrypoint
src/stock_analyser/
    domain/
        scanning/                   Indicators, strategy rules, outcomes, scoring
        backtesting/                Historical replay, horizons, and returns
        fundamentals/               Provider-independent financial calculations
        reporting/                  Report data and message specifications
        markets/                    Market identity and dataset conventions
    application/
        commands/                   Run scan/backtest, update strategy, send report
        queries/                    Status, summaries, failures, traces, data health
        workflows/                  Scan, backtest, and refresh orchestration
        ports/                      Market, fundamentals, storage, mail, model contracts
        scanning.py                 Provider-aware scan application service
        backtesting_service.py      Provider-aware backtest application service
    agents/                         Ticksy orchestration, policy, audit, and tools
    infrastructure/
        yahoo/                      Yahoo Finance adapters
        screener/                   Screener adapter and durable checkpoints
        r2/                         Snapshot storage, publication, lease, and retention
        local/                      Local data and stock-universe access
        reporting/                  XLSX/chart/email rendering
        smtp/                       Authenticated mail transport
        openai/                     OpenAI model adapter
        gemini/                     Gemini model adapter
        data_services.py            Runtime provider composition
        model_factory.py            Hosted-model composition
    presentation/streamlit/
        pages/                      Setup, Strategy, Live Scan, Results, Backtester
        components/                 Theme, controls, insights, charts, reports, Ticksy
        session_adapter.py          Streamlit session-state boundary
        app.py                      Streamlit composition root
    jobs/
        market_refresh.py           R2 staging, validation, and atomic publication
        _market_snapshot_refresh.py Market-data dataset builder
        screener_refresh.py         Resumable Screener dataset builder
        storage_housekeeping.py     Plan-first storage retention
        refresh_alert.py            Refresh-failure email
        stock_universe_refresh.py   Validated NSE universe rebuild
        maintenance/                Snapshot administration commands
        migrations/                 One-time migration/recovery commands
        diagnostics/                Operator diagnostic exports
tests/
    domain/
    application/
    agents/
    infrastructure/
    integration/
    manual/
        regression/                 Release parity and cloud-result verification
        smoke/                      Explicit live-provider smoke commands
    support/
```

The former root packages `agents/`, `application/`, `core/`, `domain/`,
`models/`, `providers/`, `services/`, `ui/`, and the source-checkout package
shim are retired. They must not be restored as alternate implementation or
compatibility locations.

## Dependency Rules

- Domain code is deterministic and imports no application, presentation, or
  concrete infrastructure modules.
- Application code coordinates domain behavior through ports. It imports no
  Streamlit or concrete provider implementation.
- Infrastructure implements ports and owns all external I/O.
- Presentation translates user/session state into application commands and
  queries. It contains no scan, score, backtest, or financial formula.
- Jobs are composition entrypoints. Scheduled jobs use application workflows
  and infrastructure adapters, then publish only validated output.
- Tests enforce these dependency directions through AST import checks.

## Scanning and Backtesting

`application/scanning.py` coordinates injected providers and the pure modules
under `domain/scanning`. Every symbol ends as a typed Post-Cross result,
Impending-Cross result, or structured failure. Mandatory rules run before the
user-selected optional fundamental filters. Scoring remains deterministic and
belongs to the domain.

`application/backtesting_service.py` coordinates historical data access while
`domain/backtesting` owns signal qualification, point-in-time valuation,
forward-return calculations, and summaries.

The 1,500-symbol parity command in
`tests/manual/regression/compare_scan_refactor.py` compares
qualification, rejection reasons, and scores against the preserved baseline
using the same immutable snapshot and configuration.

## Data and External Systems

`infrastructure/data_services.py` is the market-data composition boundary. It
constructs a consistent live-Yahoo or pinned local/cloud-snapshot provider
bundle. A scan session stays pinned to one snapshot so tables, charts,
backtests, and reports cannot silently mix data generations.

Yahoo, Screener, R2/S3, SMTP, OpenAI, and Gemini behavior is isolated under
`infrastructure/`. Credentials come only from Streamlit Secrets, GitHub
Actions Secrets, or local environment variables and are never written to
datasets, audit records, or Git.

R2 publication is content-addressed and atomic. Dataset builders write to an
isolated staging directory, validate manifests and file hashes, upload
immutable objects, verify the candidate remotely, and only then replace the
active pointer. Leases prevent publication and retention from racing.

## Ticksy Boundary

Ticksy is an orchestration layer, not a second calculation engine. It receives
an allow-listed copy of the current application context and can call only
registered deterministic application queries or confirmation-gated commands.
Tools do not receive raw Streamlit state, secrets, provider clients, browser
access, news, RAG, or external market-data retrieval.

Each tool declares its effect and minimum approval. The registry validates
arguments and policy before execution, limits hosted-provider tool calls, and
records sanitized session-scoped audit events. Python domain/application code
remains the source of truth for calculations.

## Presentation and Reporting

`presentation/streamlit/app.py` is the UI composition root. Page controllers
use `session_adapter.py` for session state and application commands/queries for
behavior. Root `app.py` adds `src` for a source checkout, imports that packaged
entrypoint, and calls `run()`.

Reporting domain modules build provider-independent workbook frames, chart
specifications, attachment batches, and message content. Infrastructure
renders XLSX/PNG/ZIP/email artifacts and sends them through the SMTP port.
Recipients and named strategy presets remain session-only.

## Operational Entrypoints

GitHub Actions installs the package and calls:

```powershell
python -m stock_analyser.jobs.market_refresh
python -m stock_analyser.jobs.screener_refresh
python -m stock_analyser.jobs.storage_housekeeping
python -m stock_analyser.jobs.refresh_alert
python -m stock_analyser.jobs.stock_universe_refresh
python -m stock_analyser.jobs.maintenance.cloud_snapshots
python -m stock_analyser.jobs.migrations.git_data_archive
python -m stock_analyser.jobs.diagnostics.export_scan_failure_report
```

`market_refresh` invokes the packaged dataset builders as modules; it does not
depend on deleted root launchers. Manual parity, cloud-result verification,
and live-provider smoke commands remain under `tests/manual/` and are never
collected as normal offline tests.

## Reliability Gates

- Every scanned symbol has a terminal typed outcome.
- No snapshot becomes visible before complete validation.
- Normal scans and stock-detail charts never scrape Screener live.
- Optional-filter missing data retains the stock and records not-evaluated
  status; it does not create another result group.
- CI runs lint/import boundaries, domain/application/agent tests,
  infrastructure contracts, scanner regression, Streamlit smoke tests, and
  branch-aware package coverage.
- Releases that can affect scanning, fundamentals, provider composition, or
  market data also run the immutable 1,500-symbol parity gate.
