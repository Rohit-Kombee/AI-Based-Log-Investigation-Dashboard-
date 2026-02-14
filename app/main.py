"""FastAPI app: AI Log Investigation Assistant."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, Query

# Structured logging for app (ingest rejections, etc.)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
from fastapi.responses import FileResponse, RedirectResponse

from app import group, ingest, insights, normalize, spikes, validate
from app.db import get_stats, get_recent_logs
from app.generator_service import run_scenario
from app.schema import (
    GroupResponse,
    IngestRequest,
    IngestResponse,
    InsightsResponse,
    NormalizeRequest,
    SpikesResponse,
    ValidateRequest,
    ValidateResponse,
)

app = FastAPI(
    title="AI Log Investigation Assistant",
    description="Log ingestion, normalization, validation, grouping, spike detection, and LLM insights.",
    version="1.0.0",
)


def _build_fallback_openapi():
    """Minimal OpenAPI schema when default generator fails (Python 3.9 + Pydantic bug)."""
    return {
        "openapi": "3.1.0",
        "info": {"title": app.title, "version": app.version, "description": app.description},
        "paths": {
            "/": {"get": {"summary": "Redirect to /docs", "responses": {"302": {"description": "Redirect"}}}},
            "/ingest": {"post": {"summary": "Accept raw logs", "requestBody": {"content": {"application/json": {"schema": {"type": "object", "properties": {"logs": {"type": "array", "items": {"type": "object"}}}}}}}, "responses": {"200": {"description": "IngestResponse"}}}},
            "/normalize": {"post": {"summary": "Convert raw log to canonical", "responses": {"200": {"description": "Canonical log"}}}},
            "/validate": {"post": {"summary": "Validate a log", "responses": {"200": {"description": "ValidateResponse"}}}},
            "/group": {"get": {"summary": "Cluster similar errors", "parameters": [{"name": "service", "in": "query"}, {"name": "level", "in": "query"}, {"name": "limit", "in": "query"}, {"name": "since", "in": "query"}], "responses": {"200": {"description": "GroupResponse"}}}},
            "/spikes": {"get": {"summary": "Detect volume spikes", "parameters": [{"name": "window_minutes", "in": "query"}, {"name": "ratio_threshold", "in": "query"}, {"name": "service", "in": "query"}, {"name": "level", "in": "query"}], "responses": {"200": {"description": "SpikesResponse"}}}},
            "/insights": {"get": {"summary": "LLM summary", "parameters": [{"name": "service", "in": "query"}, {"name": "level", "in": "query"}, {"name": "since", "in": "query"}], "responses": {"200": {"description": "InsightsResponse"}}}},
            "/health": {"get": {"summary": "Health check", "responses": {"200": {"description": "OK"}}}},
        },
        "components": {"schemas": {}},
    }


_original_openapi = app.openapi


def _custom_openapi():
    """Generate OpenAPI schema. Use fallback on Python 3.9 + Pydantic schema bug."""
    try:
        return _original_openapi()
    except AttributeError as e:
        if "_SpecialForm" in str(e) or "replace" in str(e):
            return _build_fallback_openapi()
        raise


app.openapi = _custom_openapi


@app.get("/", include_in_schema=False)
def root():
    """Redirect browser to API docs."""
    return RedirectResponse(url="/docs", status_code=302)


@app.get("/stats", include_in_schema=False)
def get_stats_endpoint():
    """Dashboard: total logs (accepted all time), total_rejected (all time), groups, spikes."""
    stats = get_stats()
    recent = ingest.get_recent_ingests()
    try:
        spikes_resp = spikes.get_spikes(window_minutes=5, baseline_windows=6)
        spikes_count = len(spikes_resp.spikes)
    except Exception:
        spikes_count = 0
    return {
        "total_logs": stats["total_logs"],
        "total_groups": stats["total_groups"],
        "total_rejected": stats.get("total_rejected", 0),
        "spikes_count": spikes_count,
        "recent_ingests": recent,
    }


_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_DASHBOARD_PATH = _STATIC_DIR / "dashboard.html"
_GENERATOR_PATH = _STATIC_DIR / "generator.html"


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    """Serve the log dashboard frontend."""
    if _DASHBOARD_PATH.exists():
        return FileResponse(_DASHBOARD_PATH, media_type="text/html")
    return RedirectResponse(url="/docs", status_code=302)


@app.get("/api/logs", include_in_schema=False)
def api_logs(limit: int = Query(10, ge=1, le=100)):
    """Last N logs in DB (for dashboard drill-down)."""
    return {"logs": get_recent_logs(limit=limit)}


@app.get("/api/groups", include_in_schema=False)
def api_groups(limit: int = Query(10, ge=1, le=100)):
    """First N error groups (for dashboard drill-down)."""
    r = group.get_groups(limit=limit)
    return {"groups": [{"group_id": g.group_id, "count": g.count, "level": g.level, "service": g.service, "sample_message": g.sample_message, "first_seen": g.first_seen.isoformat(), "last_seen": g.last_seen.isoformat()} for g in r.groups]}


@app.get("/api/spikes", include_in_schema=False)
def api_spikes(limit: int = Query(10, ge=1, le=100)):
    """First N spikes (for dashboard drill-down)."""
    r = spikes.get_spikes()
    items = [{"group_id": s.group_id, "service": s.service, "level": s.level, "count": s.count, "ratio": s.ratio, "window_start": s.window_start} for s in r.spikes[:limit]]
    return {"spikes": items}


@app.get("/api/rejected", include_in_schema=False)
def api_rejected(limit: int = Query(10, ge=1, le=100)):
    """Last N rejected log entries (for dashboard drill-down)."""
    return {"rejected": ingest.get_recent_rejected(limit=limit)}


@app.get("/generator", include_in_schema=False)
def generator_page():
    """Serve the generator dashboard (scenario dropdown, send logs)."""
    if _GENERATOR_PATH.exists():
        return FileResponse(_GENERATOR_PATH, media_type="text/html")
    return RedirectResponse(url="/docs", status_code=302)


@app.post("/generator/send", include_in_schema=False)
def generator_send(body: Dict[str, Any]):
    """Run generator scenario: send batches of logs to ingest. Body: scenario, batches?, batch_size?."""
    scenario = body.get("scenario") or "normal"
    batches = int(body.get("batches", 20))
    batch_size = int(body.get("batch_size", 5))
    batches = max(1, min(batches, 100))
    batch_size = max(1, min(batch_size, 50))
    result = run_scenario(scenario, batches=batches, batch_size=batch_size)
    return result


@app.post("/ingest", response_model=IngestResponse)
def post_ingest(body: IngestRequest) -> IngestResponse:
    """Accept raw logs; normalize, validate, and store."""
    accepted, rejected, errors = ingest.process_logs(body.logs)
    return IngestResponse(accepted=accepted, rejected=rejected, errors=errors)


@app.post("/normalize")
def post_normalize(body: NormalizeRequest) -> Dict[str, Any]:
    """Convert a raw log to canonical schema."""
    canonical = normalize.normalize(body.log)
    return canonical.model_dump(mode="json")


@app.post("/validate", response_model=ValidateResponse)
def post_validate(body: ValidateRequest) -> ValidateResponse:
    """Check if a log is valid; return errors if not."""
    valid, err_list = validate.validate_log(body.log)
    return ValidateResponse(valid=valid, errors=err_list)


@app.get("/group", response_model=GroupResponse)
def get_group(
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    since: Optional[str] = Query(None, description="ISO timestamp"),
) -> GroupResponse:
    """Cluster similar errors by fingerprint."""
    return group.get_groups(service=service, level=level, limit=limit, since=since)


@app.get("/spikes", response_model=SpikesResponse)
def get_spikes(
    window_minutes: int = Query(5, ge=1, le=60),
    ratio_threshold: float = Query(2.0, ge=1.0),
    baseline_windows: int = Query(6, ge=1),
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
) -> SpikesResponse:
    """Detect volume spikes per error group."""
    return spikes.get_spikes(
        window_minutes=window_minutes,
        ratio_threshold=ratio_threshold,
        baseline_windows=baseline_windows,
        service=service,
        level=level,
    )


@app.get("/insights", response_model=InsightsResponse)
def get_insights(
    service: Optional[str] = Query(None),
    level: Optional[str] = Query(None),
    since: Optional[str] = Query(None),
) -> InsightsResponse:
    """LLM-generated human-friendly summary of top groups and spikes."""
    return insights.get_insights(service=service, level=level, since=since)


@app.get("/health")
def health() -> Dict[str, str]:
    """Health check."""
    return {"status": "ok"}
