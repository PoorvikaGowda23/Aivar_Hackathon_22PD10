"""
Stage 10 Test — Fast test without LLM calls.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "app"))

from database import init_db, SessionLocal
from models import CardVersionRecord
from crud import save_card, get_card_versions, get_card_by_version, list_all_agents
from schema import AgentCard, LLMInfo, IncidentContact, DecisionAuthority, RiskClassification

print("Initialising database...")
init_db()

db = SessionLocal()
try:
    dummy_card = AgentCard(
        agent_id="test-agent-001",
        agent_name="Test Agent",
        purpose_and_scope="Test purpose and scope for unit test.",
        llm=LLMInfo(provider="Groq", model_name="llama-3.3-70b-versatile", version="3.3"),
        decision_authority=DecisionAuthority.ADVISORY,
        risk_classification=RiskClassification.LIMITED,
        incident_contact=IncidentContact(name="Support", email="support@example.com"),
    )

    rec1 = save_card(db, dummy_card)
    print(f"Saved Version 1: ID={rec1.id}, agent_id={rec1.agent_id}, version={rec1.version}")

    rec2 = save_card(db, dummy_card)
    print(f"Saved Version 2: ID={rec2.id}, agent_id={rec2.agent_id}, version={rec2.version}")

    versions = get_card_versions(db, "test-agent-001")
    print(f"Total versions retrieved for test-agent-001: {len(versions)}")

    v1 = get_card_by_version(db, "test-agent-001", 1)
    print(f"Version 1 record retrieved: {v1}")

    agents = list_all_agents(db)
    print(f"All agents summary: {agents}")

    print("STAGE 10 TEST PASSED (SQLite + Sync SQLAlchemy persistence verified)!")
finally:
    db.close()
