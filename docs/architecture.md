# Architecture

Stock Analyser YF is organized as a production-oriented layered application.

```text
Streamlit UI
    ↓
Scan Application Service
    ↓
Scanner Rules and Scoring
    ↓
Market Data and Fundamentals Providers
    ↓
Yahoo Finance, Cache, and Observability
```

## Current Components

- `ui/`: Streamlit pages, formatted results, and interactive charts.
- `models/scan_config.py`: immutable scan configuration and validation.
- `models/scan_run.py`: typed qualified and failed outcomes with dataframe
  adapters for the UI.
- `services/scan_service.py`: scan orchestration with injected provider
  dependencies and structured failures.
- `providers/yahoo_finance.py`: retrying, TTL-cached Yahoo price batches with
  observable request, cache, retry, and failure counters.
- `core/data_loader.py`: symbol-universe loading and batch price retrieval.
- `core/scanner.py`: compatibility facade for legacy callers.
- Technical-analysis modules: indicators, Golden Cross, targeted pre-cross
  trough validation, and long-MA slope-transition validation.
- `core/fundamentals.py`: retried and cached fundamental-data retrieval.
- `models/`: typed scan and failure-result contracts.

## Target Reliability Boundaries

- The UI must not contain market-data or scanner business logic.
- Every external request must have an observable success or failure outcome.
- Every scanned symbol must finish as either a qualified result or a structured
  failure result.
- Caches are an optimization only; results must identify their scan time and
  selected settings.
