"""
Stage 11: FastAPI application.

Wires together every stage into a deployable HTTP service.
Routes are deliberately thin — they call the plain functions built and
tested in Stages 1-10 and handle only HTTP concerns (file I/O, status
codes, response types).

Start locally:
  cd c:\\Users\\user\\Desktop\\Aivar_Hackathon_22PD10
  myenv\\Scripts\\uvicorn app.main:app --reload --port 8000

Interactive docs:  http://localhost:8000/docs
"""

from __future__ import annotations

# ── Path bootstrap ─────────────────────────────────────────────────────────
# All sibling modules (database, models, crud, …) use bare imports.
# Inserting the app/ directory at the front of sys.path makes those imports
# work regardless of whether uvicorn is launched as:
#   uvicorn app.main:app          (from project root)
#   uvicorn main:app              (from inside app/)
import sys as _sys
from pathlib import Path as _Path

_APP_DIR = _Path(__file__).parent.resolve()
if str(_APP_DIR) not in _sys.path:
    _sys.path.insert(0, str(_APP_DIR))
# ──────────────────────────────────────────────────────────────────────────

import json
import os
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

# ── FastAPI imports ────────────────────────────────────────────────────────
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

# ── Stage imports — order matters: models must register with Base BEFORE
#    init_db() is called in the lifespan startup block. ──────────────────
import models  # noqa: F401 — side-effect: registers CardVersionRecord with Base
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
from regulation_mapper import annotate_card
from schema import AgentCard


# ── Lifespan: create DB tables once on startup ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # idempotent — safe to call on every cold start
    yield              # server is live


# ── App instance ───────────────────────────────────────────────────────────
app = FastAPI(
    title="Agent Compliance Card Generator",
    description=(
        "Generates structured, regulation-aligned compliance cards for AI agents "
        "from an agent config, tool manifest, and run trace. "
        "Every card is persisted as an immutable version and can be rendered as "
        "structured JSON or a human-readable HTML document."
    ),
    version="1.0.0",
    lifespan=lifespan,
)


# ══════════════════════════════════════════════════════════════════════════════
# /health
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/health",
    tags=["Operations"],
    summary="Liveness and dependency check",
)
def health(db: Session = Depends(get_db)):
    """
    Returns 200 (healthy) or 503 (degraded).
    Checks:
      - SQLite DB is reachable
      - GROQ_API_KEY environment variable is set
    """
    # Database ping
    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as exc:
        db_status = f"error: {exc}"

    # LLM key presence
    groq_key = os.getenv("GROQ_API_KEY", "")
    llm_status = "key_present" if groq_key else "key_missing"

    overall = "healthy" if (db_status == "ok" and groq_key) else "degraded"

    return JSONResponse(
        status_code=200 if overall == "healthy" else 503,
        content={
            "status": overall,
            "checks": {
                "database": db_status,
                "llm_key": llm_status,
            },
        },
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
    config_file: UploadFile = File(..., description="agent_config.json"),
    manifest_file: UploadFile = File(..., description="tool_manifest.json"),
    trace_file: UploadFile = File(..., description="run_trace.json"),
    db: Session = Depends(get_db),
):
    """
    Upload three JSON files to generate a compliance card.

    - Parses the config + manifest + trace (deterministic)
    - Calls the LLM for purpose_and_scope + known_limitations
    - Runs the completeness checker
    - Persists the card as a new immutable version in SQLite
    - Returns the full card JSON + completeness summary
    """
    # Read uploads into memory first so temp files can be written synchronously
    config_bytes = config_file.file.read()
    manifest_bytes = manifest_file.file.read()
    trace_bytes = trace_file.file.read()

    # Write to a temp directory; generate_agent_card expects file paths
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "config.json").write_bytes(config_bytes)
        (tmp / "manifest.json").write_bytes(manifest_bytes)
        (tmp / "trace.json").write_bytes(trace_bytes)

        try:
            card = generate_agent_card(
                config_path=tmp / "config.json",
                manifest_path=tmp / "manifest.json",
                trace_path=tmp / "trace.json",
            )
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Card generation failed: {exc}")

    # Persist to DB (auto-assigns next version for this agent_id)
    record = save_card(db, card)

    # Run completeness check for the response summary
    report = check_card(card)

    return {
        "agent_id": card.agent_id,
        "agent_name": card.agent_name,
        "version": record.version,
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
# GET /agents   — list all stored agents
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/agents",
    tags=["Cards"],
    summary="List all agents stored in the database",
)
def list_agents_route(db: Session = Depends(get_db)):
    """Returns a summary of every agent_id with latest version and total version count."""
    agents = list_all_agents(db)
    # Stringify datetimes for JSON serialisation
    for agent in agents:
        if agent.get("created_at"):
            agent["created_at"] = str(agent["created_at"])
    return {"count": len(agents), "agents": agents}


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}   — latest version as JSON
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/agents/cards/{agent_id}",
    tags=["Cards"],
    summary="Get latest card version as JSON",
)
def get_card_latest(agent_id: str, db: Session = Depends(get_db)):
    """Returns the most recent compliance card for an agent as structured JSON."""
    record = get_latest_card(db, agent_id)
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No compliance card found for agent_id '{agent_id}'.",
        )
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
        raise HTTPException(
            status_code=404,
            detail=f"Version {version} not found for agent '{agent_id}'.",
        )
    return json.loads(record.card_json)


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}/document   — human-readable HTML
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
    """
    Returns the compliance card as a styled HTML document.
    Includes regulation citations next to every field.
    Has a Print / Save as PDF button.
    """
    record = (
        get_card_by_version(db, agent_id, version)
        if version is not None
        else get_latest_card(db, agent_id)
    )
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No card found for agent '{agent_id}'.",
        )

    card_dict = json.loads(record.card_json)
    card = AgentCard(**card_dict)
    annotated = annotate_card(card.model_dump())
    report = check_card(card)

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
    """
    Runs the rule-based completeness checker and returns a full report.
    Flags null values, empty lists, and placeholder tokens (TBD, N/A, TODO, ...).
    """
    record = (
        get_card_by_version(db, agent_id, version)
        if version is not None
        else get_latest_card(db, agent_id)
    )
    if not record:
        raise HTTPException(
            status_code=404,
            detail=f"No card found for agent '{agent_id}'.",
        )

    card = AgentCard(**json.loads(record.card_json))
    report = check_card(card)
    return report.model_dump()


