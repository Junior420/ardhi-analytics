"""Portfolio tracking: roll-up, market-shock alerts, actuals vs projections.

Owner-scoped. Everything is derived by re-running the tested analysis engine
over the user's saved deals — no metrics are stored, so a roll-up always
reflects the current rule pack and code. Actuals (what the property really
earned) are the only new persisted data.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text

from dbcore import engine_for
from finance_core.projections import build_pro_forma
from finance_core.sensitivity import shift

from . import store
from .analysis import to_assumptions
from .schemas import DealInput

_ACTUALS_SCHEMA = """CREATE TABLE IF NOT EXISTS deal_actuals (
    id TEXT PRIMARY KEY,
    deal_id TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    year INTEGER NOT NULL,
    gross_rent_actual REAL NOT NULL,
    opex_actual REAL NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
)"""


def _engine():
    engine = engine_for(store.DB_PATH)
    with engine.begin() as conn:
        conn.execute(text(_ACTUALS_SCHEMA))
    return engine


def _owned_deals(owner_id: str, is_admin: bool) -> list[tuple[str, dict]]:
    """(deal_id, payload) for each of the user's saved deals."""
    out = []
    for row in store.list_deals(None if is_admin else owner_id):
        rec = store.get_deal(row["id"])
        if rec:
            out.append((row["id"], {**rec["payload"], "_name": row["name"]}))
    return out


# ---------------------------------------------------------------- summary

def summary(owner_id: str, is_admin: bool = False) -> dict:
    deals = _owned_deals(owner_id, is_admin)
    rows, total_equity, total_noi, total_debt_service = [], 0.0, 0.0, 0.0
    weighted_irr_num = 0.0
    exposure_use: dict[str, float] = defaultdict(float)
    exposure_tenure: dict[str, float] = defaultdict(float)

    for deal_id, payload in deals:
        name = payload.pop("_name", "Untitled deal")
        try:
            deal = DealInput(**payload)
            a, _ = to_assumptions(deal)
            pf = build_pro_forma(a)
        except Exception:
            rows.append({"id": deal_id, "name": name, "error": "could not analyze"})
            continue
        m = pf.metrics
        equity = m["equity_invested"]
        irr_key = "levered_irr" if deal.loan else "unlevered_irr"
        irr = m.get(irr_key)
        total_equity += equity
        total_noi += m["noi_year1"]
        if "annual_debt_service" in m:
            total_debt_service += m["annual_debt_service"]
        if irr is not None:
            weighted_irr_num += irr * equity
        exposure_use[deal.use] += equity
        exposure_tenure[deal.tenure] += equity
        rows.append({
            "id": deal_id, "name": name, "use": deal.use,
            "equity_invested": equity, "levered_irr": m.get("levered_irr"),
            "unlevered_irr": m.get("unlevered_irr"),
            "dscr_year1": m.get("dscr_year1"), "noi_year1": m["noi_year1"],
        })

    return {
        "deal_count": len(deals),
        "total_equity_invested": total_equity,
        "total_noi_year1": total_noi,
        "portfolio_dscr_year1": (total_noi / total_debt_service
                                 if total_debt_service else None),
        "equity_weighted_irr": (weighted_irr_num / total_equity
                                if total_equity else None),
        "exposure_by_use": dict(exposure_use),
        "exposure_by_tenure": dict(exposure_tenure),
        "deals": rows,
    }


# ----------------------------------------------------------------- alerts

