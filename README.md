# Ardhi Analytics

Real estate finance & investment analysis platform, Tanzania-first.
Blueprint: [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md).

## What works now

Enter a rental/commercial property deal → one click →

- Full multi-year pro forma (rent growth, vacancy, opex, capex reserves)
- Levered & unlevered IRR, NPV, equity multiple, cash-on-cash, DSCR, LTV,
  debt yield, cap rate, GRM, break-even occupancy
- Amortization-aware mortgage modeling (incl. interest-only phases)
- Exit modeling at a forward exit cap rate with loan payoff
- Tanzania rule pack v1 (draft): stamp duty, CGT single instalment,
  rent withholding tax, transfer procedure checklist, tenure/foreign-buyer
  compliance flags
- One-click PDF investment appraisal report (with scenario & sensitivity sections)
- Scenario comparison (pessimistic / base / optimistic) and one-way + two-way
  sensitivity analysis (`/api/scenarios`, `/api/sensitivity`)
- Valuation engine: income approach (direct cap + DCF) and sales comparison
  with adjustment grids and cross-approach reconciliation (`/api/valuation`)
- Saved deals (SQLite, `/api/deals` CRUD)
- Live market data layer (`/api/market/tz`): World Bank (inflation, GDP
  growth, lending rate) and daily FX, with provenance stamps, a 6-hour cache,
  staleness flags, and curated reference fallback so the app degrades
  gracefully offline
- Comparables database (`/api/comps`): contributed sale/rent observations
  with source attribution, unit-price market stats (median/range per m²),
  dispersion-aware confidence grades, and screening value indications;
  demo seed script with clearly-labeled illustrative data
  (`python -m scripts.seed_comps`)
- Accounts & multi-user (`/api/auth/*`): email+password with PBKDF2 hashing
  and JWT sessions; first user becomes admin. Saved deals are owner-scoped,
  comp contributions are attributed to the signed-in user, comp deletion is
  admin-only; analysis endpoints stay public. Set `ARDHI_JWT_SECRET` in
  production (dev uses a per-process random secret).
- Monte Carlo simulation (`/api/montecarlo`): Gaussian shocks on rent,
  growth, vacancy, expenses, exit cap and loan rate; seedable/deterministic;
  returns IRR/NPV/equity-multiple distributions, downside probabilities
  (P(IRR<0), P(NPV<0), P(EM<1x)) and a histogram — ~0.4s for 1,000 draws
- Simple web UI (no build step; account, live market data, comparables,
  and Monte Carlo histogram cards)

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

## Test it

```bash
cd backend
pytest
```

`finance_core/` is a pure calculation library — no I/O, no framework — with
golden tests verified against Excel and published amortization tables. Treat
it as the crown jewel: every new formula lands with a golden test.

## Layout

```
backend/
  finance_core/   pure finance math (tvm, loans, metrics, pro formas)
  app/            FastAPI API + web UI + PDF reports
    rulepack.py   loads/evaluates jurisdiction rule packs
  rulepacks/      versioned YAML rule packs (tz_v1.yaml — DRAFT)
  tests/          golden + API tests
```

## Important caveats

- **The Tanzania rule pack is a draft.** Every rate (stamp duty, CGT, WHT,
  fees) must be verified against current TRA/Ministry of Lands practice by a
  qualified professional before reliance. The pack carries `verify: true`
  markers and effective dates for this purpose.
- Output is analysis, not legal/tax/investment advice; statutory valuations
  require a registered valuer's sign-off.

## Next (from the blueprint)

Remaining Phase 1: report templates for valuers and banks, Swahili
localization.
