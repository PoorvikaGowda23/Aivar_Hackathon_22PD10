"""
Tests for app/regulation_mapper.py.
"""

from regulation_mapper import REGULATION_MAP, annotate_card, get_citations, unmapped_fields
from schema import AgentCard


def test_every_schema_field_has_citations():
    """Verify 100% field coverage: every field in AgentCard model has citations."""
    schema_fields = set(AgentCard.model_fields.keys())
    map_fields = set(REGULATION_MAP.keys())

    missing = schema_fields - map_fields
    assert len(missing) == 0, f"Fields in AgentCard missing from REGULATION_MAP: {missing}"

    for field in schema_fields:
        citations = get_citations(field)
        assert len(citations) > 0, f"Field '{field}' has empty citations list"


def test_annotate_card():
    """Verify annotate_card wraps field values and attaches citations."""
    sample_card_dict = {
        "agent_id": "test-123",
        "agent_name": "Test Agent",
        "purpose_and_scope": "Testing mapping",
    }
    annotated = annotate_card(sample_card_dict)

    assert "agent_id" in annotated
    assert annotated["agent_id"]["value"] == "test-123"
    assert isinstance(annotated["agent_id"]["citations"], list)
    assert len(annotated["agent_id"]["citations"]) > 0


def test_unmapped_fields():
    """Verify unmapped_fields detects unknown keys and passes known keys."""
    known_card_dict = {"agent_id": "test-123", "purpose_and_scope": "Test"}
    assert unmapped_fields(known_card_dict) == []

    unknown_card_dict = {"agent_id": "test-123", "custom_unknown_field": "val"}
    assert unmapped_fields(unknown_card_dict) == ["custom_unknown_field"]
