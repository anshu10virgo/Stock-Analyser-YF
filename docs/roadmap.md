# Roadmap

Reviewed against the current implementation on October 19, 2026. Remaining work
is proposed; release dates are not committed. Operational instructions live in
the [deployment and storage guide](deployment.md).

## Recommended next work

1. Verify a scheduled changed-data R2 publication and finish hosted smoke checks.
2. Improve failed-stock exploration and surface existing scan diagnostics.
3. Add persistent strategy profiles and completed scan history. These provide
   the stored comparisons needed for Ticksy daily-change explanations.
4. Migrate Streamlit presentation modules and operational jobs into the
   installable package while preserving deployed entrypoints.
5. Choose advanced Backtesting or US expansion as the next major feature.

## Completed — Package Foundation and Scanning Domain Extraction

### Goal

Introduce the installable package boundary and extract deterministic scanning
rules without changing the application interface, calculations, defaults, or
runtime providers.

### Scope

- Create `src/stock_analyser` with domain, application, agents,
  infrastructure, presentation, and jobs package boundaries.
- Add `pyproject.toml` and retain a thin root Streamlit Cloud entrypoint.
- Make `stock_analyser.domain.scanning` the canonical home for scan models,
  indicators, Post-Cross rules, Impending rules, reversal rules, optional
  rules, and scoring.
- Keep `ScanService` as the temporary provider-aware orchestration facade.
- Preserve legacy import paths through explicit compatibility modules.
- Keep existing scripts aligned and add a repeatable 1,500-symbol before/after
  parity check using the same local immutable snapshot.

### Deliberately Deferred

- Application commands, queries, workflows, and port implementations.
- Moving Yahoo, Screener, R2, SMTP, Gemini, or OpenAI adapters.
- Moving the remaining Streamlit pages or operational jobs.
- Any UI, strategy, scoring, default, or financial-formula change.

### Acceptance Criteria

- The package installs from `pyproject.toml` and root `app.py` remains a thin
  Streamlit bootstrap.
- Existing jobs and tests continue to resolve their current import paths.
- Domain scanning modules have no Streamlit, Yahoo, R2, SMTP, or email imports.
- The same top 1,500 ranked symbols and configuration produce identical Post-
  Cross, Impending, failure, and scoring outputs before and after extraction.
- Focused tests, the full suite, and `git diff --check` pass.

## Completed — Application Commands, Queries, Workflows, and Ports

### Goal

Make UI and agent entrypoints depend on explicit use cases rather than directly
constructing scanner services or calling helper modules, without changing any
calculation, qualification, score, or visible workflow.

### Scope

- Add scan, Backtest, strategy-update, and report-delivery commands.
- Add scan-summary, stock-status, failure-explanation, calculation-trace, and
  data-health queries over bounded local application state.
- Add scan, Backtest, and refresh workflow boundaries.
- Define provider contracts for market data, fundamentals, storage, mail, and
  hosted-model access.
- Route Streamlit scan/Backtest execution and Ticksy's registered tools through
  the application layer.
- Preserve existing services and imports as temporary compatibility paths.

### Deliberately Deferred

- Moving Yahoo, Screener, R2, SMTP, Gemini, and OpenAI implementations into
  `infrastructure/`.
- Moving remaining root agent modules, Streamlit components, and jobs.
- New agent capabilities or state-changing tools.
- Any UI, rule, score, default, or financial-formula change.

### Acceptance Criteria

- Streamlit does not construct `ScanService` or `BacktestService` directly.
- Registered Ticksy tools call application queries rather than service helpers.
- Strategy commands have no Streamlit dependency and retain confirmation.
- Existing outputs remain identical under focused, full-suite, and 1,500-stock
  parity regression checks.
- Operational verification scripts use the application workflows where they
  exercise normal scan and Backtest execution.

## Completed — Infrastructure Adapters, Phase 1

### Goal

Move Yahoo Finance, Screener.in, local/R2 snapshot storage, and SMTP transport
behind the application ports without changing UI behaviour, scan rules,
scores, defaults, or financial calculations.

### Scope

- Add canonical Yahoo history, fundamentals, classifications, market-cap, and
  industry-valuation adapters under `stock_analyser.infrastructure.yahoo`.
