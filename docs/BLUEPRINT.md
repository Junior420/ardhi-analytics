# Real Estate Finance & Investment Analysis Platform — Project Blueprint

> Working name: **Ardhi Analytics** (Swahili: *ardhi* = land). Rename freely.
>
> One-click, end-to-end real estate finance analysis: you feed it a property,
> a deal, or a portfolio — it fetches live market data, runs the full analysis
> stack (valuation, financing, projections, risk, compliance), and produces a
> professional, regulator-ready report. Tanzania-first, built to expand to any
> jurisdiction.

---

## 1. Vision

A single platform where an investor, valuer, bank, or developer can:

1. **Describe an asset or deal** (property, land parcel, development project,
   crowdfunding offering, or portfolio).
2. **Click "Analyze"** — the system pulls live data (interest rates, FX,
   inflation, comparable sales/rents, construction costs), runs every standard
   analysis, checks the deal against the laws and procedures of the selected
   jurisdiction (Tanzania first), and interprets the results.
3. **Receive a decision-grade report** — valuation, financial projections,
   investment recommendation, risk flags, and compliance checklist — as PDF,
   web dashboard, and machine-readable JSON.

Design principle: **the analysis engine is jurisdiction-agnostic; the rules,
taxes, procedures, and report formats are pluggable per country.** Tanzania is
the first and most complete plugin, not a hard-coded assumption.

---

## 2. Who it serves

| User | What they get |
|---|---|
| Individual investors | Buy/hold/sell decisions, rental yield, mortgage affordability |
| Registered valuers | IVS-compliant valuation workpapers and reports |
| Banks & MFIs | Collateral valuation, DSCR/LTV checks, mortgage portfolio analytics |
| Developers | Feasibility studies, construction pro formas, residual land value |
| Crowdfunding platforms & their investors | Offering analysis, projected distributions, regulatory checks |
| Land administrators / advisors | Tenure due diligence, land rent, conversion procedures |
| Institutional / REIT investors | Portfolio analytics, fund-level metrics |

---

## 3. Functional modules

### 3.1 Deal & Property Intake
- Structured intake for: residential, commercial, industrial, agricultural
  land, mixed-use, development projects, and crowdfunded offerings.
- Tenure capture (critical in Tanzania): Granted Right of Occupancy (33/66/99
  years), Customary Right of Occupancy, derivative rights, leaseholds; title
  number, plot/block, land rent status.
- Document upload (title deeds, sale agreements, drawings) with OCR-assisted
  field extraction.

### 3.2 Valuation Engine (three classical approaches + automated)
- **Income approach**: direct capitalization and DCF (explicit forecast +
  terminal value).
- **Sales comparison approach**: comparable selection, adjustment grid,
  reconciliation.
- **Cost approach**: replacement cost, depreciation, land value.
- **Automated Valuation Model (AVM)**: hedonic regression / ML on the
  comparables database, with confidence intervals — used as a cross-check,
  never the sole basis (aligns with valuation standards).
- Output aligned to **International Valuation Standards (IVS)** and the
  Tanzanian **Valuation and Valuers Registration Act, 2016** report
  requirements (a registered valuer must sign statutory valuations — the
  platform prepares, the professional certifies).

### 3.3 Investment & Financial Analysis Engine
The core calculation library. Pure, deterministic, unit-tested functions:
- Returns: NPV, IRR/XIRR, MIRR, equity multiple, cash-on-cash, payback.
- Income metrics: NOI, cap rate, gross rent multiplier, operating expense
  ratio, break-even occupancy.
- Debt metrics: DSCR, LTV, LTC, debt yield, amortization schedules (fixed,
  variable, balloon, interest-only), refinance modeling.
- Development: residual land value, profit-on-cost, construction draw
  schedules, S-curve cost phasing.
- Portfolio: weighted returns, concentration, correlation, fund waterfalls
  (preferred return, catch-up, promote/carry) — needed for crowdfunding SPVs.
- Multi-currency: TZS-native with USD/EUR parallel reporting; FX from live
  Bank of Tanzania rates.

### 3.4 Projections & Scenario Engine
- 1–30 year pro formas: rent rolls, vacancy, expense growth, capex reserves.
- Scenario manager: base / optimistic / pessimistic side by side.
- **Sensitivity analysis**: tornado charts on rent, exit cap, interest rate,
  construction cost, occupancy.
- **Monte Carlo simulation**: distribution of IRR/NPV, probability of loss,
  VaR-style downside metrics.
- Inflation-aware: NBS CPI feeds real vs nominal projections.

### 3.5 Compliance & Legal Procedure Engine (the differentiator)
A **rules-as-data** engine: each jurisdiction ships a versioned rule pack
(YAML/JSON + effective dates), evaluated against the deal. Tanzania pack v1:

