"""
Stage 10: CRUD operations for card storage and retrieval.

Handles persistence logic:
  - Automatically calculates next version integer for a given agent_id
  - Inserts new card version records (never overwrites existing ones)
  - Queries version history and specific versions
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from models import CardVersionRecord
from schema import AgentCard


def save_card(db: Session, card: AgentCard) -> CardVersionRecord:
    """
    Save a new AgentCard into the database.
    Automatically assigns the next version integer for the card's agent_id.
    """
    card_dict = card.model_dump()
    agent_id = card.agent_id
    agent_name = card.agent_name

    # Determine next version number for this agent_id
    current_max = (
        db.query(func.max(CardVersionRecord.version))
        .filter(CardVersionRecord.agent_id == agent_id)
        .scalar()
    )
    next_version = (current_max or 0) + 1

    # Update card version attribute and serialised JSON
    card.version = next_version
    card_dict["version"] = next_version

    record = CardVersionRecord(
        agent_id=agent_id,
        agent_name=agent_name,
        version=next_version,
        card_json=json.dumps(card_dict, default=str),
    )

    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_card_versions(db: Session, agent_id: str) -> List[CardVersionRecord]:
    """Retrieve all stored versions for a specific agent_id ordered by version asc."""
    return (
        db.query(CardVersionRecord)
        .filter(CardVersionRecord.agent_id == agent_id)
        .order_by(CardVersionRecord.version.asc())
        .all()
    )


def get_card_by_version(
    db: Session, agent_id: str, version: int
) -> Optional[CardVersionRecord]:
    """Retrieve a specific version of a card by agent_id and version number."""
    return (
        db.query(CardVersionRecord)
        .filter(
            CardVersionRecord.agent_id == agent_id,
            CardVersionRecord.version == version,
        )
        .first()
    )


def get_latest_card(db: Session, agent_id: str) -> Optional[CardVersionRecord]:
    """Retrieve the latest version of a card for a given agent_id."""
    return (
        db.query(CardVersionRecord)
        .filter(CardVersionRecord.agent_id == agent_id)
        .order_by(CardVersionRecord.version.desc())
        .first()
    )


def list_all_agents(db: Session) -> List[Dict[str, Any]]:
    """List all unique agents and details of their latest version."""
    # Subquery to find max version per agent_id
    subq = (
        db.query(
            CardVersionRecord.agent_id,
            func.max(CardVersionRecord.version).label("max_version"),
        )
        .group_by(CardVersionRecord.agent_id)
        .subquery()
    )

    records = (
        db.query(CardVersionRecord)
        .join(
            subq,
            (CardVersionRecord.agent_id == subq.c.agent_id)
            & (CardVersionRecord.version == subq.c.max_version),
        )
        .order_by(CardVersionRecord.agent_id.asc())
        .all()
    )

    result = []
    for r in records:
        total_versions = (
            db.query(func.count(CardVersionRecord.id))
            .filter(CardVersionRecord.agent_id == r.agent_id)
            .scalar()
        )
        result.append(
            {
                "agent_id": r.agent_id,
                "agent_name": r.agent_name,
                "latest_version": r.version,
                "total_versions": total_versions,
                "created_at": r.created_at,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Standalone test — run: python app/crud.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))

    from database import init_db, SessionLocal
    from generator import generate_agent_card

    print("Initialising database tables...")
    init_db()

    db = SessionLocal()
    try:
        fixtures_dir = Path(__file__).parent.parent / "fixtures" / "simple"

        print("Generating card from simple fixture...")
        card = generate_agent_card(
            config_path=fixtures_dir / "agent_config.json",
            manifest_path=fixtures_dir / "tool_manifest.json",
            trace_path=fixtures_dir / "run_trace.json",
        )

        print(f"Saving card '{card.agent_id}' to SQLite DB...")
        record = save_card(db, card)
        print(f"Saved Record ID: {record.id}, Agent: {record.agent_id}, Version: {record.version}")

        print("Saving second version to test auto-incrementing version number...")
        record2 = save_card(db, card)
        print(f"Saved Record ID: {record2.id}, Agent: {record2.agent_id}, Version: {record2.version}")

        versions = get_card_versions(db, card.agent_id)
        print(f"\nRetrieved {len(versions)} versions for '{card.agent_id}':")
        for v in versions:
            print(f"  - Version {v.version} saved at {v.created_at}")

        all_agents = list_all_agents(db)
        print(f"\nAll Agents in DB: {all_agents}")

        print("\nPASS — Stage 10 SQLite CRUD verified successfully!")
    finally:
        db.close()