- Add the canonical bounded-retry Screener provider under
  `stock_analyser.infrastructure.screener`.
- Add local, R2/S3, scoped snapshot, and repository-backed provider adapters
  under `stock_analyser.infrastructure.r2`.
- Add an authenticated SMTP implementation of `MailerPort` and use it for
  scan reports and scheduled-refresh failure alerts.
- Type the provider bundle against the application ports and inject concrete
  adapter instances from one infrastructure composition factory.
- Keep existing `providers/`, `core/`, and `services/` import paths as explicit
  compatibility exports while callers migrate.
- Point operational scripts directly at canonical infrastructure adapters.

### Deliberately Deferred

- Gemini and OpenAI adapter migration, which requires a separate Ticksy
  provider regression slice.
- Moving remaining Streamlit modules and scheduled-job entrypoints into
  `presentation/` and `jobs/`.
- Removing compatibility facades before all callers have migrated.
- Any UI, scan-rule, scoring, default, or financial-formula change.

### Acceptance Criteria

- Concrete market-data, fundamentals, storage, and SMTP adapters satisfy their
  runtime-checkable application port contracts.
- Existing imports resolve to the canonical adapter classes.
- Scripts use canonical Yahoo, Screener, R2, and SMTP paths.
- Focused infrastructure tests, the full suite, scanner parity, and
  `git diff --check` pass.

## Completed — Ticksy Read-Only Tool Integration

### Goal

Let Ticksy select and execute approved local read-only tools while keeping all
answers grounded in deterministic application data and preserving existing
confirmation boundaries.

### Scope

- Publish only registered local function declarations to Gemini or OpenAI;
  browser, search, news, RAG, and provider-hosted tools remain unavailable.
- Allow no more than three local tool calls for one user request.
- Validate every provider-generated function name and argument through the
  central registry before execution.
- Feed successful structured tool results into the final response context.
- Return a deterministic unavailable-data answer instead of asking the model
  to fill missing stock or Backtester information.
- Show compact scan time, snapshot identity, and tool names beneath grounded
  Ticksy responses.
- Keep each tool runtime and its sanitized audit records isolated to the
  active Streamlit session.
- Add readable rejection summaries shared by the Results UI and Ticksy.

### Deliberately Deferred

- Agent-triggered scans, Backtests, strategy changes, email, refresh, Git, or
  deployment through the registry.
- Multi-step planning, durable assistant memory, and cross-snapshot analysis.
- Any change to financial formulas, rules, scoring, or data providers.

### Acceptance Criteria

- Provider payloads expose only the allow-listed local function catalogue.
- Unknown tools and invalid arguments cannot reach Python handlers.
- Unavailable local data never becomes a model-generated value.
- Existing confirmed actions retain their current user-confirmation flow.
- Focused provider, registry, runtime, and UI-state tests pass.

## Completed — Agentic Foundation and Code Revamp

### Goal

Introduce a safe application boundary for future agents without changing scan
qualification, scoring, Backtester outputs, refresh jobs, or the current
Ticksy user experience.

### Scope

- Add an allow-listed `ApplicationContext` so assistant code receives copied,
  explicit application state instead of unrestricted Streamlit session state.
- Add typed tool definitions, calls, results, effects, and approval levels.
- Add a central tool registry that validates arguments and permission policy
  before executing deterministic Python handlers.
- Add sanitized, in-memory audit events containing tool identity, approval,
  timing, status, and active market-data snapshot identity.
- Register the first read-only local tools for scan summary, stock status,
  market condition, Backtester records, calculation trace, data health, and
  rejection summaries.
- Route Ticksy's existing hosted-provider context through the bounded
  application snapshot while preserving deterministic local routing and the
  existing explicit confirmation flow.
- Document the target agentic boundary and add focused regression tests.

### Deliberately Deferred

- Multi-step planning and model-directed state-changing operations.
- Agent-triggered scans, Backtests, email, refreshes, Git operations, or
  production deployment through the new registry.
- Durable audit storage, persistent user memory, and cross-snapshot analysis.
- Changes to financial formulas, strategy defaults, scoring, or data sources.

### Acceptance Criteria

- Secret and unrelated Streamlit state cannot enter the assistant context.
- Read-only tools operate only on copied local scan and Backtester state.
- State-changing, expensive, external-side-effect, and production tools cannot
  be registered with weaker-than-required approval.