- **Land tenure**: Land Act 1999 (Cap 113), Village Land Act 1999 (Cap 114),
  Land Regulations; occupancy term limits; land rent obligations; change-of-use
  and disposition consent procedures (Commissioner for Lands).
- **Foreign ownership**: foreigners generally hold land only via Tanzania
  Investment Centre (TIC) derivative rights for investment purposes — the
  engine flags deal structures accordingly.
- **Taxes & duties** (rates stored as dated reference data, not hard-coded):
  stamp duty on transfers, capital gains tax on disposal, withholding tax on
  rent, VAT on commercial leases where applicable, local property tax (TRA
  collected), land rent.
- **Transaction procedure checklists**: official search, valuation
  requirement, consent to transfer, registration (Registrar of Titles),
  mortgage registration; estimated timelines and fees.
- **Mortgage & banking**: Mortgage Financing (Special Provisions) Act 2008,
  Bank of Tanzania prudential context for lender-facing outputs.
- **Crowdfunding/securities**: Capital Markets and Securities Authority (CMSA)
  regulatory perimeter for offerings — flags when a structure likely
  constitutes a public offer needing approval/licensing.
- **AML/KYC hooks**: for any money-touching flows (Anti-Money Laundering Act).

Every compliance output carries: rule citation, effective date, confidence,
and a "verify with counsel" disclaimer. **The platform informs; it does not
give legal advice.**

Other jurisdictions later = new rule packs (Kenya, Uganda, Rwanda are natural
next steps — similar land/tax structures, EAC market).

### 3.6 Live Data Layer
Connector framework (each source = an adapter with caching, retry, and
provenance stamping):

| Data | Source (Tanzania) | Method |
|---|---|---|
| Policy/interest rates, FX, T-bill yields | Bank of Tanzania | Published data/scraper → API |
| CPI, GDP, housing statistics | National Bureau of Statistics | Data portal |
| Listings / asking prices & rents | Local portals (Kupatana, Zoom Tanzania, agency feeds), partner agreements | Scrapers + partner APIs |
| Comparable sales | Internal DB seeded from partner valuers/banks (the moat) | Contributed data |
| Construction costs | Quantity-surveyor indices, NCC data | Curated dataset, updated quarterly |
| Global benchmarks | World Bank, IMF, Numbeo, REIT indices | Public APIs |
| Geospatial | OpenStreetMap, satellite basemaps; Ministry of Lands cadastre if/when accessible | Tiles + geocoding |

Every number in a report is traceable: *source, timestamp, transformation*.
Stale data is flagged, never silently used.

### 3.7 Crowdfunding Module ("crowdfare")
- Sponsors create offerings: asset, raise target, min ticket, fee structure,
  waterfall.
- The analysis engine auto-generates the offering's financials: projected
  distributions per TZS 100k invested, IRR ranges, risk grade (A–E scoring
  model), sensitivity.
- Investor dashboard: commitments, distributions, portfolio view.
- Compliance gating via the CMSA rules in §3.5.
- **Phase-2/3 feature** — start with *analysis of* crowdfunded deals, add
  *transacting* (escrow, payments via M-Pesa/Tigo Pesa/bank) only once
  licensing is sorted.

### 3.8 One-Click Report Engine
- Templated, branded reports: **Investment Appraisal**, **Valuation Report
  (IVS/Tanzanian format)**, **Bank Collateral Report**, **Feasibility Study**,
  **Crowdfunding Offering Memo**, **Portfolio Review**.
- HTML → PDF (WeasyPrint/Playwright), plus DOCX export for valuers who edit,
  plus JSON for system-to-system use.
- **AI interpretation layer**: an LLM (Claude API) writes the narrative —
  executive summary, market commentary, risk discussion — *strictly grounded
  in the computed numbers and retrieved data* (the model never invents
  figures; it explains them). Every AI-written section is labeled.

### 3.9 Tracking & Monitoring
- Portfolio tracker: actuals vs projections, variance alerts.
- Market watch: rate changes, FX moves, new comparables in an area →
  notifications ("BOT rate +100bps: your Deal X DSCR falls to 1.15").
- Scheduled re-analysis (monthly re-run of every saved deal).

---

## 4. Architecture

**Start as a modular monolith, split later.** Matches your existing stack
(FastAPI + PostgreSQL from Volta Store) so you build on what you know.

