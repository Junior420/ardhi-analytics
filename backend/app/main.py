"""Ardhi Analytics API.

Run from backend/:  uvicorn app.main:app --reload

Auth model: analysis endpoints (analyze, scenarios, sensitivity, valuation,
report, market, rule packs) and comp reads are public. Anything tied to an
identity — saved deals, contributing or deleting comps — requires a bearer
token from /api/auth/login.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from connectors import market_snapshot

from . import (auth, avm_service, comps, ingest, insights, narrative,
               portfolio, rulepack, store)
from .analysis import analyze
from .report import build_pdf
from .schemas import (
    AnalysisResult, CompIn, Credentials, DealInput, IndicateRequest,
    ActualIn, AvmRequest, IngestJsonRequest, MonteCarloRequest, ValuationRequest,
)

app = FastAPI(title="Ardhi Analytics", version="0.1.0",
              description="Real estate finance & investment analysis — Tanzania-first.")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "ardhi", "version": app.version}


@app.post("/api/auth/register")
def register(creds: Credentials) -> dict:
    try:
        user = auth.register(creds.email, creds.password)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"user": user, "access_token": auth.create_token(user), "token_type": "bearer"}


@app.post("/api/auth/login")
def login(creds: Credentials) -> dict:
    user = auth.authenticate(creds.email, creds.password)
    if user is None:
        raise HTTPException(status_code=401, detail="invalid email or password")
    return {"user": user, "access_token": auth.create_token(user), "token_type": "bearer"}


@app.get("/api/auth/me")
def me(user: dict = Depends(auth.current_user)) -> dict:
    return user


@app.get("/api/market/{jurisdiction}")
def market(jurisdiction: str) -> dict:
    try:
        return market_snapshot(jurisdiction)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/api/rulepack/{jurisdiction}")
def get_rulepack(jurisdiction: str) -> dict:
    try:
        return rulepack.load(jurisdiction)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/api/analyze", response_model=AnalysisResult)
def analyze_deal(deal: DealInput) -> AnalysisResult:
    try:
        return analyze(deal)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/scenarios")
def scenarios(deal: DealInput) -> dict:
    try:
        return insights.scenarios(deal)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/sensitivity")
def sensitivity(deal: DealInput) -> dict:
    try:
        return insights.sensitivity(deal)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/montecarlo")
def montecarlo(req: MonteCarloRequest) -> dict:
    try:
        return insights.simulate(req.deal, n=req.n, seed=req.seed)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/narrative/status")
def narrative_status() -> dict:
    return {"available": narrative.available(), "model": narrative.MODEL}


@app.post("/api/narrative")
def narrative_endpoint(deal: DealInput) -> dict:
    if not narrative.available():
        raise HTTPException(status_code=503,
                            detail="AI narrative not configured (set ANTHROPIC_API_KEY)")
    try:
        return narrative.generate(deal)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"narrative generation failed: {e}")


@app.post("/api/valuation")
def valuation(req: ValuationRequest) -> dict:
    try:
        return insights.valuation(req)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))


def _owned_deal(deal_id: str, user: dict) -> dict:
    deal = store.get_deal(deal_id)
    if deal is None or (deal["owner_id"] != user["id"] and user["role"] != "admin"):
        # 404 for both cases: don't reveal other users' deal ids
        raise HTTPException(status_code=404, detail="deal not found")
    return deal


@app.get("/api/portfolio/summary")
def portfolio_summary(user: dict = Depends(auth.current_user)) -> dict:
    return portfolio.summary(user["id"], user["role"] == "admin")


@app.get("/api/portfolio/alerts")
def portfolio_alerts(rate_bps: float = 100, rent_pct: float = -10,
                     user: dict = Depends(auth.current_user)) -> dict:
    return portfolio.alerts(user["id"], user["role"] == "admin", rate_bps, rent_pct)


@app.post("/api/deals/{deal_id}/actuals")
def add_actual(deal_id: str, actual: ActualIn,
               user: dict = Depends(auth.current_user)) -> dict:
    _owned_deal(deal_id, user)  # 404 if not the owner's deal
    return portfolio.record_actual(deal_id, user["id"], actual.year,
                                   actual.gross_rent_actual, actual.opex_actual,
                                   actual.note)


@app.get("/api/deals/{deal_id}/actuals")
def deal_variance(deal_id: str, user: dict = Depends(auth.current_user)) -> dict:
    owned = _owned_deal(deal_id, user)
    return portfolio.variance(deal_id, owned["payload"], user["id"])


@app.post("/api/deals")
def save_deal(deal: DealInput, user: dict = Depends(auth.current_user)) -> dict:
    return store.save_deal(deal.model_dump(), owner_id=user["id"])


@app.get("/api/deals")
def list_deals(user: dict = Depends(auth.current_user)) -> list[dict]:
    return store.list_deals(None if user["role"] == "admin" else user["id"])


@app.get("/api/deals/{deal_id}")
def get_deal(deal_id: str, user: dict = Depends(auth.current_user)) -> dict:
    return _owned_deal(deal_id, user)["payload"]


@app.delete("/api/deals/{deal_id}")
def delete_deal(deal_id: str, user: dict = Depends(auth.current_user)) -> dict:
    _owned_deal(deal_id, user)
    store.delete_deal(deal_id)
    return {"deleted": deal_id}


@app.post("/api/comps")
def add_comp(comp: CompIn, user: dict = Depends(auth.current_user)) -> dict:
    record = comp.model_dump()
    record["contributor"] = user["email"]
    return comps.add_comp(record)


@app.get("/api/comps")
def list_comps(kind: str | None = None, use: str | None = None,
               region: str | None = None, district: str | None = None,
               since: str | None = None, limit: int = 100) -> list[dict]:
    return comps.list_comps({"kind": kind, "use": use, "region": region,
                             "district": district, "since": since}, limit)


@app.get("/api/comps/stats")
def comp_stats(kind: str | None = None, use: str | None = None,
               region: str | None = None, district: str | None = None,
               since: str | None = None) -> dict:
    return comps.stats({"kind": kind, "use": use, "region": region,
                        "district": district, "since": since})


def _require_admin(user: dict) -> None:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="ingestion is admin-only")


@app.post("/api/ingest/json")
def ingest_json(req: IngestJsonRequest, user: dict = Depends(auth.current_user)) -> dict:
    _require_admin(user)
    try:
        return ingest.from_json(req.records, req.source, req.dry_run, req.mapping)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/ingest/csv")
def ingest_csv(source: str, dry_run: bool = True,
               file: UploadFile = File(...),
               user: dict = Depends(auth.current_user)) -> dict:
    _require_admin(user)
    try:
        text_data = file.file.read().decode("utf-8-sig")
        return ingest.from_csv(text_data, source, dry_run)
    except (ValueError, TypeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/avm")
def avm_estimate(req: AvmRequest) -> dict:
    filters = {"kind": req.kind, "use": req.use, "region": req.region,
               "district": req.district, "since": req.since}
    try:
        return avm_service.estimate(req.area_sqm, filters)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/comps/indicate")
def indicate(req: IndicateRequest) -> dict:
    filters = {"kind": req.kind, "use": req.use, "region": req.region,
               "district": req.district, "since": req.since}
    try:
        return comps.indicate_value(req.area_sqm, filters)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.delete("/api/comps/{comp_id}")
def delete_comp(comp_id: str, user: dict = Depends(auth.current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="only admins can delete comparables")
    if not comps.delete_comp(comp_id):
        raise HTTPException(status_code=404, detail="comparable not found")
    return {"deleted": comp_id}


@app.post("/api/report")
def report(deal: DealInput, template: str = "investor") -> Response:
    try:
        result = analyze(deal)
        pdf = build_pdf(result, template=template)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    filename = f"{deal.name.replace(' ', '_') or 'deal'}_{template}.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
