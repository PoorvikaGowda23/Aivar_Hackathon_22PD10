"""
Tests for app/generator.py (end-to-end card generation from fixtures).
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from generator import generate_agent_card
from llm_extractor import NarrativeFields
from schema import AgentCard

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize("fixture_name", ["simple", "complex", "incomplete"])
def test_generate_agent_card_mocked(fixture_name):
    """End-to-end test of generate_agent_card for each fixture set with mocked LLM."""
    f_dir = FIXTURES_DIR / fixture_name
    config_path = f_dir / "agent_config.json"
    manifest_path = f_dir / "tool_manifest.json"
    trace_path = f_dir / "run_trace.json"

    mock_narrative = NarrativeFields(
        purpose_and_scope=f"Synthetic purpose for {fixture_name}.",
        known_limitations=[f"Synthetic limitation 1 for {fixture_name}."],
    )

    with patch("generator.generate_narrative_fields", return_value=mock_narrative):
        card = generate_agent_card(config_path, manifest_path, trace_path)

        assert isinstance(card, AgentCard)
        assert card.agent_id
        assert card.agent_name
        assert card.purpose_and_scope == f"Synthetic purpose for {fixture_name}."
        assert card.known_limitations == [f"Synthetic limitation 1 for {fixture_name}."]
        assert card.llm.provider
        assert card.llm.model_name


def test_generate_agent_card_missing_keys(tmp_path):
    """Verify ValueError when agent_config is missing required keys."""
    bad_config = tmp_path / "bad_config.json"
    bad_config.write_text('{"missing": "agent_id"}', encoding="utf-8")

    manifest = FIXTURES_DIR / "simple" / "tool_manifest.json"
    trace = FIXTURES_DIR / "simple" / "run_trace.json"

    with pytest.raises(ValueError, match="agent_config must include 'agent_id' and 'agent_name'"):
        generate_agent_card(bad_config, manifest, trace)
