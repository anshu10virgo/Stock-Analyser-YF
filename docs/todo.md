# Current TODO

## Reliability

- [ ] Record a structured failure for every skipped or errored symbol.
- [ ] Show failed stocks and failure reasons in the dashboard.
- [ ] Replace silent broad exception handling with logging and typed outcomes.
- [ ] Validate available history against configured MA periods.

## Scanner Correctness

- [ ] Enforce price above Long MA.
- [ ] Apply the Require Higher Low setting.
- [ ] Apply enabled Long MA trend validation.
- [x] Enforce the 52-week Long-MA high-to-trough-to-recovery validation.

## Performance

- [ ] Add TTL caching for price and chart data.
- [ ] Add execution timing and cache metrics.
- [ ] Add controlled Yahoo request throttling for large scans.

## Quality and Delivery

- [ ] Add automated tests for scanner rules and provider failures.
- [ ] Add CI checks for tests and linting.
- [ ] Add release notes and deployment-health guidance.
