"""
Stage 11 + 12: FastAPI application with structured logging, request-ID
middleware, global exception handlers, and a real health check.

Start locally:
  myenv/Scripts/uvicorn app.main:app --reload --port 8000

Interactive docs:  http://localhost:8000/docs
"""

from __future__ import annotations

# ── Path bootstrap ─────────────────────────────────────────────────────────
# Bare imports (database, models, crud …) work whether uvicorn is launched as
#   uvicorn app.main:app   (from project root)
#   uvicorn main:app       (from inside app/)
import sys as _sys
from pathlib import Path as _Path

_APP_DIR = _Path(__file__).parent.resolve()
if str(_APP_DIR) not in _sys.path:
    _sys.path.insert(0, str(_APP_DIR))
# ──────────────────────────────────────────────────────────────────────────

import json
import os
import time
import tempfile
import traceback
import urllib.error
import urllib.request
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

# ── Stage imports (models must load before init_db) ────────────────────────
import models  # noqa: F401 — registers CardVersionRecord with Base.metadata
from database import get_db, init_db
from crud import (
    get_card_by_version,
    get_card_versions,
    get_latest_card,
    list_all_agents,
    save_card,
)
from completeness import check_card
from document import export_html, export_json
from generator import generate_agent_card
from logging_config import setup_logging
from regulation_mapper import annotate_card
from schema import AgentCard

# ── Logger ─────────────────────────────────────────────────────────────────
logger = setup_logging(level=os.getenv("LOG_LEVEL", "INFO"))


# ══════════════════════════════════════════════════════════════════════════════
# Stage 12 — Request-ID middleware
# ══════════════════════════════════════════════════════════════════════════════

class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Attaches a short UUID to every request:
      - stored on request.state.request_id
      - echoed in the X-Request-ID response header
      - included in every structured log line for that request
    Also emits one JSON log line per request with method, path, status,
    and wall-clock duration.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id
        t0 = time.monotonic()

        try:
            response = await call_next(request)
        except Exception as exc:
            # Log unhandled exceptions that escape route handlers
            logger.error(
                "unhandled exception in middleware",
                extra={
                    "request_id": request_id,
                    "path": request.url.path,
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                },
            )
            raise

        duration_ms = round((time.monotonic() - t0) * 1000)
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method":      request.method,
                "path":        request.url.path,
                "query":       str(request.query_params) or None,
                "status":      response.status_code,
                "duration_ms": duration_ms,
            },
        )
        return response


# ══════════════════════════════════════════════════════════════════════════════
# Lifespan — startup / shutdown
# ══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup: initialising database tables")
    try:
        init_db()
        logger.info("startup: database tables ready")
    except Exception as exc:
        logger.error("startup: database init warning", extra={"error": str(exc)})
    logger.info("startup: complete — service ready")
    yield
    logger.info("shutdown: service stopping")


# ══════════════════════════════════════════════════════════════════════════════
# App instance
# ══════════════════════════════════════════════════════════════════════════════

