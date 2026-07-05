"""Ardhi Analytics API — Phase 0.

Run from ardhi/backend:  uvicorn app.main:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import insights, rulepack, store
from .analysis import analyze
from .report import build_pdf
from .schemas import AnalysisResult, DealInput, ValuationRequest

app = FastAPI(title="Ardhi Analytics", version="0.1.0",
              description="Real estate finance & investment analysis — Tanzania-first.")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "ardhi", "version": app.version}


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


@app.post("/api/valuation")
def valuation(req: ValuationRequest) -> dict:
    try:
        return insights.valuation(req)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/api/deals")
def save_deal(deal: DealInput) -> dict:
    return store.save_deal(deal.model_dump())


@app.get("/api/deals")
def list_deals() -> list[dict]:
    return store.list_deals()


@app.get("/api/deals/{deal_id}")
def get_deal(deal_id: str) -> dict:
    deal = store.get_deal(deal_id)
    if deal is None:
        raise HTTPException(status_code=404, detail="deal not found")
    return deal


@app.delete("/api/deals/{deal_id}")
def delete_deal(deal_id: str) -> dict:
    if not store.delete_deal(deal_id):
        raise HTTPException(status_code=404, detail="deal not found")
    return {"deleted": deal_id}


@app.post("/api/report")
def report(deal: DealInput) -> Response:
    try:
        result = analyze(deal)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    pdf = build_pdf(result)
    filename = f"{deal.name.replace(' ', '_') or 'deal'}_appraisal.pdf"
    return Response(content=pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