- Every attempted registered tool call returns a structured result and creates
  a sanitized audit event.
- Existing Ticksy requests and confirmations continue to behave as before.
- Focused tests, the full test suite, changed-file lint, and
  `git diff --check` pass.


## Completed — Historical Valuation Foundation

### Goal

Add reproducible historical valuation and long-term fundamental data without
changing current scan qualification or result columns.

### Scope

- Add one bounded-retry Screener provider.
- Add one resumable refresh for historical P/E/TTM EPS, long-term growth,
  P/E averages/medians, debt-to-equity, ROE, and OPM.
- Calculate PEG in the daily Yahoo refresh using stored Screener 3-year profit
  growth.
- Process 10 stocks per batch and wait five seconds between batches by default.
- Publish versioned Screener snapshots through an atomic manifest in R2.
- Show historical P/E and TTM EPS only in the selected-stock chart.
- Keep growth, debt, ROE, OPM, daily PEG, and historical P/E summary fields
  backend-only.
- Preserve all existing mandatory/optional rules, ranking, and result columns.

### Acceptance Criteria

- Normal scans and chart expansion make no live Screener requests.
- Every universe symbol ends as a successful record or an audited failure.
- Interrupted refreshes resume after the last completed batch.
- The chart supports 1M, 6M, 1Y, 3Y, 5Y, and 10Y periods.
- No new Screener field affects qualification, score, exports, or main results.
- Automated tests cover parsing, calculations, throttling, retry, resume,
  storage validation, repository reads, and chart layers.

## Completed — Optional Fundamental Filters

### Goal

Add empty-by-default fundamental screening without changing mandatory
technical qualification, technical scoring, or the two result groups.

### Scope

- Add an ordered dropdown builder for nine valuation, growth, quality, and
  company-size filters.
- Use the current median Industry P/E for the relative valuation rule.
- Compare current P/E with the stock's own available 3Y/5Y/10Y average P/E.
- Apply three-state evaluation with lenient missing-data handling.
- Load the stored Screener summary once only when selected filters need it.
- Retain incomplete-data stocks with filter-level availability labels.
- Remove the legacy optional ten-post-cross-session rule.
- Persist optional settings only in active Streamlit session strategies.

### Acceptance Criteria

- No selected filters produces the same results as the existing scan.
- Confirmed failures reject with readable optional-check reasons.
- Missing individual historical periods do not create tags.
- Completely unavailable filter data retains the stock with one filter-level
  label.
- Post and Impending Golden Cross remain the only result groups.
- Optional filters do not affect score.
- Normal scans make no live Screener requests.
- Automated tests cover rule boundaries, partial history, missing snapshots,
  session reruns, and result formatting.

## Completed — Result Detail and Email Reporting

### Goal

Improve qualified-stock exploration and reproducible sharing without changing
scanner qualification, optional-filter formulas, scoring, or the Historical
P/E and TTM EPS chart.

### Scope

- Show market cap in crore and add debt-to-equity, ROE, and PEG to Company
  Overview while removing P/E Source.
- Present 3Y profit, EPS, and revenue CAGR as separate cards.
- Expand the price/MA chart to all retained history with 6M through Max
  controls, zoom, pan, reset, hover details, and range navigation.
- Email a filters-first workbook containing both result groups to one or more
  session-only recipients.
- Attach maximum-period price/MA charts in size-bounded ZIP parts.

### Acceptance Criteria

- Normal result expansion and report generation make no live Screener request.
- Missing company metrics display as unavailable.
- The workbook sheet order is Filters, Post Golden Cross, then Impending
  Golden Cross.
- SMTP credentials remain in Streamlit Secrets and recipients are not
  persisted.
- Existing technical rules, scoring, and valuation-chart behaviour remain
  unchanged.
- Tests cover display formatting, chart controls, workbook order, recipient
  validation, attachment batching, and SMTP delivery.

## Completed — Historical Golden Cross Backtester

### Goal

Let users replay the active Post Golden Cross strategy against historical
prices for selected Setup-universe stocks, without changing Live Scan results.

### Scope

- Use the refreshed ranked stock-universe snapshot and change the Setup
  default from 1,500 to 2,000 stocks, capped by the available universe.