```
┌──────────────────────────────────────────────────────┐
│  Frontend: React/Next.js (PWA — offline-tolerant,    │
│  mobile-first for the Tanzanian market)              │
└───────────────▲──────────────────────────────────────┘
                │ REST/JSON (FastAPI)
┌───────────────┴──────────────────────────────────────┐
│  API layer: auth (JWT), orgs/teams, RBAC, audit log  │
├──────────────────────────────────────────────────────┤
│  Domain services                                     │
│   • deals & properties   • valuation                 │
│   • projections/scenarios• compliance (rule packs)   │
│   • reports              • crowdfunding              │
│   • portfolio/tracking   • notifications             │
├──────────────────────────────────────────────────────┤
│  finance_core (pure Python lib — no I/O)             │
│   NPV/IRR/DCF/amortization/waterfalls/Monte Carlo    │
│   → exhaustively unit-tested vs Excel/HP-12C results │
├──────────────────────────────────────────────────────┤
│  Data platform                                       │
│   • connector framework (BOT, NBS, portals, WB/IMF)  │
│   • Celery/APScheduler jobs, Redis cache             │
│   • provenance store (source, timestamp, license)    │
├──────────────────────────────────────────────────────┤
│  PostgreSQL (+PostGIS for parcels/geo)  •  S3 files  │
└──────────────────────────────────────────────────────┘
```

Key decisions:
- **`finance_core` as a standalone library** is the heart. Every formula is a
  pure function with golden tests. Everything else can be rewritten; this
  cannot be wrong.
- **Rule packs as versioned data** (not code) so a lawyer/analyst can review
  them, and jurisdictions can be added without touching the engine.
- **PostGIS** from day one — location is the product in real estate.
- **Money as Decimal/integer minor units**, never floats, everywhere.
- **Audit log everything** — valuations and investment advice attract
  disputes; you want an immutable record of inputs → outputs → data versions.
- Deploy on Render/Railway/Fly initially (you already use Render); move to a
  cloud region with African presence (AWS Cape Town) as latency/data-residency
  matters grow.

---

## 5. Phased roadmap

**Phase 0 — Foundation (4–6 weeks)**
- Repo scaffold, `finance_core` with the full metrics set + golden tests,
  deal/property models, auth, basic React shell.
- *Milestone: enter a rental property, get NPV/IRR/cap rate/DSCR + a simple
  PDF.*

**Phase 1 — Tanzania MVP (2–3 months)**
- Valuation engine (income + sales comparison), pro forma builder, scenario &
  sensitivity analysis, Tanzania rule pack v1 (tenure, taxes, procedures),
  report engine with 3 templates, BOT/NBS data connectors, manual comparables
  DB with contribution workflow.
- *Milestone: a valuer or investor produces a decision-grade Tanzanian report
  in one click. This is the sellable MVP.*

**Phase 2 — Intelligence & data depth (2–3 months)**
- Listing scrapers + partner data agreements, AVM v1, Monte Carlo, AI
  narrative layer, portfolio tracker with alerts, DOCX export, mobile polish.

**Phase 3 — Crowdfunding & ecosystem (3–4 months)**
- Offering builder + waterfall engine, investor dashboards, CMSA compliance
  gating, payments integration (M-Pesa etc.) *after* legal structuring; bank
  API for collateral revaluation.

**Phase 4 — Multi-jurisdiction (ongoing)**
- Kenya/Uganda/Rwanda rule packs, multi-currency portfolios, localization
  (Swahili/English UI from Phase 1 — both are official).

---

## 6. Monetization

1. **SaaS tiers**: Free (3 analyses/mo) → Pro for investors/valuers
   (per-seat) → Enterprise for banks/funds (API, white-label reports, SSO).
2. **Pay-per-report** for occasional users (mobile-money friendly).
3. **Data products**: market indices, comparables access (the contributed
   comps database becomes the moat).
4. **Crowdfunding take-rate** (Phase 3+): % of funds raised / AUM fee.
5. **Bank integrations**: per-valuation API pricing for collateral checks.

---

## 7. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Sparse/opaque Tanzanian transaction data | Start with contributed data (partner valuers/banks get free access for data); AVM only as cross-check; always show confidence levels |
| Regulatory liability (valuation/investment/legal advice) | Reports are "analysis, not advice"; statutory valuations require a registered valuer's sign-off; legal review of all rule packs; strong disclaimers + audit trail |
| Crowdfunding licensing complexity | Ship analysis-only first; engage CMSA before touching investor money |
| Laws/rates change | Rule packs versioned with effective dates + a review calendar; every report states the rule-pack version used |
| Scraper fragility / data licensing | Prefer partner APIs and public statistics; provenance stamps; graceful degradation to cached data with staleness flags |
| Scope explosion (this doc is huge) | The phase gates above; nothing in Phase 3 starts before Phase 1 ships |

---

## 8. Immediate next steps

1. ~~Create a dedicated repository~~ — done: this repo (`ardhi-analytics`).
2. ~~Scaffold Phase 0~~ — done: `finance_core` + tests, Tanzania rule pack v1
   (draft), API, UI, PDF reports, scenarios/sensitivity, valuation engine.
3. Next: collect the Tanzania reference data (current tax rates, land
   procedures, BOT data endpoints) into the first rule pack draft, and line up
   one pilot user (a valuer or a bank credit officer) to shape the report
   templates.
