"""
Tests for app/parsers.py across all 3 fixture sets (simple, complex, incomplete).
"""

from pathlib import Path
import pytest

from parsers import (
    load_json,
    build_llm_info,
    build_tool_inventory,
    build_data_sources,
    build_human_oversight,
    build_incident_contact,
    parse_decision_authority,
    parse_risk_classification,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


@pytest.mark.parametrize("fixture_name", ["simple", "complex", "incomplete"])
def test_parse_fixtures(fixture_name):
    """Verify load_json and field builders on all 3 fixture sets."""
    f_dir = FIXTURES_DIR / fixture_name
    config_path = f_dir / "agent_config.json"
    manifest_path = f_dir / "tool_manifest.json"
    trace_path = f_dir / "run_trace.json"

    assert config_path.exists()
    assert manifest_path.exists()
    assert trace_path.exists()

    config = load_json(config_path)
    manifest = load_json(manifest_path)
    trace = load_json(trace_path)

    assert isinstance(config, dict)
    assert isinstance(manifest, dict)
    assert isinstance(trace, dict)

    # 1. LLM Info
    if "llm" in config:
        llm = build_llm_info(config)
        assert llm.provider
        assert llm.model_name
    
    # 2. Tool Inventory
    tools = build_tool_inventory(manifest)
    assert isinstance(tools, list)
    if fixture_name in ["simple", "complex"]:
        assert len(tools) > 0

    # 3. Data Sources
    sources = build_data_sources(config)
    assert isinstance(sources, list)

    # 4. Human Oversight
    oversight = build_human_oversight(config)
    assert isinstance(oversight, list)

    # 5. Incident Contact
    contact = build_incident_contact(config)
    if fixture_name in ["simple", "complex"]:
        assert contact is not None
        assert contact.email

    # 6. Decision Authority & Risk Classification
    da = parse_decision_authority(config)
    rc = parse_risk_classification(config)
    if fixture_name in ["simple", "complex"]:
        assert da is not None
        assert rc is not None


def test_load_json_missing_file():
    """Verify FileNotFoundError on missing file."""
    with pytest.raises(FileNotFoundError):
        load_json(FIXTURES_DIR / "nonexistent_file.json")