- Add Backtester as the fifth workflow option and rename Results to Golden
  Cross Results.
- Reuse the complete Post Golden Cross rules with point-in-time evaluation:
  actual MA cross, cross age, MA slope, Long-MA decline/recovery, price-above-
  Long-MA, and maximum price premium checks.
- Produce one signal at the first qualifying close after each actual Golden
  Cross; do not repeat it until a new actual cross occurs.
- Enter at the next available trading session's unadjusted Open price.
- Calculate actual historical returns after 1W, 2W, 3W, 1M, 3M, 6M, and 1Y;
  show N/A when the future price history is insufficient.
- Add searchable multi-select stock selection from the Setup universe and 1Y,
  3Y, 5Y, and 10Y test-period controls.
- Show all active strategy parameters, signal-level P/E context, a result row
  for every historical signal, summary metrics, and a selected-stock chart.
- Use the established app theme and Results chart colours: Close navy, Short
  MA teal, and Long MA orange.
- Exclude dividends, fees, slippage, exit rules, re-entry, short positions,
  leverage, and portfolio allocation from this fixed-horizon MVP.

### Acceptance Criteria

- Backtest signals use no data that was unavailable on their signal date.
- Every signal uses the next available Open price as its entry.
- A stock can display multiple historical signals, with no duplicate signal for
  the same actual Golden Cross.
- Historical P/E uses the latest stored observation on or before the signal
  date and does not affect qualification.
- Live Scan session state and results remain independent of Backtester state.
- Results show Signals, Signals with 1Y data, average 1Y return, and median
  1Y return, without a win-rate metric.
- Automated tests cover signal timing, duplicate prevention, entry timing,
  return horizons, historical P/E selection, multi-stock selection, and the
  Setup default handoff.

## Partially delivered: Reliability and Auditability

Delivered: typed per-symbol failures with stage/reason, optional-rule rejection
reasons, moving-average-dependent history requests, aggregated rejection
insights, and scanner/data-loading regression tests.

Remaining:

- Add a searchable failed-stock view with stage/reason filtering.
- Make failure counts and data availability easier to inspect without Ticksy.
- Extend diagnostics for new rules, preserving existing qualification.

## Partially delivered: Performance and Data Resilience

Delivered: live/snapshot provider selection, batched price downloads, chart TTL
caching, verified R2 object reuse, bounded refresh retries/throttling, and scan
metrics for timing and data-source diagnostics.

Remaining:

- Surface existing duration, data-failure, and source/cache diagnostics in the UI.
- Measure scan and chart performance before choosing further optimizations.
- Review expiry and invalidation across live-provider data caches. Immutable
  snapshots already use content hashes and snapshot-specific cache keys.

## Partially delivered: Reporting and User Experience

Delivered: filters-first Excel email reports, both qualified result groups,
size-bounded chart attachments, scan timestamps, and up to five session-only
named strategies.

Remaining:

- Persist saved strategy profiles beyond the active session.
- Store completed scan history with strategy, source, and snapshot identity.
- Improve result filtering, sorting, and mobile exploration where needed.

## Completed: Ticksy Local-Data AI Assistant

### Goal

Add a local-data-only assistant that explains verified Stock Analyser results
and prepares confirmed scan or Backtester workflows without changing
calculation logic.

### Delivered Scope

- Bottom-right Ticksy launcher and themed panel with the Ticksy icon,
  session-only chat, New Chat, quick actions, and a permanently visible
  local-data-only summary.
- Typed assistant request/action models, bounded local context, and
  deterministic local-response routing.
- Local explanations for current Post Golden Cross, Impending Golden Cross, and
  failed-stock results. They use stored MA values, slopes, gaps, cross details,
  and recorded failure reasons where available.
- Natural-language recognition for common ticker and current-result company
  references, periods, market scans, Backtests, and moving-average-pair
  requests, with explicit confirmation before state-changing scan, strategy,
  or Backtester actions.
- Confirmed handoffs to Strategy, Live Scan, Results, selected-stock charts,
  and Backtester while preserving the active deterministic Python services and
  their outputs.
- On-request illustrative crossover windows for Impending stocks when the
  Short MA converges on the Long MA at a positive local rate; the response is
  explicitly not a prediction or a scan, ranking, alert, or Backtester rule.
