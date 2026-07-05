"""Rule pack loader and evaluator.

Rule packs are versioned YAML data (rulepacks/<jurisdiction>_v<N>.yaml).
This module loads them and computes jurisdiction-specific transaction costs,
taxes, and compliance checklists for a deal. Adding a jurisdiction means
adding a YAML file — no engine changes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

RULEPACK_DIR = Path(__file__).resolve().parent.parent / "rulepacks"


@lru_cache(maxsize=None)
def load(jurisdiction: str = "tz", version: int = 1) -> dict:
    path = RULEPACK_DIR / f"{jurisdiction.lower()}_v{version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No rule pack for jurisdiction={jurisdiction} v{version}")
    with open(path) as f:
        return yaml.safe_load(f)


def acquisition_costs(pack: dict, price: float) -> dict:
    """Estimated buyer-side transaction costs on acquisition."""
    taxes = pack["taxes"]
    items = {
        "stamp_duty": price * taxes["stamp_duty_transfer"]["rate"],
        "registration_fee": float(taxes["registration_fee"]["amount"]),
        "legal_fees_estimate": price * taxes["legal_fees_estimate"]["rate"],
    }
    items["total"] = sum(items.values())
    return items


def disposal_taxes(pack: dict, sale_price: float, cost_basis: float,
                   resident: bool = True) -> dict:
    """Estimated seller-side taxes on exit (single instalment CGT)."""
    cgt_cfg = pack["taxes"]["capital_gains_single_instalment"]
    rate = cgt_cfg["rate_resident"] if resident else cgt_cfg["rate_non_resident"]
    gain = max(sale_price - cost_basis, 0.0)
    return {
        "gain_on_realization": gain,
        "cgt_rate": rate,
        "capital_gains_tax": gain * rate,
    }


def rental_withholding(pack: dict, gross_annual_rent: float,
                       use: str = "residential") -> dict:
    wht = pack["taxes"]["withholding_tax_rent"]
    rate = wht["rate_residential"] if use == "residential" else wht["rate_commercial"]
    return {"rate": rate, "annual_withholding": gross_annual_rent * rate}


def compliance_checklist(pack: dict, *, buyer_non_resident: bool = False,
                         tenure_customary: bool = False,
                         is_crowdfunded: bool = False) -> list[dict]:
    """Flags applicable to the deal, plus the standard procedure steps."""
    context = {
        "buyer_non_resident": buyer_non_resident,
        "tenure_customary": tenure_customary,
        "is_crowdfunded": is_crowdfunded,
    }
    flags = []
    for flag in pack.get("compliance_flags", []):
        condition = flag.get("condition")
        if condition is None or context.get(condition, False):
            flags.append({"id": flag["id"], "message": flag["message"]})
    return flags


def procedure_steps(pack: dict, procedure: str = "transfer_of_registered_land") -> list[dict]:
    return pack.get("procedures", {}).get(procedure, [])
