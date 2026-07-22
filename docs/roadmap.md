# Roadmap

## Active Sprint — Impending Golden Cross

### Goal

Extend the existing Post Golden Cross scanner with an opt-in Impending Golden
Cross path while keeping qualification results separate and reusing shared
technical calculations.

### Scope

- Split strategy controls into shared, Post-Cross, and opt-in Impending-Cross
  mandatory checks.
- Keep Post and Impending results separate throughout live progress and final
  reporting.
- Add a configurable MA-proximity threshold with a 3% default and a 20% upper
  selection limit, plus a 20-session pre-cross validation default.
- Require the Short-MA five-session slope to exceed the Long-MA slope for an
  impending result.
- Permit a non-negative five-session Long-MA slope for Impending stocks while
  retaining strict positive recovery for Post-Cross stocks.
- Keep the existing 85-point score exclusive to Post Golden Cross results.
- Remove the legacy symbol-file fallback and rely on the validated-universe
  manifest.
- Reduce the size of the four-step workflow navigation.
- Add regression coverage and synchronize business, feature, progress, and
  architecture documentation.

### Acceptance Criteria

- Impending scanning is disabled by default and does not alter Post Golden
  Cross qualification when enabled.
- Results remain mutually exclusive Post and Impending groups.
- Every Impending result satisfies all shared and unique mandatory rules.
- Session strategies retain the new settings without changing system defaults
  or writing user presets to Git.
- A missing universe manifest fails explicitly without a legacy-file fallback.
- Automated tests cover proximity, acceleration, pre-cross history, flat
  Long-MA acceptance, result separation, and manifest-only universe selection.

## Release 1.1 — Reliability and Auditability

- Structured failure results for every symbol and scanner stage.
- Dashboard view for failed stocks and aggregated failure counts.
- Enforce any future optional scanner rules consistently and expose structured
  rejection reasons.
- Derive minimum history requirements from the configured moving averages.
- Automated tests for data loading, scanner rules, and failure handling.

## Release 1.2 — Performance and Data Resilience

- TTL caching for price history, chart data, and fundamentals.
- Batch-level download diagnostics and controlled retry/throttling.
- Data-provider abstraction to support an alternative provider or local store.
- Scan execution metrics: duration, symbols processed, data failures, and
  cache usage.

## Release 1.3 — Reporting and User Experience

- Excel and CSV exports for qualified and rejected stocks.
- Saved scan configuration profiles.
- Filters, sorting, and mobile-friendly result exploration.
- Clear scan history and result timestamping.

## Release 1.4 — Production Operations

- Continuous integration for tests and linting.
- Deployment health checks, structured logs, and error monitoring.
- Release tags, changelog, and rollback procedure.
