"""
Tests for app/completeness.py (rule-based completeness checker).
"""

from completeness import check_card, IssueType
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


def test_complete_card():
    """Verify clean card reports is_complete=True with 0 issues."""
    card = AgentCard(
        agent_id="test-clean",
        agent_name="Clean Agent",
        purpose_and_scope="Valid scope description.",
        llm=LLMInfo(provider="Groq", model_name="llama-3.3-70b-versatile", version="3.3"),
        tool_inventory=[
            ToolEntry(name="reader", description="Reads data", operations=["read"], data_accessed=["db"])
        ],
        data_sources=[
            DataSource(name="Postgres", data_type="SQL DB", sensitivity="internal")
        ],
        decision_authority=DecisionAuthority.ADVISORY,
        human_oversight=[
            HumanOversightMechanism(description="Human approves output")
        ],
        risk_classification=RiskClassification.LIMITED,
        known_limitations=["No limitations recorded."],
        incident_contact=IncidentContact(name="Support", email="support@example.com"),
    )

    report = check_card(card)
    assert report.is_complete is True
    assert len(report.issues) == 0


def test_incomplete_placeholders_and_empty():
    """Verify detection of placeholders (TBD, N/A, TODO) and empty lists/strings."""
    card_dict = {
        "agent_id": "test-inc",
        "agent_name": "Incomplete Agent",
        "purpose_and_scope": "TBD",  # Placeholder
        "llm": {"provider": "Groq", "model_name": "llama", "version": "1.0"},
        "tool_inventory": [],  # Empty list
        "data_sources": [{"name": "DB", "data_type": "", "sensitivity": "high"}],  # Empty string
        "decision_authority": "ADVISORY",
        "human_oversight": [{"description": "TODO"}],  # Placeholder in list item
        "risk_classification": "LIMITED",
        "known_limitations": ["N/A"],  # Placeholder in list item
        "incident_contact": {"name": "Fixme", "email": "contact@example.com"},  # Placeholder
    }

    report = check_card(card_dict)
    assert report.is_complete is False
    assert len(report.issues) >= 5

    issue_fields = [i.field for i in report.issues]
    assert "purpose_and_scope" in issue_fields
    assert "tool_inventory" in issue_fields
    assert "data_sources[0].data_type" in issue_fields
    assert "human_oversight[0].description" in issue_fields
    assert "known_limitations[0]" in issue_fields
    assert "incident_contact.name" in issue_fields

    issue_types = {i.field: i.issue_type for i in report.issues}
    assert issue_types["purpose_and_scope"] == IssueType.PLACEHOLDER
    assert issue_types["tool_inventory"] == IssueType.EMPTY
    assert issue_types["data_sources[0].data_type"] == IssueType.EMPTY
