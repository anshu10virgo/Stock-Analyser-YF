# Stock Analyser YF

## Purpose

Build a dependable, configurable stock-analysis application for NSE securities.
The product must provide transparent technical screening, reliable source-data
presentation, actionable failure reporting, and a responsive Streamlit
experience for desktop and mobile users.

## Objectives

- Provide configurable, repeatable technical scans.
- Make every pass, rejection, data-quality issue, and provider failure
  traceable to a reason.
- Display responsive stock charts with the same settings used by the scan.
- Support shareable deployment and controlled releases through GitHub.
- Improve performance through safe caching and efficient batch retrieval.
- Maintain automated tests for critical scanner and data-provider behavior.

## Data Source

Yahoo Finance is the current market-data provider.

## Scope

- Moving averages and Golden Cross detection
- Trough, trend, distance, and ranking analysis
- Fundamental context where Yahoo Finance provides it
- Interactive Streamlit reporting

Historical data is currently downloaded on demand. The architecture must remain
ready for persistent market-data storage and additional providers when scale or
reliability requires them.
