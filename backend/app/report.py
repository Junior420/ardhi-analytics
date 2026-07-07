"""One-click PDF reports (fpdf2). Three templates, one dispatcher:

- investor : full investment appraisal (metrics, projections, scenarios,
             Monte Carlo, market context, compliance)
- bank     : collateral/lender report (LTV, DSCR, debt yield, amortization
             profile, stressed serviceability)
- valuer   : IVS-aligned valuation workpaper (basis of value, approaches,
             disclosed assumptions, signature block) — support material for
             a registered valuer, never a signed valuation by itself
"""

from __future__ import annotations

from datetime import date

from fpdf import FPDF

from connectors import market_snapshot
from finance_core import dcf_value, direct_capitalization, reconcile_approaches
from finance_core.projections import build_pro_forma
from finance_core.sensitivity import shift

from . import insights
from .analysis import to_assumptions
from .schemas import AnalysisResult

TEMPLATES = ("investor", "bank", "valuer")

_MARKET_LABELS = {
    "inflation_cpi_yoy": "Inflation (CPI, y/y)",
    "gdp_growth": "GDP growth",
    "lending_rate": "Lending interest rate",
    "policy_rate": "Central bank policy rate",
    "mortgage_rate_typical": "Typical mortgage rate",
    "usd_tzs": "USD/TZS exchange rate",
}

INK = (30, 41, 59)
MUTED = (100, 116, 139)
ACCENT = (13, 110, 93)


def _txt(s: str) -> str:
    """Core PDF fonts are latin-1; degrade anything else gracefully."""
    return (s.replace("—", "-").replace("–", "-")
             .replace("’", "'").replace("‘", "'")
             .encode("latin-1", "replace").decode("latin-1"))


def _fmt(v: float, currency: str = "") -> str:
    return f"{currency} {v:,.0f}".strip()


def _pct(v) -> str:
    return "n/a" if v is None else f"{v * 100:.2f}%"


class _Report(FPDF):
    doc_kind = "Investment Appraisal"

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*MUTED)
        self.cell(0, 6, _txt(f"Ardhi Analytics - {self.doc_kind}"), align="R",
                  new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 6, f"Page {self.page_no()} - Analysis, not advice. Generated {date.today().isoformat()}",
                  align="C")

    def section(self, title: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*ACCENT)
        self.cell(0, 8, _txt(title), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)

    def kv(self, label: str, value: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.cell(70, 6, _txt(label))
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*INK)
        self.cell(0, 6, _txt(value), new_x="LMARGIN", new_y="NEXT")

    def note(self, text: str, size: int = 7):
        self.set_font("Helvetica", "I", size)
        self.set_text_color(*MUTED)
        self.multi_cell(0, 4, _txt(text), new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)

    def table(self, headers: list[str], widths: list[int], rows: list[list[str]]):
        self.set_font("Helvetica", "B", 8)
        for h, w in zip(headers, widths):
            self.cell(w, 6, _txt(h), border="B")
        self.ln()
        self.set_font("Helvetica", "", 8)
        for row in rows:
            for val, w in zip(row, widths):
                self.cell(w, 6, _txt(val))
            self.ln()


def _start(r: AnalysisResult, doc_kind: str, title_suffix: str = "") -> _Report:
    pdf = _Report()
    pdf.doc_kind = doc_kind
    pdf.set_title(f"{doc_kind} - {r.deal.name}")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, _txt(r.deal.name + title_suffix), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, _txt(f"Jurisdiction: {r.rulepack['jurisdiction']} (rule pack v{r.rulepack['version']}, "
                        f"{r.rulepack['status']}) - {r.deal.use} - {r.deal.hold_years}-year hold"),
             new_x="LMARGIN", new_y="NEXT")
    return pdf


