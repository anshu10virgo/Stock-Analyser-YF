# Project Rules

## Product Standards

- Treat Stock Analyser YF as a production-oriented application.
- Preserve scan reproducibility by recording scan time, selected settings, and
  price basis.
- Do not silently skip a symbol. Return a structured failure with a stage and
  reason whenever processing cannot continue.
- Keep technical rules independent from Streamlit rendering.
- Do not present unavailable provider data as a valid zero or pass result.

## Engineering Standards

- Add type hints and docstrings to new public functions and classes.
- Add or update automated tests for every scanner rule, data-provider behavior,
  and bug fix.
- Use logging rather than `print()` for operational events and failures.
- Keep external-provider retries bounded and cache only successful responses.
- Keep secrets out of Git; use Streamlit secrets or environment variables.

## Delivery Standards

- Update documentation and `docs/project_progress.md` with completed work.
- Run the relevant tests before committing.
- Commit focused changes with descriptive messages and push only verified code.
