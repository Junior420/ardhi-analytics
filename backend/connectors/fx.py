"""FX connector — open.er-api.com (free, keyless, daily-updated USD rates)."""

from __future__ import annotations

from typing import Callable

from .base import DataPoint, FetchError, fetch_json, now_iso

URL = "https://open.er-api.com/v6/latest/USD"


def usd_rate(currency: str, fetcher: Callable = fetch_json) -> DataPoint:
    """Units of `currency` per 1 USD."""
    body = fetcher(URL)
    if not isinstance(body, dict) or body.get("result") != "success":
        raise FetchError("unexpected FX API response")
    rate = body.get("rates", {}).get(currency.upper())
    if rate is None:
        raise FetchError(f"currency {currency} not in FX response")
    return DataPoint(
        series=f"usd_{currency.lower()}",
        value=float(rate),
        unit=f"{currency.upper()}_per_USD",
        as_of=str(body.get("time_last_update_utc", "")),
        source="Exchange Rate API (open.er-api.com)",
        source_url=URL,
        retrieved_at=now_iso(),
        provenance="live",
    )