def _compliance_and_disclaimer(pdf: _Report, r: AnalysisResult):
    pdf.section("Compliance Checklist")
    pdf.set_font("Helvetica", "", 9)
    for flag in r.compliance_flags:
        pdf.multi_cell(0, 5, _txt(f"- {flag['message']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 6, "Transfer procedure (registered land):", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    for i, step in enumerate(r.procedure_steps, 1):
        pdf.multi_cell(0, 5, _txt(f"{i}. {step['step']} (~{step.get('typical_days', '?')} days)"),
                       new_x="LMARGIN", new_y="NEXT")
    pdf.section("Disclaimer")
    pdf.note(r.disclaimer, size=8)


def _market_context(pdf: _Report, r: AnalysisResult):
    try:
        snapshot = market_snapshot(r.deal.jurisdiction)
    except Exception:
        return
    if not snapshot["series"]:
        return
    pdf.section("Market Context")
    for key, point in snapshot["series"].items():
        label = _MARKET_LABELS.get(key, key.replace("_", " "))
        if point["unit"] == "fraction":
            value = _pct(point["value"])
        else:
            value = f"{point['value']:,.2f} {point['unit'].replace('_', ' ')}"
        tag = point["provenance"] + (", stale" if point["stale"] else "")
        pdf.kv(label, value)
        pdf.note(f"    {point['source']} - as of {point['as_of']} ({tag})")


# ---------------------------------------------------------------- investor

def _build_investor(r: AnalysisResult) -> _Report:
    cur = r.deal.currency
    pdf = _start(r, "Investment Appraisal")
    m = r.metrics

    pdf.section("Key Metrics")
    pdf.kv("Purchase price", _fmt(r.deal.purchase_price, cur))
    pdf.kv("Total acquisition cost (incl. duties/fees)", _fmt(m["total_acquisition_cost"], cur))
    pdf.kv("Equity invested", _fmt(m["equity_invested"], cur))
    pdf.kv("NOI (year 1)", _fmt(m["noi_year1"], cur))
    pdf.kv("Entry cap rate", _pct(m["entry_cap_rate"]))
    pdf.kv("Levered IRR", _pct(m.get("levered_irr")))
    pdf.kv("Unlevered IRR", _pct(m.get("unlevered_irr")))
    pdf.kv("NPV (levered, at discount rate)", _fmt(m["levered_npv"], cur))
    pdf.kv("Equity multiple", f"{m['equity_multiple']:.2f}x")
    pdf.kv("Cash-on-cash (year 1)", _pct(m["cash_on_cash_year1"]))
    if "dscr_year1" in m:
        pdf.kv("DSCR (year 1)", f"{m['dscr_year1']:.2f}")
        pdf.kv("LTV", _pct(m["ltv"]))
        pdf.kv("Debt yield", _pct(m["debt_yield"]))
        pdf.kv("Break-even occupancy", _pct(m["break_even_occupancy"]))

    pdf.section("Cash Flow Projection")
    pdf.table(["Yr", "GPI", "EGI", "Opex", "NOI", "Debt svc", "Cash flow"],
              [10, 30, 30, 30, 30, 30, 30],
              [[str(y.year), _fmt(y.gross_potential_income), _fmt(y.effective_gross_income),
                _fmt(y.operating_expenses), _fmt(y.noi), _fmt(y.debt_service),
                _fmt(y.cash_flow_after_debt)] for y in r.years])

    pdf.section("Exit (Sale) Summary")
    pdf.kv(f"Gross sale price (year {r.sale.year}, at exit cap)", _fmt(r.sale.gross_sale_price, cur))
    pdf.kv("Selling costs", _fmt(r.sale.selling_costs, cur))
    pdf.kv("Loan payoff", _fmt(r.sale.loan_payoff, cur))
    pdf.kv("Net proceeds to equity", _fmt(r.sale.net_sale_proceeds_levered, cur))
    pdf.kv("Est. capital gains tax (single instalment)",
           f"{_fmt(r.disposal_taxes['capital_gains_tax'], cur)} at {_pct(r.disposal_taxes['cgt_rate'])}")

    pdf.section("Scenario Comparison")
    scen = insights.scenarios(r.deal)["scenarios"]
    irr_key = "levered_irr" if r.deal.loan else "unlevered_irr"
    pdf.table(["Scenario", "IRR", "NPV", "Equity multiple", "DSCR (yr 1)"],
              [35, 30, 45, 35, 30],
              [[name.capitalize(), _pct(scen[name].get(irr_key)),
                _fmt(scen[name]["levered_npv"], cur),
                f"{scen[name]['equity_multiple']:.2f}x",
                f"{scen[name]['dscr_year1']:.2f}" if scen[name].get("dscr_year1") else "n/a"]
               for name in ("pessimistic", "base", "optimistic")])

    pdf.section("Sensitivity (one-way, IRR)")
    rows = insights.sensitivity(r.deal)["tornado"]
    pdf.table(["Driver", "Downside IRR", "Base IRR", "Upside IRR", "Swing"],
              [55, 32, 32, 32, 24],
              [[row["param"].replace("loan.", "").replace("_", " "),
                _pct(row["downside"]), _pct(row["base"]), _pct(row["upside"]),
                _pct(row["swing"])] for row in rows])

    pdf.section("Monte Carlo Simulation")
    try:
        mc = insights.simulate(r.deal, n=500, seed=42)
        pdf.kv("Draws", f"{mc['n_effective']} effective of {mc['n']} (seed 42)")
        pdf.kv("Median IRR", _pct(mc["irr"]["median"]))
        pdf.kv("90% IRR interval (p5-p95)", f"{_pct(mc['irr']['p5'])} to {_pct(mc['irr']['p95'])}")
        pdf.kv("Probability IRR < 0", _pct(mc["irr"]["prob_below_zero"]))
        pdf.kv("Probability NPV < 0", _pct(mc["npv"]["prob_below_zero"]))
        pdf.kv("Probability equity multiple < 1x", _pct(mc["equity_multiple"]["prob_below_one"]))
        pdf.note("Gaussian shocks on rent level/growth, vacancy, expenses, "
                 "exit cap rate and loan rate; deterministic for the stated seed.")
    except Exception:
        pdf.note("Simulation unavailable for these inputs.", size=8)

    _market_context(pdf, r)

    pdf.section("Acquisition Costs (Tanzania draft rule pack)")
    for k, v in r.acquisition_costs.items():
        pdf.kv(k.replace("_", " ").capitalize(), _fmt(v, cur))
    pdf.kv("Withholding tax on rent (annual est.)",
           f"{_fmt(r.rental_withholding['annual_withholding'], cur)} at {_pct(r.rental_withholding['rate'])}")

    _compliance_and_disclaimer(pdf, r)
    return pdf


# -------------------------------------------------------------------- bank

def _build_bank(r: AnalysisResult) -> _Report:
    cur = r.deal.currency
    pdf = _start(r, "Collateral Assessment")
    m = r.metrics
    a, _ = to_assumptions(r.deal)

    pdf.section("Collateral & Facility Summary")
    pdf.kv("Indicated purchase price / value basis", _fmt(r.deal.purchase_price, cur))
    pdf.kv("Income value (DCF at discount rate)", _fmt(dcf_value(a), cur))
    pdf.kv("NOI (year 1)", _fmt(m["noi_year1"], cur))
    pdf.kv("Tenure", r.deal.tenure.replace("_", " "))
    if a.loan and "ltv" in m:
        pdf.kv("Facility (loan amount)", _fmt(a.loan.amount, cur))
        pdf.kv("LTV", _pct(m["ltv"]))
        pdf.kv("Debt yield (NOI / loan)", _pct(m["debt_yield"]))
        pdf.kv("DSCR (year 1)", f"{m['dscr_year1']:.2f}")
        pdf.kv("Annual debt service", _fmt(m["annual_debt_service"], cur))
        pdf.kv("Break-even occupancy", _pct(m["break_even_occupancy"]))
    else:
        pdf.note("No facility specified - lending metrics require loan terms.", size=8)

    if a.loan:
        pdf.section("Amortization Profile")
        from finance_core import remaining_balance
        years = sorted({1, 3, 5, r.deal.hold_years})
        pdf.table(["End of year", "Outstanding balance", "Balance / price"],
                  [40, 60, 40],
                  [[str(y),
                    _fmt(remaining_balance(a.loan.amount, a.loan.annual_rate,
                                           a.loan.term_years, y * 12,
                                           interest_only_years=a.loan.interest_only_years), cur),
                    _pct(remaining_balance(a.loan.amount, a.loan.annual_rate,
                                           a.loan.term_years, y * 12,
                                           interest_only_years=a.loan.interest_only_years)
                         / r.deal.purchase_price)]
                   for y in years if y <= a.loan.term_years])

        pdf.section("Stressed Serviceability")
        stresses = [
            ("Base", a),
            ("Rate +200bps", shift(a, "loan.annual_rate", "absolute", 0.02)),
            ("Rent -10%", shift(a, "gross_rent_annual", "relative", -0.10)),
            ("Rate +200bps & rent -10%",
             shift(shift(a, "loan.annual_rate", "absolute", 0.02),
                   "gross_rent_annual", "relative", -0.10)),
        ]
        rows = []
        for label, sa in stresses:
            pf = build_pro_forma(sa)
            sm = pf.metrics
            rows.append([label, f"{sm['dscr_year1']:.2f}", _pct(sm["debt_yield"]),
                         _pct(sm["break_even_occupancy"]),
                         _fmt(pf.years[0].cash_flow_after_debt, cur)])
        pdf.table(["Stress", "DSCR (yr 1)", "Debt yield", "Break-even occ.", "Net cash flow (yr 1)"],
                  [50, 28, 28, 32, 45], rows)
        pdf.note("Stresses re-run the full pro forma with shifted assumptions; "
                 "DSCR below 1.00 means income does not cover debt service.")

    pdf.section("Income Reliability")
    pdf.table(["Yr", "NOI", "Debt service", "DSCR"],
              [15, 55, 55, 30],
              [[str(y.year), _fmt(y.noi, cur), _fmt(y.debt_service, cur),
                f"{(y.noi / y.debt_service):.2f}" if y.debt_service else "n/a"]
               for y in r.years])

    _market_context(pdf, r)
    _compliance_and_disclaimer(pdf, r)
    return pdf


# ------------------------------------------------------------------ valuer

def _build_valuer(r: AnalysisResult) -> _Report:
    cur = r.deal.currency
    pdf = _start(r, "Valuation Workpaper")
    a, acq = to_assumptions(r.deal)
    noi = r.metrics["noi_year1"]

    pdf.note("IVS-aligned workpaper prepared by analysis software as support "
             "material. A statutory valuation must be prepared, signed and "
             "certified by a valuer registered under the Valuation and Valuers "
             "Registration Act, 2016.", size=8)

    pdf.section("Basis of Value")
    pdf.kv("Basis", "Market Value (IVS 104)")
    pdf.kv("Interest valued", r.deal.tenure.replace("_", " "))
    pdf.kv("Valuation date", date.today().isoformat())
    pdf.kv("Currency", cur)

    pdf.section("Approach 1: Income - Direct Capitalization")
    cap = r.deal.exit_cap_rate
    dc_value = direct_capitalization(noi, cap)
    pdf.kv("Stabilized NOI (year 1)", _fmt(noi, cur))
    pdf.kv("Adopted capitalization rate", _pct(cap))
    pdf.kv("Indicated value", _fmt(dc_value, cur))
    pdf.note("Capitalization rate adopted from the deal's exit cap assumption; "
             "substitute a market-derived rate where comparable evidence exists.")

    pdf.section("Approach 2: Income - Discounted Cash Flow")
    dcf = dcf_value(a)
    pdf.kv("Explicit forecast period", f"{r.deal.hold_years} years")
    pdf.kv("Discount rate", _pct(r.deal.discount_rate))
    pdf.kv("Exit capitalization rate", _pct(r.deal.exit_cap_rate))
    pdf.kv("Indicated value", _fmt(dcf, cur))

    pdf.section("Reconciliation")
    rec = reconcile_approaches({"income_direct_cap": dc_value, "income_dcf": dcf})
    pdf.kv("Reconciled opinion-of-value input", _fmt(rec["reconciled_value"], cur))
    pdf.note("Equal weights applied. The sales comparison approach should be "
             "added from the comparables database where sufficient evidence "
             "exists (see /api/comps/stats for the subject's segment).")

    pdf.section("Significant Assumptions (disclosed)")
    d = r.deal
    for label, value in [
        ("Gross rent (year 1, annual)", _fmt(d.gross_rent_annual, cur)),
        ("Vacancy allowance", _pct(d.vacancy_rate)),
        ("Operating expenses (year 1)", _fmt(d.operating_expenses_annual, cur)),
        ("Rent growth", _pct(d.rent_growth)),
        ("Expense growth", _pct(d.expense_growth)),
        ("Selling costs at exit", _pct(d.selling_costs_rate)),
        ("Acquisition costs (rule pack)", _fmt(acq["total"], cur)),
    ]:
        pdf.kv(label, value)

    _market_context(pdf, r)
    _compliance_and_disclaimer(pdf, r)

    pdf.section("Certification")
    pdf.set_font("Helvetica", "", 9)
    for line in ("Valuer name: _______________________________",
                 "Registration no. (VRB): _____________________",
                 "Signature: _________________________________",
                 "Date: ______________________________________"):
        pdf.cell(0, 8, line, new_x="LMARGIN", new_y="NEXT")
    return pdf


_BUILDERS = {"investor": _build_investor, "bank": _build_bank, "valuer": _build_valuer}


def build_pdf(r: AnalysisResult, template: str = "investor") -> bytes:
    if template not in _BUILDERS:
        raise ValueError(f"unknown template {template!r}; choose from {', '.join(TEMPLATES)}")
    return bytes(_BUILDERS[template](r).output())
