"""One-click PDF report generation (fpdf2)."""

from __future__ import annotations

from datetime import date

from fpdf import FPDF

from . import insights
from .schemas import AnalysisResult

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
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*MUTED)
        self.cell(0, 6, "Ardhi Analytics - Investment Appraisal", align="R",
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
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.set_text_color(*INK)

    def kv(self, label: str, value: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*MUTED)
        self.cell(70, 6, _txt(label))
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*INK)
        self.cell(0, 6, _txt(value), new_x="LMARGIN", new_y="NEXT")


def build_pdf(r: AnalysisResult) -> bytes:
    cur = r.deal.currency
    pdf = _Report()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, _txt(r.deal.name), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, f"Jurisdiction: {r.rulepack['jurisdiction']} (rule pack v{r.rulepack['version']}, "
                   f"{r.rulepack['status']}) - {r.deal.use} - {r.deal.hold_years}-year hold",
             new_x="LMARGIN", new_y="NEXT")

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
    headers = ["Yr", "GPI", "EGI", "Opex", "NOI", "Debt svc", "Cash flow"]
    widths = [10, 30, 30, 30, 30, 30, 30]
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, h, border="B")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for y in r.years:
        for val, w in zip([str(y.year), _fmt(y.gross_potential_income), _fmt(y.effective_gross_income),
                           _fmt(y.operating_expenses), _fmt(y.noi), _fmt(y.debt_service),
                           _fmt(y.cash_flow_after_debt)], widths):
            pdf.cell(w, 6, val)
        pdf.ln()

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
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(["Scenario", "IRR", "NPV", "Equity multiple", "DSCR (yr 1)"],
                    [35, 30, 45, 35, 30]):
        pdf.cell(w, 6, h, border="B")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for name in ("pessimistic", "base", "optimistic"):
        s = scen[name]
        dscr_txt = f"{s['dscr_year1']:.2f}" if s.get("dscr_year1") else "n/a"
        for val, w in zip([name.capitalize(), _pct(s.get(irr_key)), _fmt(s["levered_npv"], cur),
                           f"{s['equity_multiple']:.2f}x", dscr_txt],
                          [35, 30, 45, 35, 30]):
            pdf.cell(w, 6, val)
        pdf.ln()

    pdf.section("Sensitivity (one-way, IRR)")
    rows = insights.sensitivity(r.deal)["tornado"]
    pdf.set_font("Helvetica", "B", 8)
    for h, w in zip(["Driver", "Downside IRR", "Base IRR", "Upside IRR", "Swing"],
                    [55, 32, 32, 32, 24]):
        pdf.cell(w, 6, h, border="B")
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for row in rows:
        label = row["param"].replace("loan.", "").replace("_", " ")
        for val, w in zip([label, _pct(row["downside"]), _pct(row["base"]),
                           _pct(row["upside"]), _pct(row["swing"])],
                          [55, 32, 32, 32, 24]):
            pdf.cell(w, 6, val)
        pdf.ln()

    pdf.section("Acquisition Costs (Tanzania draft rule pack)")
    for k, v in r.acquisition_costs.items():
        pdf.kv(k.replace("_", " ").capitalize(), _fmt(v, cur))
    pdf.kv("Withholding tax on rent (annual est.)",
           f"{_fmt(r.rental_withholding['annual_withholding'], cur)} at {_pct(r.rental_withholding['rate'])}")

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
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 4, _txt(r.disclaimer), new_x="LMARGIN", new_y="NEXT")

    return bytes(pdf.output())