def alerts(owner_id: str, is_admin: bool = False,
           rate_bps: float = 100, rent_pct: float = -10) -> dict:
    """Stress every saved deal under a market shock and flag ones that break.

    rate_bps: parallel shift in the loan interest rate (basis points).
    rent_pct: relative shock to gross rent (percent, negative = decline)."""
    rate_delta = rate_bps / 10_000.0
    rent_delta = rent_pct / 100.0
    out_alerts = []

    for deal_id, payload in _owned_deals(owner_id, is_admin):
        name = payload.pop("_name", "Untitled deal")
        try:
            deal = DealInput(**payload)
            a, _ = to_assumptions(deal)
            base = build_pro_forma(a)
            shocked = a
            if a.loan:
                shocked = shift(shocked, "loan.annual_rate", "absolute", rate_delta)
            shocked = shift(shocked, "gross_rent_annual", "relative", rent_delta)
            stressed = build_pro_forma(shocked)
        except Exception:
            continue

        b, s = base.metrics, stressed.metrics
        flags = []
        if "dscr_year1" in b:
            if s["dscr_year1"] < 1.0 <= b["dscr_year1"]:
                flags.append(f"DSCR falls below 1.0 ({b['dscr_year1']:.2f} → {s['dscr_year1']:.2f})")
            elif s["dscr_year1"] < 1.0:
                flags.append(f"DSCR stays below 1.0 ({b['dscr_year1']:.2f} → {s['dscr_year1']:.2f})")
        irr_key = "levered_irr" if deal.loan else "unlevered_irr"
        b_irr, s_irr = b.get(irr_key), s.get(irr_key)
        if s_irr is not None and b_irr is not None and s_irr < deal.discount_rate <= b_irr:
            flags.append(f"IRR drops below the {deal.discount_rate:.0%} hurdle "
                         f"({b_irr:.1%} → {s_irr:.1%})")
        if base.years[0].cash_flow_after_debt >= 0 > stressed.years[0].cash_flow_after_debt:
            flags.append("Year-1 cash flow turns negative")

        if flags:
            out_alerts.append({"id": deal_id, "name": name, "flags": flags})

    return {
        "shock": {"rate_bps": rate_bps, "rent_pct": rent_pct},
        "alert_count": len(out_alerts),
        "alerts": out_alerts,
    }


# ---------------------------------------------------------------- actuals

def record_actual(deal_id: str, owner_id: str, year: int,
                  gross_rent_actual: float, opex_actual: float,
                  note: str = "") -> dict:
    rec = {"id": str(uuid.uuid4()), "deal_id": deal_id, "owner_id": owner_id,
           "year": year, "gross_rent_actual": gross_rent_actual,
           "opex_actual": opex_actual, "note": note,
           "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    with _engine().begin() as conn:
        conn.execute(text(
            """INSERT INTO deal_actuals (id, deal_id, owner_id, year,
                  gross_rent_actual, opex_actual, note, created_at)
               VALUES (:id, :deal_id, :owner_id, :year, :gross_rent_actual,
                       :opex_actual, :note, :created_at)"""), rec)
    return rec


def variance(deal_id: str, payload: dict, owner_id: str) -> dict:
    """Compare recorded actuals against the projected year they map to."""
    deal = DealInput(**{k: v for k, v in payload.items() if not k.startswith("_")})
    a, _ = to_assumptions(deal)
    pf = build_pro_forma(a)
    with _engine().connect() as conn:
        rows = conn.execute(text(
            "SELECT year, gross_rent_actual, opex_actual, note FROM deal_actuals "
            "WHERE deal_id = :d AND owner_id = :o ORDER BY year"),
            {"d": deal_id, "o": owner_id}).mappings().all()

    result = []
    for r in rows:
        year = r["year"]
        if year < 1 or year > len(pf.years):
            result.append({"year": year, "error": "year outside projection horizon"})
            continue
        proj = pf.years[year - 1]
        rent_var = r["gross_rent_actual"] - proj.gross_potential_income
        opex_var = r["opex_actual"] - proj.operating_expenses
        noi_actual = (r["gross_rent_actual"] * (1 - deal.vacancy_rate)) - r["opex_actual"]
        result.append({
            "year": year,
            "gross_rent": {"projected": proj.gross_potential_income,
                           "actual": r["gross_rent_actual"], "variance": rent_var,
                           "variance_pct": rent_var / proj.gross_potential_income
                           if proj.gross_potential_income else None},
            "opex": {"projected": proj.operating_expenses,
                     "actual": r["opex_actual"], "variance": opex_var},
            "noi": {"projected": proj.noi, "actual": noi_actual,
                    "variance": noi_actual - proj.noi},
            "note": r["note"],
        })
    return {"deal_id": deal_id, "years_recorded": len(rows), "variance": result}
