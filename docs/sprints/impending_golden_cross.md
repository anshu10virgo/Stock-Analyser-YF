# Sprint: Impending Golden Cross

## Goal

Extend the existing Post Golden Cross scanner with an opt-in Impending Golden
Cross path while keeping qualification results separate and reusing shared
technical calculations.

## Frontend Scope

- Group Strategy controls into Golden Cross shared mandatory checks and Post
  Golden Cross mandatory checks.
- Add an opt-in Impending Golden Cross control that reveals only its unique
  configurable thresholds.
- Preserve optional Post-Cross confirmations and session-only presets.
- Show Post and Impending counts during scanning and separate tables after the
  scan.
- Reduce the size of the Setup, Strategy, Live Scan, and Results navigation.

## Backend Scope

- Route stocks above the Long-MA relationship to Post-Cross evaluation and
  stocks at or below it to Impending evaluation when enabled.
- Apply shared Short-MA direction, Long-MA 52-week decline, and price-premium
  checks once.
- Add configurable 3% MA-gap and 20-session pre-cross defaults.
- Require the Short-MA five-session slope to exceed the Long-MA slope for an
  impending result.
- Permit a non-negative latest five-session Long-MA slope for impending stocks
  while retaining strict positive recovery for Post-Cross stocks.
- Keep the existing score exclusive to Post Golden Cross results.
- Remove the legacy stock-universe fallback and require the active-universe
  manifest.

## Documentation Scope

- Update business rules, features, architecture, progress, and roadmap.
- Describe the manual universe refresh followed by market-data reconciliation.

## Acceptance Criteria

- Impending scanning is disabled by default.
- Enabling it does not change Post Golden Cross qualification.
- Results appear in mutually exclusive Post and Impending groups.
- Impending results satisfy every shared and unique mandatory rule.
- Saved session strategies include the new settings without changing system
  defaults or writing user presets to Git.
- Missing universe manifests fail explicitly instead of reading a legacy file.
- Automated tests cover proximity, acceleration, pre-cross history, flat
  Long-MA acceptance, result separation, and manifest-only universe selection.
