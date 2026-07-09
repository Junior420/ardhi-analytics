"""AI narrative layer — grounded executive summary & risk commentary.

Design rule: the model NEVER invents figures. It receives the already-computed
numbers (metrics, scenarios, Monte Carlo, compliance flags) as structured
context and writes prose that interprets them. Every figure it may cite is in
the prompt; it is instructed to use only those. Output is clearly labelled as
AI-generated in every surface that renders it.

Degrades gracefully: with no ANTHROPIC_API_KEY (and no `anthropic` package),
`available()` is False and callers show a "not configured" message instead of
failing — the rest of the platform is unaffected.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from .analysis import to_assumptions
from .schemas import DealInput

MODEL = os.environ.get("ARDHI_NARRATIVE_MODEL", "claude-opus-4-8")

_SYSTEM = """You are a real estate investment analyst writing for Ardhi \
Analytics, a Tanzania-focused platform. You will be given the fully computed \
results of a deal analysis as JSON: metrics, cash-flow projection, scenarios, \
a Monte Carlo simulation, tax/acquisition costs, and compliance flags.

Write a concise executive summary and risk commentary for a professional \
reader (investor, valuer, or credit officer).

STRICT RULES:
- Use ONLY the numbers present in the provided JSON. Never invent, estimate, \
or extrapolate a figure that is not given. If something is not in the data, \
do not state it.
- Quote figures exactly as given (you may round percentages to one decimal and \
currency to the nearest million TZS for readability, noting "approx." when you do).
- Be direct about weaknesses. If DSCR < 1, cash-on-cash is negative, or the \
probability of missing the hurdle rate is high, say so plainly.
- Do not give legal or tax advice. You may note that compliance items exist \
and must be verified with professionals.
- No preamble ("Here is..."). Start with the recommendation.

Structure your response in GitHub-flavoured markdown with these sections:
## Executive Summary  (3-5 sentences: the verdict and why)
## Return Profile  (what the IRR/NPV/equity multiple/cash-on-cash say)
## Key Risks  (bullet list, most material first, grounded in the sensitivity \
and Monte Carlo data)
## Compliance & Next Steps  (brief; reference the flags)"""


def available() -> bool:
    """True when the narrative layer can actually call the API."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _context(deal: DealInput) -> dict:
    """Assemble the computed facts the model is allowed to cite. Imported
    lazily to avoid a circular import (insights imports narrative indirectly)."""
    from . import insights
    from .analysis import analyze

    result = analyze(deal)
    scenarios = insights.scenarios(deal)["scenarios"]
    sensitivity = insights.sensitivity(deal)["tornado"]
    try:
        mc = insights.simulate(deal, n=500, seed=42)
        mc_ctx = {
            "median_irr": mc["irr"]["median"],
            "irr_p5": mc["irr"]["p5"],
            "irr_p95": mc["irr"]["p95"],
            "prob_irr_below_zero": mc["irr"]["prob_below_zero"],
            "prob_irr_below_discount_rate": mc["irr"]["prob_below_discount_rate"],
            "prob_npv_below_zero": mc["npv"]["prob_below_zero"],
            "prob_equity_multiple_below_1x": mc["equity_multiple"]["prob_below_one"],
        }
    except Exception:
        mc_ctx = None

    return {
        "deal": {
            "name": deal.name, "use": deal.use, "tenure": deal.tenure,
            "currency": deal.currency, "hold_years": deal.hold_years,
            "purchase_price": deal.purchase_price,
            "buyer_resident": deal.buyer_resident,
            "financed": deal.loan is not None,
            "discount_rate_hurdle": deal.discount_rate,
        },
        "metrics": result.metrics,
        "exit": result.sale.model_dump(),
        "scenarios": scenarios,
        "sensitivity_top_drivers": sensitivity[:4],
        "monte_carlo": mc_ctx,
        "acquisition_costs": result.acquisition_costs,
        "disposal_taxes": result.disposal_taxes,
        "compliance_flags": [f["message"] for f in result.compliance_flags],
    }


def generate(deal: DealInput, max_tokens: int = 1200) -> dict:
    """Return {'markdown': ..., 'model': ..., 'grounded_context': ...}.

    Raises RuntimeError if the layer is not configured — callers should check
    available() first (the API endpoint returns 503 in that case)."""
    if not available():
        raise RuntimeError("AI narrative not configured (set ANTHROPIC_API_KEY)")

    import anthropic

    context = _context(deal)
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=max_tokens,
        system=_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                "Here is the computed analysis. Write the narrative using only "
                "these figures.\n\n```json\n"
                + json.dumps(context, indent=2, default=str)
                + "\n```"
            ),
        }],
    )
    text = "".join(block.text for block in message.content if block.type == "text")
    return {
        "markdown": text.strip(),
        "model": message.model,
        "disclaimer": ("AI-generated interpretation, grounded in the computed "
                       "figures above. Not legal, tax, or investment advice."),
    }