- Current-scan market summaries, current-result stock comparisons, historical
  Backtester signal summaries, parameter help, data provenance, calculation
  traces, scan-health summaries, and plain-English local reports.
- Basic selected-universe company lookup, workflow guidance, a data
  dictionary, and session-only Ticksy notes.
- Confirmed strategy proposals for the core technical settings and supported
  threshold, P/E, and market-cap optional filters.
- Impending Golden Cross retained as an optional scan group with the prompt
  "Do you want impending stocks?" and a default maximum Short-MA/Long-MA gap
  of 10%.
- Gemini Flash and OpenAI provider implementations behind one configuration
  interface, plus a safe disabled state when the active provider key is absent.
- Strict no-browser, no-news, no-RAG, no-external-market-data tool boundary;
  Python services remain the calculation and rule source of truth.

### Acceptance Criteria

- Existing scan and Backtest calculations remain reproducible with or without
  Ticksy enabled.
- Ticksy cannot use browser, search, news, RAG, or external market-data tools.
- Proposed scan and Backtester actions require explicit user confirmation.
- Changing between Gemini Flash and OpenAI preserves the same local tools and
  deterministic calculation results.

## Delivered: Cloudflare R2 Storage

- Private R2 storage with separate IN/US namespaces. India is active; US
  ingestion remains future work.
- Immutable files and catalogs, hash verification, per-symbol reads, local
  caching, snapshot pinning, and verified rollback.
- Hosted reads use Streamlit Secrets. Scheduled publishers use the approved
  GitHub Actions Secret with read-only repository permissions.
- Daily market-data and monthly Screener workflows validate before activation.
  No-change runs retain the active snapshot; concurrent updates are guarded.
- Production datasets are removed from the current Git tree. Development uses
  explicit downloads; tests generate fixtures without cloud credentials.
- Retention previews, cache-cleanup commands, and storage-usage reports exist.
- Python calculations and Ticksy's local-data-only boundary are preserved.

Operational follow-up:

- Observe a scheduled run publishing changed data. The confirmed normal refresh
  returned `no_new_data`.
- Complete remaining hosted scan, chart, Backtester, Ticksy, and export checks.
- Monitor refresh and storage reports as additional snapshots accumulate.

See the [deployment and storage guide](deployment.md) for commands.

## Future — Advanced Backtesting

### Goal

Extend the historical Golden Cross backtester from fixed forward-return
measurement into optional trade and portfolio simulation.

### Scope

- Configurable exits: fixed holding period, profit target, stop loss, or a
  Death Cross exit.
- Portfolio allocation: equal allocation, fixed amount per signal, and a
  maximum number of open positions.
- Re-entry: permit a new trade only after the previous trade in that stock has
  exited and a later, new valid Golden Cross signal occurs.
- Keep broker fees, taxes, and slippage out of scope.

### Acceptance Criteria

- Every simulated trade records its entry date, entry price, exit date, exit
  price, exit reason, and realised return.
- Allocation rules never invest more capital than is available.
- Re-entry never duplicates an open trade or reuses the same Golden Cross.
- Fixed-horizon Backtester results remain available independently of this
  optional simulation mode.

## Partially delivered: Production Operations

Delivered: offline test CI, refresh-failure email notifications, refresh/storage
reports, guarded R2 publication, and documented snapshot rollback.

Remaining:

- Add automated linting to CI.
- Add ongoing deployment health checks and centralized error monitoring.
- Standardize release tags, changelog entries, and application-code rollback.
- Finish the R2 operational follow-up listed above.

## Future — Code Quality and Maintainability

### Goal

Make the application easier to understand and change without altering its
financial rules, local-data guardrails, or user-visible behaviour.

### Scope

- Split the scanner's per-symbol workflow into focused Post Golden Cross,
  Impending Golden Cross, shared-validation, and result-building helpers.
- Separate Ticksy panel rendering, pending-action confirmation, prompt
  routing, and provider-error presentation into small UI helpers.
- Separate Backtester data loading, execution, results rendering, and chart
  rendering into focused functions.
- Refactor the market-data refresh entrypoint into clear mode, preparation,
  persistence, and manifest-update stages; keep operational scripts aligned
  with every application change that affects them.
