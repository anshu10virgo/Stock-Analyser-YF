# Stock Analyser Agent Instructions

## Scope

These instructions apply to the entire repository.

## Project Rules

- Keep Ticksy local-data-only. Do not add browser, web-search, news, RAG, or
  external market-data tools to the assistant.
- Keep Python services as the single source of truth for scan, strategy, and
  Backtester calculations. Model providers only interpret requests and present
  local results.
- Require explicit user confirmation before a Ticksy action changes strategy
  settings or prepares a scan or Backtest.
- Keep API keys only in Streamlit Secrets. Never commit `.streamlit/secrets.toml`.
  User-approved exception: R2 refresh and housekeeping jobs may use the repository's
  `R2_PUBLISHER_CONFIG` GitHub Actions Secret. The hosted app receives only
  read-only R2 credentials in Streamlit Secrets, never publisher credentials.
- Preserve the established `Stock Analyser` visual theme and concise UI labels.
- Write clear, easy-to-understand code with descriptive names, small focused
  functions, and straightforward control flow. Avoid unnecessary complexity.
- After every project update, review `scripts/` and update any affected script
  so operational workflows remain aligned with the application.

## Validation

- Add or update focused tests when changing scanner, Backtester, or Ticksy
  behaviour.
- Run the relevant tests and `git diff --check` before proposing a commit.
- Do not commit local previews, generated caches, `.codex/`, or
  `wireframe-work/` artifacts unless the user explicitly requests them.
