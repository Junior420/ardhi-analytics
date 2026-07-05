"""Deal analysis service: wires DealInput → rule pack → finance_core → result."""

from __future__ import annotations

from dataclasses import asdict

from finance_core.projections import Assumptions, LoanTerms, build_pro_forma

from . import rulepack
from .schemas import AnalysisResult, DealInput, SaleOut, YearRowOut


def to_assumptions(deal: DealInput) -> tuple[Assumptions, dict]:
    """Build engine assumptions (with rule-pack acquisition costs) from a deal."""
    pack = rulepack.load(deal.jurisdiction)
    acq = rulepack.acquisition_costs(pack, deal.purchase_price)

    loan_terms = None
    if deal.loan:
        amount = deal.loan.amount or (deal.loan.ltv or 0) * deal.purchase_price
        if amount <= 0:
            raise ValueError("loan requires either amount or ltv")
        loan_terms = LoanTerms(
            amount=amount,
            annual_rate=deal.loan.annual_rate,
            term_years=deal.loan.term_years,
            interest_only_years=deal.loan.interest_only_years,
        )

    return Assumptions(
        purchase_price=deal.purchase_price,
        acquisition_costs=acq["total"],
        gross_rent_annual=deal.gross_rent_annual,
        vacancy_rate=deal.vacancy_rate,
        operating_expenses_annual=deal.operating_expenses_annual,
        rent_growth=deal.rent_growth,
        expense_growth=deal.expense_growth,
        capex_reserve_rate=deal.capex_reserve_rate,
        hold_years=deal.hold_years,
        exit_cap_rate=deal.exit_cap_rate,
        selling_costs_rate=deal.selling_costs_rate,
        discount_rate=deal.discount_rate,
        loan=loan_terms,
    ), acq


def analyze(deal: DealInput) -> AnalysisResult:
    pack = rulepack.load(deal.jurisdiction)
    assumptions, acq = to_assumptions(deal)
    pf = build_pro_forma(assumptions)

    disposal = rulepack.disposal_taxes(
        pack, pf.sale.gross_sale_price,
        cost_basis=deal.purchase_price + acq["total"],
        resident=deal.buyer_resident,
    )
    wht = rulepack.rental_withholding(pack, deal.gross_rent_annual, deal.use)
    flags = rulepack.compliance_checklist(
        pack,
        buyer_non_resident=not deal.buyer_resident,
        tenure_customary=deal.tenure == "customary",
        is_crowdfunded=deal.is_crowdfunded,
    )

    return AnalysisResult(
        deal=deal,
        metrics=pf.metrics,
        years=[YearRowOut(**asdict(y)) for y in pf.years],
        sale=SaleOut(**asdict(pf.sale)),
        acquisition_costs=acq,
        disposal_taxes=disposal,
        rental_withholding=wht,
        compliance_flags=flags,
        procedure_steps=rulepack.procedure_steps(pack),
        rulepack={"jurisdiction": pack["jurisdiction"], "version": pack["version"],
                  "status": pack["status"], "last_reviewed": str(pack["last_reviewed"])},
        disclaimer=pack["disclaimer"],
    )
