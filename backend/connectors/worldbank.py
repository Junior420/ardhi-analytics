"""World Bank Open Data connector (no API key, stable JSON API).

Macro series per country: CPI inflation, real GDP growth, lending rate.
Docs: https://datahelpdesk.worldbank.org/knowledgebase/topics/125589
"""

from __future__ import annotations

from typing import Callable, Optional

from .base import DataPoint, FetchError, fetch_json, now_iso

BASE = "https://api.worldbank.org/v2/country/{iso3}/indicator/{code}?format=json&mrv=5"

INDICATORS = {
    "inflation_cpi_yoy": ("FP.CPI.TOTL.ZG", "Inflation, consumer prices (annual %)"),
    "gdp_growth": ("NY.GDP.MKTP.KD.ZG", "GDP growth (annual %)"),
    "lending_rate": ("FR.INR.LEND", "Lending interest rate (%)"),
}


def get_indicator(series: str, iso3: str,
                  fetcher: Callable = fetch_json) -> Optional[DataPoint]:
    """Latest non-null observation for a series, or None if the country has
    no data for it (e.g. Tanzania does not report FR.INR.LEND some years)."""
    code, label = INDICATORS[series]
    url = BASE.format(iso3=iso3, code=code)
    body = fetcher(url)
    if not isinstance(body, list) or len(body) < 2 or not body[1]:
        raise FetchError(f"unexpected World Bank response shape for {code}")
    for obs in body[1]:  # most recent first
        if obs.get("value") is not None:
            return DataPoint(
                series=series,
                value=float(obs["value"]) / 100.0,  # store rates as fractions
                unit="fraction",
                as_of=str(obs["date"]),
                source=f"World Bank — {label}",
                source_url=url,
                retrieved_at=now_iso(),
                provenance="live",
            )
    return None