- Simplify Ticksy action routing by extracting repeated strategy session-state
  updates and making intent conditions explicit.
- Keep the existing Results-page helper structure and conservative
  Screener/filter validation logic unless a specific readability issue arises.

### Acceptance Criteria

- Refactors do not change scan qualification, scoring, Backtester outcomes,
  data-refresh outputs, or Ticksy guardrails.
- Each refactored workflow has focused tests for its existing behaviour.
- Function names, state transitions, and error paths make the workflow clear
  without requiring readers to trace unrelated UI or provider code.

## Future — United States Market Expansion

### Goal

Extend Stock Analyser to support a separate United States universe while
preserving the existing NSE workflow and data sets.

### Scope

- Add a market selector for India — NSE and United States — S&P 500.
- Maintain a versioned, market-cap-ranked S&P 500 stock universe with company
  names and exchange tickers.
- Use SEC Company Facts filings for historical annual and quarterly financial
  statements, with bounded retries, fair-use throttling, and auditable refresh
  results.
- Use Yahoo Finance raw historical prices for technical indicators and price-
  based valuation calculations.
- Retain at least ten years of annual history where available and quarterly
  history for the most recent five years where available.
- Calculate US equivalents of the existing fundamental metrics, including
  revenue and profit growth, EPS growth, debt-to-equity, ROE, operating margin,
  P/E, and PEG with clearly documented definitions.
- Keep country-specific field mappings and formula differences explicit rather
  than mixing US and NSE data in one source model.

### Acceptance Criteria

- Users can switch markets without mixing NSE and US symbols, prices, or
  fundamentals.
- The S&P 500 universe and financial snapshots are versioned and reproducible.
- Historical P/E uses raw price and point-in-time trailing EPS, without using
  dividend-adjusted prices.
- Missing, amended, or non-comparable SEC filing data is labelled unavailable
  rather than silently substituted.
- US data refreshes and calculations have automated coverage for mapping,
  point-in-time selection, and formula boundaries.

## Future — Ticksy Enhancements

### Goal

Build on the completed Ticksy foundation with additional local-data assistant
capabilities, without changing calculation logic or using external market,
news, web, or RAG data.

### Scope

- Broaden flexible natural-language phrasing for existing Ticksy actions and
  settings beyond common ticker/company, period, scan, Backtest, and
  moving-average-pair wording; ask a concise clarification only when needed.
- Extend the delivered failed-stock stage and reason explanation into a full
  rule-by-rule diagnostic and nearest-unmet-condition ranking.
- Extend the delivered Post and Impending explanation with requested
  conditions, unavailable-data detail, and optional-fundamental context that
  are not in the current local result record.
- Add an on-request daily change summary that compares the latest completed
  scan with the prior local snapshot, optionally by industry or requested
  stock, covering status, indicator, and available valuation changes.
- Broaden the delivered natural-language filter support beyond the current
  threshold, P/E, and market-cap phrases; display the interpreted filters and
  require confirmation before running a scan.
- Broaden answers across current local scan and Backtester results beyond the
  delivered market summaries, comparisons, reports, and signal histories,
  without modifying the underlying results.
- Extend selected-universe lookup with stored industry classifications and
  industry-membership counts.
- Explain why a stock entered or left a result group by comparing completed
  local scan snapshots and identifying the changed rule outcome.
- Persist user-approved notes as searchable local records beyond the current
  Ticksy session.

### Acceptance Criteria

- Assistant explanations list the data date, strategy values, and source
  values used for every rule-based conclusion.
- Requested strategy changes are displayed and explicitly confirmed before a
  scan or backtest runs.
- Equivalent natural-language phrasings produce the same interpreted action
  and the displayed interpretation lets users correct any misunderstanding.
- The assistant cannot alter settings, refresh data, or trigger external-data
  retrieval without a separate, explicit application workflow.
- Unavailable local data produces a clear unavailable response rather than an
  inferred or externally sourced answer.
- Existing scan and backtest outputs are reproducible with or without the
  assistant enabled.
- Switching Gemini Flash and OpenAI through configuration preserves the same
  local tool contracts, guardrails, and deterministic calculation results.
- Daily summaries use only completed local scan history and clearly state when
  a prior comparison snapshot or industry classification is unavailable.
