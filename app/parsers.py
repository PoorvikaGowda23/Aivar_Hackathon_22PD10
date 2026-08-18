"""
Step 2a: Deterministic parsing.

Reads the three raw input files (agent config, tool manifest, run trace)
and maps the parts that are already structured facts directly onto the
schema's sub-objects. No LLM involved here on purpose — if the config
already says the risk classification is "limited", we should not be
asking a model to re-derive that; we should just read it.

Only two fields are NOT handled here: `purpose_and_scope` and
`known_limitations`. Those need synthesis from free-form data and are
handled by llm_extractor.py instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from schema import (
    DataSource,
    DecisionAuthority,
    HumanOversightMechanism,
    IncidentContact,
    LLMInfo,
    RiskClassification,
    ToolEntry,
)


def load_json(path: str | Path) -> Dict[str, Any]:
    """Read a JSON file into a plain dict. Raises a clear error if missing/invalid."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Expected input file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path} is not valid JSON: {e}") from e


# ---------------------------------------------------------------------------
# Field builders — each one owns exactly one part of the schema
# ---------------------------------------------------------------------------

def build_llm_info(raw_config: Dict[str, Any]) -> LLMInfo:
    llm = raw_config.get("llm")
    if not llm:
        raise ValueError("agent_config is missing the required 'llm' section")
    return LLMInfo(**llm)


def build_tool_inventory(raw_manifest: Dict[str, Any]) -> list[ToolEntry]:
    tools = raw_manifest.get("tools", [])
    return [ToolEntry(**tool) for tool in tools]


def build_data_sources(raw_config: Dict[str, Any]) -> list[DataSource]:
    sources = raw_config.get("data_sources", [])
    return [DataSource(**source) for source in sources]


def build_human_oversight(raw_config: Dict[str, Any]) -> list[HumanOversightMechanism]:
    mechanisms = raw_config.get("human_oversight", [])
    return [HumanOversightMechanism(**m) for m in mechanisms]


def build_incident_contact(raw_config: Dict[str, Any]) -> Optional[IncidentContact]:
    contact = raw_config.get("incident_contact")
    if not contact:
        return None
    return IncidentContact(**contact)


def parse_decision_authority(raw_config: Dict[str, Any]) -> Optional[DecisionAuthority]:
    value = raw_config.get("decision_authority")
    if not value:
        return None
    return DecisionAuthority(value)


def parse_risk_classification(raw_config: Dict[str, Any]) -> Optional[RiskClassification]:
    value = raw_config.get("risk_classification")
    if not value:
        return None
    return RiskClassification(value)