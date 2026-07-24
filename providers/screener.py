"""Screener.in provider for cached historical valuation fundamentals."""

from __future__ import annotations

import re
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Callable

import pandas as pd
import requests
from bs4 import BeautifulSoup


SUMMARY_COLUMNS = (
    "symbol",
    "screener_company_id",
    "statement_type",
    "financial_reporting_date",
    "pe_average_3y",
    "pe_median_3y",
    "pe_average_5y",
    "pe_median_5y",
    "pe_average_10y",
    "pe_median_10y",
    "sales_growth_3y",
    "sales_growth_5y",
    "sales_growth_10y",
    "profit_growth_3y",
    "profit_growth_5y",
    "profit_growth_10y",
    "eps_growth_3y",
    "eps_growth_5y",
    "eps_growth_10y",
    "debt_to_equity",
    "roe",
    "opm",
    "source_url",
    "refreshed_at",
)
HISTORY_COLUMNS = ("symbol", "date", "pe", "ttm_eps")


class ScreenerDataError(RuntimeError):
    """Raised when a Screener response cannot satisfy the data contract."""


@dataclass(frozen=True)
class ScreenerCompanySnapshot:
    """One company's summary metrics and chart observations."""

    summary: dict
    history: pd.DataFrame


def _number(value):
    if value is None:
        return None
    cleaned = (
        str(value)
        .replace(",", "")
        .replace("%", "")
        .replace("\u20b9", "")
        .replace("Cr.", "")
        .strip()
    )
    if cleaned in {"", "-", "--"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cagr(start, end, years):
    """Return conventional CAGR only when both endpoints are positive."""
    if start is None or end is None or start <= 0 or end <= 0:
        return None
    return ((end / start) ** (1 / years) - 1) * 100


def _table_rows(section) -> tuple[list[str], dict[str, list[float | None]]]:
    if section is None:
        return [], {}
    table = section.find("table")
    if table is None:
        return [], {}
    header_cells = table.select("thead th")
    headers = [" ".join(cell.stripped_strings) for cell in header_cells][1:]
    rows = {}
    for row in table.select("tbody tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        label = " ".join(cells[0].stripped_strings).removesuffix(" +").strip()
        rows[label] = [_number(" ".join(cell.stripped_strings)) for cell in cells[1:]]
    return headers, rows


def _growth_values(section, label: str) -> dict[int, float | None]:
    if section is None:
        return {3: None, 5: None, 10: None}
    tokens = list(section.stripped_strings)
    try:
        start = tokens.index(label) + 1
    except ValueError:
        return {3: None, 5: None, 10: None}
    values = {}
    for index in range(start, min(start + 12, len(tokens) - 1)):
        match = re.fullmatch(r"(3|5|10) Years:", tokens[index])
        if match:
            values[int(match.group(1))] = _number(tokens[index + 1])
    return {years: values.get(years) for years in (3, 5, 10)}


def _top_ratios(soup) -> dict[str, float | None]:
    """Extract the numeric values displayed in Screener's top-ratio cards."""
    ratios = {}
    container = soup.find("ul", id="top-ratios")
    if container is None:
        return ratios
    for item in container.find_all("li"):
        name = item.find("span", class_="name")
        value = item.find("span", class_="number")
        if name is not None and value is not None:
            ratios[" ".join(name.stripped_strings)] = _number(
                " ".join(value.stripped_strings)
            )
    return ratios


def _latest_value(values) -> float | None:
    return next((value for value in reversed(values) if value is not None), None)


class ScreenerFundamentalsProvider:
    """Fetch public Screener company pages and historical valuation charts."""

    BASE_URL = "https://www.screener.in"
    MAX_RETRIES = 3
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(
        self,
        session=None,
        timeout_seconds: int = 20,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.sleep = sleep
        self._metrics = {"requests": 0, "retries": 0, "failures": 0}

    @staticmethod
    def screener_symbol(symbol: str) -> str:
        return symbol.upper().removesuffix(".NS").removesuffix(".BO")

    def _get(self, url, **kwargs):
        last_error = None
        request_headers = kwargs.pop("headers", {})
        for attempt in range(self.MAX_RETRIES):
            try:
                self._metrics["requests"] += 1
                response = self.session.get(
                    url,
                    headers={
                        "User-Agent": self.USER_AGENT,
                        **request_headers,
                    },
                    timeout=self.timeout_seconds,
                    **kwargs,
                )
                response.raise_for_status()
                return response
            except requests.RequestException as error:
                last_error = error
                if attempt < self.MAX_RETRIES - 1:
                    self._metrics["retries"] += 1
                    self.sleep(2 ** attempt)
        self._metrics["failures"] += 1
        raise ScreenerDataError(f"Screener request failed: {url}") from last_error

    @staticmethod
    def _history_frame(datasets, metric, value_column):
        rows = datasets.get(metric, [])
        frame = pd.DataFrame(
            [(row[0], row[1]) for row in rows if len(row) >= 2],
            columns=("date", value_column),
        )
        if frame.empty:
            return frame
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
        return (
            frame.dropna(subset=["date", value_column])
            .drop_duplicates("date", keep="last")
            .sort_values("date")
        )

    @staticmethod
    def _pe_statistics(pe: pd.DataFrame) -> dict:
        latest = pe["date"].max()
        statistics = {}
        for years in (3, 5, 10):
            period = pe.loc[pe["date"].ge(latest - pd.DateOffset(years=years)), "pe"]
            statistics[f"pe_average_{years}y"] = (
                round(float(period.mean()), 4) if not period.empty else None
            )
            statistics[f"pe_median_{years}y"] = (
                round(float(period.median()), 4) if not period.empty else None
            )
        return statistics

    @staticmethod
    def _annual_eps(headers, values) -> tuple[list[pd.Timestamp], list[float]]:
        observations = []
        for header, value in zip(headers, values):
            parsed_date = pd.to_datetime(header, format="%b %Y", errors="coerce")
            if pd.notna(parsed_date) and value is not None:
                observations.append((parsed_date, value))
        observations.sort(key=lambda item: item[0])
        return (
            [item[0] for item in observations],
            [item[1] for item in observations],
        )

    def fetch(self, symbol: str, refreshed_at: str) -> ScreenerCompanySnapshot:
        """Fetch every Screener-derived metric required by the snapshot."""
        screener_symbol = self.screener_symbol(symbol)
        source_url = f"{self.BASE_URL}/company/{screener_symbol}/consolidated/"
        page = self._get(source_url)
        soup = BeautifulSoup(page.text, "html.parser")
        company_info = soup.find(id="company-info")
        company_id = company_info.get("data-company-id") if company_info else None
        if not company_id:
            raise ScreenerDataError(
                f"Screener company identifier is unavailable for {symbol}"
            )
        is_consolidated = company_info.get("data-consolidated") == "true"
        statement_type = "consolidated" if is_consolidated else "standalone"

        chart = self._get(
            f"{self.BASE_URL}/api/company/{company_id}/chart/",
            params={
                "q": "Price to Earning-Median PE-EPS",
                "days": 3650,
                "consolidated": str(is_consolidated).lower(),
            },
            headers={"Referer": source_url},
        )
        try:
            payload = chart.json()
        except ValueError as error:
            raise ScreenerDataError(
                f"Screener chart response is invalid for {symbol}"
            ) from error
        if not isinstance(payload, dict):
            raise ScreenerDataError(
                f"Screener chart response is invalid for {symbol}"
            )
        datasets = {
            dataset.get("metric"): dataset.get("values", [])
            for dataset in payload.get("datasets", [])
            if dataset.get("metric")
        }
        pe = self._history_frame(datasets, "Price to Earning", "pe")
        eps = self._history_frame(datasets, "EPS", "ttm_eps")
        if pe.empty:
            raise ScreenerDataError(
                f"Screener returned no historical P/E observations for {symbol}"
            )
        history = pe.merge(eps, on="date", how="outer").sort_values("date")
        history.insert(0, "symbol", symbol)

        profit_loss = soup.find("section", id="profit-loss")
        balance_sheet = soup.find("section", id="balance-sheet")
        annual_headers, profit_rows = _table_rows(profit_loss)
        balance_headers, balance_rows = _table_rows(balance_sheet)
        sales_growth = _growth_values(profit_loss, "Compounded Sales Growth")
        profit_growth = _growth_values(profit_loss, "Compounded Profit Growth")
        top_ratios = _top_ratios(soup)
        roe = top_ratios.get("ROE")
        opm = _latest_value(profit_rows.get("OPM %", []))

        eps_dates, annual_eps = self._annual_eps(
            annual_headers, profit_rows.get("EPS in Rs", [])
        )
        eps_growth = {}
        for years in (3, 5, 10):
            eps_growth[years] = (
                _cagr(annual_eps[-(years + 1)], annual_eps[-1], years)
                if len(annual_eps) >= years + 1
                else None
            )

        equity_capital = balance_rows.get("Equity Capital", [])
        reserves = balance_rows.get("Reserves", [])
        borrowings = balance_rows.get("Borrowings", [])
        debt_to_equity = None
        if equity_capital and reserves and borrowings:
            equity = (equity_capital[-1] or 0) + (reserves[-1] or 0)
            if equity > 0 and borrowings[-1] is not None:
                debt_to_equity = borrowings[-1] / equity

        reporting_date = None
        if balance_headers:
            parsed = pd.to_datetime(
                balance_headers[-1], format="%b %Y", errors="coerce"
            )
            if pd.notna(parsed):
                reporting_date = (parsed + pd.offsets.MonthEnd(0)).date().isoformat()
        if reporting_date is None and eps_dates:
            reporting_date = eps_dates[-1].date().isoformat()

        summary = {
            "symbol": symbol,
            "screener_company_id": str(company_id),
            "statement_type": statement_type,
            "financial_reporting_date": reporting_date,
            **self._pe_statistics(pe),
            "sales_growth_3y": sales_growth[3],
            "sales_growth_5y": sales_growth[5],
            "sales_growth_10y": sales_growth[10],
            "profit_growth_3y": profit_growth[3],
            "profit_growth_5y": profit_growth[5],
            "profit_growth_10y": profit_growth[10],
            "eps_growth_3y": eps_growth[3],
            "eps_growth_5y": eps_growth[5],
            "eps_growth_10y": eps_growth[10],
            "debt_to_equity": debt_to_equity,
            "roe": roe,
            "opm": opm,
            "source_url": page.url or source_url,
            "refreshed_at": refreshed_at,
        }
        return ScreenerCompanySnapshot(
            summary={column: summary.get(column) for column in SUMMARY_COLUMNS},
            history=history[list(HISTORY_COLUMNS)].reset_index(drop=True),
        )

    def metrics(self):
        return deepcopy(self._metrics)
