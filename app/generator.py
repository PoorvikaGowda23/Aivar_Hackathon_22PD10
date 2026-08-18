"""
Step 2: The card generator.

Ties together the deterministic parser (parsers.py) and the LLM
extractor (llm_extractor.py) to produce one fully populated AgentCard
from three input files. This is the single function the API route
(Step 6) will call.
"""

from __future__ import annotations

from pathlib import Path

from llm_extractor import generate_narrative_fields
from parsers import (
    build_data_sources,
    build_human_oversight,
    build_incident_contact,
    build_llm_info,
    build_tool_inventory,
    load_json,
    parse_decision_authority,
    parse_risk_classification,
)
from schema import AgentCard


def generate_agent_card(
    config_path: str | Path,
    manifest_path: str | Path,
    trace_path: str | Path,
) -> AgentCard:
    """Read the three input files and produce a validated AgentCard."""
    raw_config = load_json(config_path)
    raw_manifest = load_json(manifest_path)
    raw_trace = load_json(trace_path)

    if "agent_id" not in raw_config or "agent_name" not in raw_config:
        raise ValueError("agent_config must include 'agent_id' and 'agent_name'")

    narrative = generate_narrative_fields(raw_config, raw_manifest, raw_trace)

    return AgentCard(
        agent_id=raw_config["agent_id"],
        agent_name=raw_config["agent_name"],
        purpose_and_scope=narrative.purpose_and_scope,
        llm=build_llm_info(raw_config),
        tool_inventory=build_tool_inventory(raw_manifest),
        data_sources=build_data_sources(raw_config),
        decision_authority=parse_decision_authority(raw_config),
        human_oversight=build_human_oversight(raw_config),
        risk_classification=parse_risk_classification(raw_config),
        known_limitations=narrative.known_limitations,
        incident_contact=build_incident_contact(raw_config),
    )


if __name__ == "__main__":
    # Quick manual check against the fixture files in ../fixtures/
    fixtures_dir = Path(__file__).parent.parent / "fixtures"

    card = generate_agent_card(
        config_path=fixtures_dir / "agent_config.json",
        manifest_path=fixtures_dir / "tool_manifest.json",
        trace_path=fixtures_dir / "run_trace.json",
    )

    print(card.model_dump_json(indent=2))