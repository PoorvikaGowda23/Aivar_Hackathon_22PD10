"""
Unit tests for app/simulator.py
"""

from app.simulator import generate_synthetic_triple


def test_simulator_simple():
    c, m, t = generate_synthetic_triple("customer_support", "simple")
    assert "agent_id" in c
    assert "tools" in m
    assert "execution_steps" in t
    assert c["risk_classification"] == "limited"


def test_simulator_complex():
    c, m, t = generate_synthetic_triple("fintech", "complex")
    assert "COMPLEX" in c["agent_name"]
    assert c["decision_authority"] == "autonomous"
    assert c["risk_classification"] == "high"
    assert len(t["execution_steps"]) >= 4


def test_simulator_incomplete():
    c, m, t = generate_synthetic_triple("healthcare", "incomplete")
    assert len(c["human_oversight"]) == 0
    assert c["incident_contact"]["email"] == "invalid-email-format"
