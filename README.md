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
- One-click PDF reports in three templates (`/api/report?template=...`):
  investor appraisal (metrics, projections, scenarios, sensitivity, Monte
  Carlo, market context), bank collateral report (LTV/DSCR/debt yield,
  amortization profile, stressed serviceability, year-by-year DSCR), and
  an IVS-aligned valuer workpaper (basis of value, income approaches,
  disclosed assumptions, certification block)
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
  bulk data ingestion (`/api/ingest/csv`, `/api/ingest/json`, admin-only) —
  a source-agnostic pipeline (normalize → validate → deduplicate → provenance)
  with CSV and partner-JSON adapters, per-row rejection reasons, content-hash
  deduplication (idempotent re-runs), and a dry-run preview; ingested rows are
  stamped `ingest:<source>`. Sample feed: `scripts/sample_partner_feed.csv`.
  Plus an automated valuation model (`/api/avm`) — a pure-Python hedonic
  log-log size regression on the segment's comps, returning a point estimate,
  an asymmetric 95% prediction interval, R²/size-elasticity, and a confidence
  grade; falls back to the median indication when evidence is too thin to
  regress (min 6 comps);
  demo seed script with clearly-labeled illustrative data
  (`python -m scripts.seed_comps`)
- Accounts & multi-user (`/api/auth/*`): email+password with PBKDF2 hashing
  and JWT sessions; first user becomes admin. Saved deals are owner-scoped,
  comp contributions are attributed to the signed-in user, comp deletion is
  admin-only; analysis endpoints stay public. Set `ARDHI_JWT_SECRET` in
  production (dev uses a per-process random secret).
- AI narrative layer (`/api/narrative`): Claude writes an executive summary
  and risk commentary **grounded strictly in the computed figures** — the
  model receives the metrics, scenarios, Monte Carlo probabilities, and
  compliance flags as structured context and is instructed to invent no
  numbers. Off by default; enable by setting `ANTHROPIC_API_KEY` (the UI
  hides the card and the endpoint returns 503 when unconfigured). Model via
  `ARDHI_NARRATIVE_MODEL` (default claude-opus-4-8).
- Monte Carlo simulation (`/api/montecarlo`): Gaussian shocks on rent,
  growth, vacancy, expenses, exit cap and loan rate; seedable/deterministic;
  returns IRR/NPV/equity-multiple distributions, downside probabilities
  (P(IRR<0), P(NPV<0), P(EM<1x)) and a histogram — ~0.4s for 1,000 draws
- Simple web UI (no build step; account, live market data, comparables,
  and Monte Carlo histogram cards) with an English/Kiswahili toggle —
  UI chrome is translated; standard financial jargon (IRR, NPV, DSCR)
  stays in English per Tanzanian professional practice

## Run it

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
# open http://127.0.0.1:8000
```

## Deploy it

### Recommended: free hosting + Supabase PostgreSQL

All storage runs on PostgreSQL when `DATABASE_URL` is set (SQLite remains
the zero-config default for local dev). With Supabase's free tier this
gives a durable production setup at $0/month:

1. Create a project at https://supabase.com/dashboard (sign in with GitHub).
2. Project Settings > Database > copy the **connection string** (URI).
   Any connection mode works (see [`docs/SUPABASE.md`](docs/SUPABASE.md)).
3. Give it to your host as the `DATABASE_URL` environment variable:
   - **Render**: New > Web Service (runtime Docker, plan Free) > add env vars
     `DATABASE_URL` and `ARDHI_JWT_SECRET`. No disk needed - the app is
     stateless with Postgres. (The blueprint below also prompts for it.)
   - **Cloudflare**: `npx wrangler secret put DATABASE_URL` before deploying.

Tables are created automatically on first request. CI runs the full test
suite against both SQLite and PostgreSQL 16.


The repo ships a `Dockerfile` and a Render blueprint (`render.yaml`):

1. On [Render](https://render.com): **New > Blueprint**, point it at this
   repository. The blueprint provisions a web service with a 1 GB persistent
   disk mounted at `/data` (SQLite lives there) and a generated
   `ARDHI_JWT_SECRET`.
2. Any Docker host works too:
   `docker build -t ardhi . && docker run -p 8000:8000 -v ardhi-data:/data -e ARDHI_JWT_SECRET=<secret> ardhi`

### Cloudflare (Containers)

The repo also ships a Cloudflare Containers setup (`wrangler.jsonc` +
`cloudflare/index.mjs`). Requires the Workers Paid plan ($5/mo) and Docker
running locally to build the image:

```bash
npm install
npx wrangler login
npx wrangler secret put ARDHI_JWT_SECRET   # paste a long random string
npx wrangler deploy
```

**Caveat:** container disks are ephemeral - SQLite data resets when the
container sleeps or redeploys. Use Render (above) for durable data, or ask
for the D1 storage migration to make Cloudflare fully persistent.

Environment variables: `ARDHI_JWT_SECRET` (required in production),
`ARDHI_DATA_DIR` (defaults to `backend/data` locally, `/data` in the image),
`PORT` (injected by the platform). Health check: `GET /api/health`.
CI (GitHub Actions) runs the full test suite on every push and PR.

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

Phase 1 is complete; Phase 2 is underway (deployment configs and the AI
narrative layer are in). Remaining Phase 2+: portfolio tracking with alerts,
and — after CMSA legal structuring — the crowdfunding module.
