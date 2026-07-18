# Stock Analyser YF

Stock Analyser YF is a production-oriented Streamlit application for
configurable NSE technical screening using Yahoo Finance market data.

## Run locally

```powershell
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## Current capabilities

- Configurable moving-average and Golden Cross scans.
- Adjustable adjusted/unadjusted price basis.
- Yahoo Finance fundamentals with retries and in-memory caching.
- Formatted results, scan timestamps, and one-year interactive charts.
- GitHub-backed Streamlit Community Cloud deployment.

## Documentation

- [Architecture](docs/architecture.md)
- [Business rules](docs/business_rules.md)
- [Roadmap](docs/roadmap.md)
- [Current TODO](docs/todo.md)
- [Project rules](docs/project_rules.md)