# ══════════════════════════════════════════════════════════════════════════════
# GET /agents/cards/{agent_id}/diff?from=1&to=2
# ══════════════════════════════════════════════════════════════════════════════

@app.get(
    "/agents/cards/{agent_id}/diff",
    tags=["Cards"],
    summary="Compare two card versions field-by-field",
)
def diff_versions(
    agent_id: str,
    from_version: int = Query(..., alias="from", description="Earlier version number"),
    to_version: int = Query(..., alias="to", description="Later version number"),
    db: Session = Depends(get_db),
):
    """
    Compares two stored versions of a compliance card field-by-field.
    Fields in tool_inventory, data_sources, decision_authority, and
    risk_classification are flagged as 'requires_regulatory_reassessment'
    when they change — these are the fields that determine which regulatory
    obligations apply.
    """
    r_from = get_card_by_version(db, agent_id, from_version)
    r_to   = get_card_by_version(db, agent_id, to_version)

    if not r_from:
        raise HTTPException(404, f"Version {from_version} not found for agent '{agent_id}'.")
    if not r_to:
        raise HTTPException(404, f"Version {to_version} not found for agent '{agent_id}'.")

    c_from = json.loads(r_from.card_json)
    c_to   = json.loads(r_to.card_json)

    # These field changes require regulatory re-assessment (EU AI Act Art. 6, 9, 13, 14)
    REGULATORY_FIELDS = {"tool_inventory", "data_sources", "decision_authority", "risk_classification"}
    # Exclude auto-generated bookkeeping fields from the diff
    SKIP_FIELDS = {"version", "generated_at"}

    all_keys = sorted(
        (set(c_from.keys()) | set(c_to.keys())) - SKIP_FIELDS
    )

    changes: dict = {}
    for field in all_keys:
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
        "agent_id": agent_id,
        "from_version": from_version,
        "to_version": to_version,
        "total_changes": len(changes),
        "regulatory_changes": regulatory_changed,
        "requires_reassessment": len(regulatory_changed) > 0,
        "changes": changes,
    }


# ══════════════════════════════════════════════════════════════════════════════
# GET /   — API index
# ══════════════════════════════════════════════════════════════════════════════

@app.get("/", tags=["Operations"], summary="API root")
def root():
    """Lists all available routes."""
    return {
        "service": "Agent Compliance Card Generator",
        "version": "1.0.0",
        "routes": {
            "POST /agents/cards/generate":                  "Generate a new card (upload 3 JSON files)",
            "GET  /agents":                                  "List all stored agents",
            "GET  /agents/cards/{agent_id}":                "Latest card version (JSON)",
            "GET  /agents/cards/{agent_id}/versions/{v}":   "Specific card version (JSON)",
            "GET  /agents/cards/{agent_id}/document":       "Card as human-readable HTML",
            "GET  /agents/cards/{agent_id}/completeness":   "Completeness check report",
            "GET  /agents/cards/{agent_id}/diff?from=1&to=2": "Field-by-field diff between two versions",
            "GET  /health":                                  "Liveness + dependency check",
            "GET  /docs":                                    "Interactive API documentation (Swagger UI)",
        },
    }