app = FastAPI(
    title="Agent Compliance Card Generator",
    description=(
        "Generates structured, regulation-aligned compliance cards for AI agents "
        "from an agent config, tool manifest, and run trace. "
        "Cards are persisted as immutable versions in Postgres and can be rendered "
        "as structured JSON or a human-readable HTML document."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(RequestIDMiddleware)


# ══════════════════════════════════════════════════════════════════════════════
# Stage 12 — Global exception handlers
# ══════════════════════════════════════════════════════════════════════════════

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """Pydantic / FastAPI validation errors → 422 with structured detail."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.warning(
        "validation error",
        extra={"request_id": request_id, "errors": exc.errors()},
    )
    return JSONResponse(
        status_code=422,
        headers={"X-Request-ID": request_id},
        content={
            "detail": "Request validation failed",
            "errors": exc.errors(),
            "request_id": request_id,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """FastAPI HTTP exceptions — log them and re-emit with request_id."""
    request_id = getattr(request.state, "request_id", "unknown")
    level = logger.warning if exc.status_code < 500 else logger.error
    level(
        "http exception",
        extra={"request_id": request_id, "status": exc.status_code, "detail": exc.detail},
    )
    return JSONResponse(
        status_code=exc.status_code,
        headers={"X-Request-ID": request_id},
        content={"detail": exc.detail, "request_id": request_id},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all for any unhandled exception — returns 500 instead of a raw traceback."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "unhandled exception",
        extra={
            "request_id": request_id,
            "error_type": type(exc).__name__,
            "error":      str(exc),
            "traceback":  traceback.format_exc(),
        },
    )
    return JSONResponse(
        status_code=500,
        headers={"X-Request-ID": request_id},
        content={
            "detail": "An internal server error occurred.",
            "request_id": request_id,
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# Stage 12 helpers — real health checks
# ══════════════════════════════════════════════════════════════════════════════

def _check_database(db: Session) -> dict:
    """Execute SELECT 1 and measure round-trip latency to Neon."""
    t0 = time.monotonic()
    try:
        db.execute(text("SELECT 1"))
        return {
            "status": "ok",
            "latency_ms": round((time.monotonic() - t0) * 1000),
        }
    except Exception as exc:
        return {
            "status": "error",
            "detail": str(exc)[:120],
            "latency_ms": round((time.monotonic() - t0) * 1000),
        }


def _check_groq() -> dict:
    """
    Verify the GROQ_API_KEY is set and accepted by the Groq API using the Groq SDK.
    """
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        return {"status": "key_missing"}

    t0 = time.monotonic()
    try:
        import groq
        client = groq.Groq(api_key=key, timeout=8.0)
        client.models.list()
        return {
            "status": "ok",
            "latency_ms": round((time.monotonic() - t0) * 1000),
        }
    except Exception as exc:
        err_msg = str(exc)
        status = "invalid_key" if "401" in err_msg or "authentication" in err_msg.lower() else "error"
        return {
            "status": status,
            "detail": err_msg[:120],
            "latency_ms": round((time.monotonic() - t0) * 1000),
        }


# ══════════════════════════════════════════════════════════════════════════════
# GET /health   (Stage 12 — real checks)
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/health", tags=["Operations"], summary="Liveness and dependency check")
def health(
    request: Request,
    full: bool = Query(False, description="Run deep DB and Groq connectivity checks"),
    db: Session = Depends(get_db),
):
    """
    Fast liveness check by default (<1ms).
    Pass ?full=true to run full database ping and Groq API validation.
    """
    request_id = getattr(request.state, "request_id", "unknown")

    if not full:
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "request_id": request_id,
                "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )

    db_check   = _check_database(db)
    groq_check = _check_groq()

    overall = (
        "healthy"
        if db_check["status"] == "ok" and groq_check["status"] == "ok"
        else "degraded"
    )

    body = {
        "status":     overall,
        "request_id": request_id,
        "checks": {
            "database": db_check,
            "llm":      groq_check,
        },
        "time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    logger.info(
        "health check",
        extra={"request_id": request_id, "overall": overall,
               "db": db_check["status"], "groq": groq_check["status"]},
    )
    return JSONResponse(
        status_code=200 if overall == "healthy" else 503,
        content=body,
    )


# ══════════════════════════════════════════════════════════════════════════════
# POST /agents/cards/generate
# ══════════════════════════════════════════════════════════════════════════════

@app.post(
    "/agents/cards/generate",
    tags=["Cards"],
    summary="Generate and persist a new compliance card",
    status_code=201,
)
def generate(
    request: Request,
    config_file:   UploadFile = File(..., description="agent_config.json"),
    manifest_file: UploadFile = File(..., description="tool_manifest.json"),
    trace_file:    UploadFile = File(..., description="run_trace.json"),
    db: Session = Depends(get_db),
):
    """
    Upload three JSON files to generate a compliance card.
    Parses inputs, calls the LLM for narrative fields, checks completeness,
    persists as a new immutable version in Postgres, returns full card + report.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.info("generate: reading uploaded files", extra={"request_id": request_id})

    config_bytes   = config_file.file.read()
    manifest_bytes = manifest_file.file.read()
    trace_bytes    = trace_file.file.read()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "config.json").write_bytes(config_bytes)
        (tmp / "manifest.json").write_bytes(manifest_bytes)
        (tmp / "trace.json").write_bytes(trace_bytes)

        logger.info("generate: calling LLM", extra={"request_id": request_id})
        try:
            card = generate_agent_card(
                config_path=tmp / "config.json",
                manifest_path=tmp / "manifest.json",
                trace_path=tmp / "trace.json",
            )
        except (ValueError, FileNotFoundError) as exc:
            logger.warning("generate: invalid input", extra={"request_id": request_id, "error": str(exc)})
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            logger.error("generate: LLM error", extra={"request_id": request_id, "error": str(exc)})
            raise HTTPException(status_code=500, detail=f"Card generation failed: {exc}")

    record = save_card(db, card)
    report = check_card(card)

    logger.info(
        "generate: card saved",
        extra={
            "request_id": request_id,
            "agent_id":   card.agent_id,
            "version":    record.version,
            "complete":   report.is_complete,
        },
    )

    return {
        "agent_id":     card.agent_id,
        "agent_name":   card.agent_name,
        "version":      record.version,
        "db_record_id": record.id,
        "completeness": {
            "is_complete": report.is_complete,
            "issue_count": len(report.issues),
            "issues": [
                {"field": i.field, "type": i.issue_type, "message": i.message}
                for i in report.issues
            ],
        },
        "card": json.loads(export_json(card)),
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/agents", tags=["Cards"], summary="List all agents stored in the database")
def list_agents_route(db: Session = Depends(get_db)):
    """Returns a summary of every agent_id with latest version and total version count."""
    agents = list_all_agents(db)
    for agent in agents:
        if agent.get("created_at"):
            agent["created_at"] = str(agent["created_at"])
    return {"count": len(agents), "agents": agents}


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/agents/cards/{agent_id}", tags=["Cards"], summary="Get latest card version as JSON")
def get_card_latest(agent_id: str, db: Session = Depends(get_db)):
    """Returns the most recent compliance card for an agent as structured JSON."""
    record = get_latest_card(db, agent_id)
    if not record:
        raise HTTPException(404, detail=f"No compliance card found for agent_id '{agent_id}'.")
    return json.loads(record.card_json)


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}/versions/{version}
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/agents/cards/{agent_id}/versions/{version}",
    tags=["Cards"],
    summary="Get a specific card version as JSON",
)
def get_card_version(agent_id: str, version: int, db: Session = Depends(get_db)):
    """Returns a specific version of a compliance card as structured JSON."""
    record = get_card_by_version(db, agent_id, version)
    if not record:
        raise HTTPException(404, detail=f"Version {version} not found for agent '{agent_id}'.")
    return json.loads(record.card_json)


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}/document
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/agents/cards/{agent_id}/document",
    response_class=HTMLResponse,
    tags=["Cards"],
    summary="Render compliance card as human-readable HTML",
)
def get_card_document(
    agent_id: str,
    version: Optional[int] = Query(None, description="Version number (defaults to latest)"),
    db: Session = Depends(get_db),
):
    """Returns the compliance card as a styled HTML document with print/PDF support."""
    record = (
        get_card_by_version(db, agent_id, version)
        if version is not None
        else get_latest_card(db, agent_id)
    )
    if not record:
        raise HTTPException(404, detail=f"No card found for agent '{agent_id}'.")

    card = AgentCard(**json.loads(record.card_json))
    annotated = annotate_card(card.model_dump())
    report    = check_card(card)
    return export_html(card, annotated, report)


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}/completeness
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/agents/cards/{agent_id}/completeness",
    tags=["Cards"],
    summary="Run the completeness checker on a card",
)
def get_completeness(
    agent_id: str,
    version: Optional[int] = Query(None, description="Version to check (defaults to latest)"),
    db: Session = Depends(get_db),
):
    """Flags null values, empty lists, and placeholder tokens (TBD, N/A, TODO …)."""
    record = (
        get_card_by_version(db, agent_id, version)
        if version is not None
        else get_latest_card(db, agent_id)
    )
    if not record:
        raise HTTPException(404, detail=f"No card found for agent '{agent_id}'.")

    card   = AgentCard(**json.loads(record.card_json))
    report = check_card(card)
    return report.model_dump()


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}/diff
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/agents/cards/{agent_id}/diff",
    tags=["Cards"],
    summary="Compare two card versions field-by-field",
)
def diff_versions(
    agent_id:     str,
    from_version: int = Query(..., alias="from", description="Earlier version"),
    to_version:   int = Query(..., alias="to",   description="Later version"),
    db: Session = Depends(get_db),
):
    """
    Compares two stored card versions field-by-field.
    Changes in tool_inventory, data_sources, decision_authority, and
    risk_classification are flagged as requiring regulatory reassessment.
    """
    r_from = get_card_by_version(db, agent_id, from_version)
    r_to   = get_card_by_version(db, agent_id, to_version)

    if not r_from:
        raise HTTPException(404, detail=f"Version {from_version} not found for agent '{agent_id}'.")
    if not r_to:
        raise HTTPException(404, detail=f"Version {to_version} not found for agent '{agent_id}'.")

    c_from = json.loads(r_from.card_json)
    c_to   = json.loads(r_to.card_json)

    REGULATORY_FIELDS = {"tool_inventory", "data_sources", "decision_authority", "risk_classification"}
    SKIP_FIELDS       = {"version", "generated_at"}

    changes: dict = {}
    for field in sorted((set(c_from) | set(c_to)) - SKIP_FIELDS):
        v_from = c_from.get(field)
        v_to   = c_to.get(field)
        if v_from != v_to:
            changes[field] = {
                "from": v_from,
                "to":   v_to,
                "requires_regulatory_reassessment": field in REGULATORY_FIELDS,
            }

    regulatory_changed = [f for f, d in changes.items() if d["requires_regulatory_reassessment"]]

    return {
        "agent_id":              agent_id,
        "from_version":          from_version,
        "to_version":            to_version,
        "total_changes":         len(changes),
        "regulatory_changes":    regulatory_changed,
        "requires_reassessment": len(regulatory_changed) > 0,
        "changes":               changes,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET /
# ══════════════════════════════════════════════════════════════════════════════

from portal import PORTAL_HTML

@app.get("/", response_class=HTMLResponse, tags=["Operations"], summary="Agent Compliance Portal Dashboard")
def root():
    """Serves the interactive Agent Compliance Portal website."""
    return HTMLResponse(content=PORTAL_HTML)
