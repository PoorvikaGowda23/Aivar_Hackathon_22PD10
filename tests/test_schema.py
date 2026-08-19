"""
Tests for app/schema.py (Pydantic models and Enums).
"""

import pytest
from pydantic import ValidationError
from schema import (
    AgentCard,
    LLMInfo,
    DecisionAuthority,
    RiskClassification,
    HumanOversightMechanism,
    IncidentContact,
    ToolEntry,
    DataSource,
)


def test_enum_values():
    """Verify enum members and string representations."""
    assert DecisionAuthority.INFORMATIONAL.value == "informational"
    assert DecisionAuthority.ADVISORY.value == "advisory"
    assert DecisionAuthority.AUTONOMOUS.value == "autonomous"

    assert RiskClassification.MINIMAL.value == "minimal"
    assert RiskClassification.LIMITED.value == "limited"
    assert RiskClassification.HIGH.value == "high"
    assert RiskClassification.UNACCEPTABLE.value == "unacceptable"


def test_agent_card_valid():
    """Verify successful creation and JSON serialization of a valid AgentCard."""
    card = AgentCard(
        agent_id="test-001",
        agent_name="Test Agent",
        purpose_and_scope="Valid purpose statement.",
        llm=LLMInfo(provider="Groq", model_name="llama-3.3-70b-versatile", version="3.3"),
        tool_inventory=[
            ToolEntry(name="reader", description="Reads data", operations=["read"], data_accessed=["db"])
        ],
        data_sources=[
            DataSource(name="Postgres", data_type="SQL DB", sensitivity="internal")
        ],
        decision_authority=DecisionAuthority.ADVISORY,
        human_oversight=[
            HumanOversightMechanism(description="Human in the loop approves actions")
        ],
        risk_classification=RiskClassification.LIMITED,
        known_limitations=["Cannot perform writes"],
        incident_contact=IncidentContact(name="Support", email="support@example.com"),
    )

    assert card.agent_id == "test-001"
    assert card.decision_authority == DecisionAuthority.ADVISORY
    assert card.risk_classification == RiskClassification.LIMITED
    assert len(card.tool_inventory) == 1

    # Round trip JSON serialization
    json_data = card.model_dump_json()
    reconstructed = AgentCard.model_validate_json(json_data)
    assert reconstructed.agent_id == card.agent_id
    assert reconstructed.llm.provider == "Groq"


def test_agent_card_invalid_enum():
    """Verify validation error when invalid enum string is provided."""
    with pytest.raises(ValidationError):
        AgentCard(
            agent_id="test-invalid",
            agent_name="Invalid Agent",
            purpose_and_scope="Purpose",
            llm=LLMInfo(provider="Groq", model_name="llama", version="1"),
            tool_inventory=[],
            data_sources=[],
            decision_authority="SUPER_AUTONOMOUS",  # Invalid enum value
            human_oversight=[],
            risk_classification=RiskClassification.MINIMAL,
            known_limitations=[],
            incident_contact=IncidentContact(name="A", email="a@b.com"),
        )
