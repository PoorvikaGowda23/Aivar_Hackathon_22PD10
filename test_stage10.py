"""Comprehensive Stage 10 verification — no LLM calls, tests every CRUD function."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "app"))

# pyrefly: ignore [missing-import]
from database import init_db, SessionLocal, engine, DATABASE_URL
# pyrefly: ignore [missing-import]
from models import CardVersionRecord
# pyrefly: ignore [missing-import]
from crud import save_card, get_card_versions, get_card_by_version, get_latest_card, list_all_agents 
# pyrefly: ignore [missing-import]
from schema import (AgentCard, LLMInfo, IncidentContact, DecisionAuthority,
                    RiskClassification, HumanOversightMechanism, ToolEntry, DataSource)
# pyrefly: ignore [missing-import]
from sqlalchemy import inspect as sa_inspect 

# ─── 1. Print DB config ────────────────────────────────────────────────
print(f"DATABASE_URL : {DATABASE_URL}")

# ─── 2. Create tables ─────────────────────────────────────────────────
init_db()
print("Tables created (idempotent).")

inspector = sa_inspect(engine)
tables = inspector.get_table_names()
columns = [c["name"] for c in inspector.get_columns("card_versions")]
print(f"Tables in DB     : {tables}")
print(f"card_versions cols: {columns}")
assert "card_versions" in tables, "FAIL: table not created!"

# ─── 3. Helper to build a card without LLM ────────────────────────────
def make_card(agent_id: str, name: str) -> AgentCard:
    return AgentCard(
        agent_id=agent_id,
        agent_name=name,
        purpose_and_scope="Test purpose.",
        llm=LLMInfo(provider="Groq", model_name="llama-3.3-70b-versatile", version="3.3"),
        tool_inventory=[ToolEntry(name="reader", description="Reads data",
                                  operations=["read"], data_accessed=["docs"])],
        data_sources=[DataSource(name="TestDB", data_type="structured DB", sensitivity="internal")],
        decision_authority=DecisionAuthority.ADVISORY,
        human_oversight=[HumanOversightMechanism(description="Human approves all output")],
        risk_classification=RiskClassification.LIMITED,
        known_limitations=["Test only"],
        incident_contact=IncidentContact(name="Team", email="team@example.com"),
    )

if __name__ == "__main__":
    db = SessionLocal()
    fails = []

    try:
        # ─── 4. save_card — auto-increment per agent ───────────────────────
        r1 = save_card(db, make_card("agent-alpha", "Alpha Agent"))
        r2 = save_card(db, make_card("agent-alpha", "Alpha Agent"))
        r3 = save_card(db, make_card("agent-beta",  "Beta Agent"))
        print(f"\nsave_card:")
        print(f"  agent-alpha v{r1.version} (id={r1.id})")
        print(f"  agent-alpha v{r2.version} (id={r2.id})  <- auto-incremented")
        print(f"  agent-beta  v{r3.version} (id={r3.id})  <- separate agent, starts at 1")
        if not (r1.version == 1 and r2.version == 2):
            fails.append("FAIL: version auto-increment for same agent")
        if r3.version != 1:
            fails.append("FAIL: separate agent should start at v1")
        print("  OK" if not fails else f"  {fails[-1]}")

        # ─── 5. card_json is valid JSON containing the full card ───────────
        parsed = json.loads(r1.card_json)
        assert parsed["agent_id"] == "agent-alpha"
        assert "tool_inventory" in parsed
        assert "known_limitations" in parsed
        print("\ncard_json round-trip : all fields present  OK")

        # ─── 6. get_card_versions ─────────────────────────────────────────
        versions = get_card_versions(db, "agent-alpha")
        print(f"\nget_card_versions    : {len(versions)} versions for agent-alpha", end="  ")
        if len(versions) != 2:
            fails.append(f"FAIL: expected 2 versions, got {len(versions)}")
            print(fails[-1])
        else:
            print("OK")

        # ─── 7. get_card_by_version ───────────────────────────────────────
        v1 = get_card_by_version(db, "agent-alpha", 1)
        print(f"get_card_by_version  : version={v1.version if v1 else None}", end="  ")
        if v1 is None or v1.version != 1:
            fails.append("FAIL: could not retrieve version 1")
            print(fails[-1])
        else:
            print("OK")

        # ─── 8. get_latest_card ───────────────────────────────────────────
        latest = get_latest_card(db, "agent-alpha")
        print(f"get_latest_card      : version={latest.version if latest else None}", end="  ")
        if latest is None or latest.version != 2:
            fails.append("FAIL: latest version should be 2")
            print(fails[-1])
        else:
            print("OK")

        # ─── 9. Missing version returns None ──────────────────────────────
        missing = get_card_by_version(db, "agent-alpha", 999)
        print(f"nonexistent version  : returns {'None' if missing is None else missing.version}", end="  ")
        if missing is not None:
            fails.append("FAIL: missing version should return None")
            print(fails[-1])
        else:
            print("OK")

        # ─── 10. list_all_agents ──────────────────────────────────────────
        agents = list_all_agents(db)
        agent_ids = [a["agent_id"] for a in agents]
        alpha = next((a for a in agents if a["agent_id"] == "agent-alpha"), None)
        beta  = next((a for a in agents if a["agent_id"] == "agent-beta"),  None)
        print(f"\nlist_all_agents      : {len(agents)} agents found  ", end="")
        if "agent-alpha" not in agent_ids or "agent-beta" not in agent_ids:
            fails.append("FAIL: both agents not found")
            print(fails[-1])
        elif alpha["latest_version"] != 2 or alpha["total_versions"] != 2:
            fails.append(f"FAIL: alpha summary wrong: {alpha}")
            print(fails[-1])
        elif beta["latest_version"] != 1 or beta["total_versions"] != 1:
            fails.append(f"FAIL: beta summary wrong: {beta}")
            print(fails[-1])
        else:
            print("OK")
            print(f"  agent-alpha: latest_version={alpha['latest_version']}, total_versions={alpha['total_versions']}")
            print(f"  agent-beta : latest_version={beta['latest_version']},  total_versions={beta['total_versions']}")

        # ─── 11. Verify cards.db file on disk ─────────────────────────────
        db_file = Path("cards.db")
        print(f"\ncards.db on disk     : {db_file.exists()}", end="  ")
        if not db_file.exists():
            fails.append("FAIL: cards.db file not found on disk")
            print(fails[-1])
        else:
            print(f"OK  (size={db_file.stat().st_size:,} bytes)")

    finally:
        db.close()

    # ─── Final result ───────────────────────────────────────────────────────
    print("\n" + "=" * 56)
    if not fails:
        print("STAGE 10 COMPLETE — All checks passed.")
        sys.exit(0)
    else:
        print(f"STAGE 10 INCOMPLETE — {len(fails)} failure(s):")
        for f in fails:
            print(f"  {f}")
        sys.exit(1)
