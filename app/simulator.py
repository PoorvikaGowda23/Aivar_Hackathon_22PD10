"""
Stage 14/15: Synthetic Agent Artifact Simulator Engine.

Generates realistic (agent_config, tool_manifest, run_trace) JSON triples across
4 domain verticals (customer_support, fintech, healthcare, hr) and 3 complexity levels:
  - simple: Minimal, fully-populated, passes 100% completeness cleanly.
  - complex: Multi-tool, sensitive data sources, runtime trace errors (exercises LLM limitations inference).
  - incomplete: Intentionally injects missing fields/empty lists (exercises Completeness Checker).
"""

from __future__ import annotations
from typing import Dict, Any, Tuple


def generate_synthetic_triple(
    domain: str = "customer_support",
    complexity: str = "simple"
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Returns (agent_config, tool_manifest, run_trace) dict triple.
    """
    domain = domain.lower()
    complexity = complexity.lower()

    if domain not in ("customer_support", "fintech", "healthcare", "hr"):
        domain = "customer_support"
    if complexity not in ("simple", "complex", "incomplete"):
        complexity = "simple"

    # Base templates by domain
    domain_data = {
        "customer_support": {
            "id": "agent-cs-sim",
            "name": "Customer Support Resolution Agent",
            "tools": ["ticket_reader", "knowledge_base_search", "crm_reply_writer"],
            "data": [
                {"name": "Support Ticket Database", "data_type": "Postgres SQL", "sensitivity": "internal"},
                {"name": "Help Center Knowledge Base", "data_type": "Vector Search Index", "sensitivity": "public"}
            ],
            "oversight": "Human agent reviews and approves response before sending for priority tickets.",
            "contact": {"name": "Support Operations Escalation", "email": "cs-ops@example.com", "escalation_path": "Slack #cs-escalations"}
        },
        "fintech": {
            "id": "agent-fin-sim",
            "name": "Financial Refund & Chargeback Agent",
            "tools": ["ledger_reader", "bank_transfer_api", "fraud_scoring_engine", "audit_logger"],
            "data": [
                {"name": "Core Banking Ledger", "data_type": "REST API", "sensitivity": "confidential"},
                {"name": "Customer PII Database", "data_type": "Encrypted SQL", "sensitivity": "PII"}
            ],
            "oversight": "All transaction refunds above $1,000 hold for CFO approval.",
            "contact": {"name": "Fintech Compliance Desk", "email": "fin-compliance@example.com", "escalation_path": "PagerDuty Tier 1"}
        },
        "healthcare": {
            "id": "agent-health-sim",
            "name": "Clinical Patient Triage Assistant",
            "tools": ["ehr_history_reader", "symptom_urgency_evaluator", "physician_alert_system"],
            "data": [
                {"name": "Electronic Health Records (EHR)", "data_type": "FHIR API", "sensitivity": "PII"}
            ],
            "oversight": "Licensed physician must sign off on non-routine triage advice.",
            "contact": {"name": "Clinical Safety Officer", "email": "safety@hospital.org", "escalation_path": "Hospital Hotline"}
        },
        "hr": {
            "id": "agent-hr-sim",
            "name": "Employee Onboarding & Payroll Bot",
            "tools": ["hris_employee_reader", "payroll_adjustment_writer", "benefit_portal_sync"],
            "data": [
                {"name": "HRIS Personnel Database", "data_type": "SQL Database", "sensitivity": "PII"},
                {"name": "Benefits Provider API", "data_type": "REST API", "sensitivity": "confidential"}
            ],
            "oversight": "HR manager sign-off required for salary or tax deduction changes.",
            "contact": {"name": "HR Operations Team", "email": "hr-ops@example.com", "escalation_path": "Internal HR Portal"}
        }
    }

    info = domain_data[domain]
    agent_id = f"{info['id']}-{complexity}"

    # 1. agent_config
    agent_config: Dict[str, Any] = {
        "agent_id": agent_id,
        "agent_name": f"{info['name']} ({complexity.upper()})",
        "llm": {
            "provider": "Groq",
            "model_name": "llama-3.3-70b-versatile",
            "version": "3.3",
            "hosting": "Groq Cloud API"
        },
        "decision_authority": "autonomous" if complexity == "complex" else "advisory",
        "risk_classification": "high" if complexity == "complex" or domain in ("fintech", "healthcare") else "limited",
        "data_sources": info["data"],
        "human_oversight": [
            {
                "description": info["oversight"],
                "trigger": "High-risk trigger condition"
            }
        ],
        "incident_contact": info["contact"]
    }

    # 2. tool_manifest
    tools_list = []
    for t_name in info["tools"]:
        tools_list.append({
            "name": t_name,
            "description": f"Executes operations for {t_name.replace('_', ' ')}.",
            "operations": ["execute", "read", "write"] if complexity == "complex" else ["read"],
            "data_accessed": [d["name"] for d in info["data"]]
        })
    tool_manifest = {"tools": tools_list}

    # 3. run_trace
    trace_steps = [
        {
            "step": 1,
            "event": "user_prompt",
            "content": f"Initiating automated {domain.replace('_', ' ')} execution request."
        },
        {
            "step": 2,
            "event": "tool_call",
            "tool_name": info["tools"][0],
            "input": {"query_id": "req-9901"},
            "output": {"status": "success", "result_count": 1}
        }
    ]

    if complexity == "complex":
        trace_steps.append({
            "step": 3,
            "event": "tool_call",
            "tool_name": info["tools"][-1],
            "input": {"action": "execute_transaction"},
            "output": {"status": "error", "error_code": "ERR_LIMIT_EXCEEDED", "message": "Transaction exceeded $1,000 threshold. Holding for human review."}
        })
        trace_steps.append({
            "step": 4,
            "event": "llm_completion",
            "content": "Execution halted due to safety limit breach. Escalate to human oversight."
        })
    else:
        trace_steps.append({
            "step": 3,
            "event": "llm_completion",
            "content": f"Successfully completed {domain.replace('_', ' ')} resolution task."
        })

    run_trace = {
        "trace_id": f"tr-sim-{agent_id}",
        "execution_steps": trace_steps
    }

    # Injected defects for 'incomplete' complexity
    if complexity == "incomplete":
        agent_config["human_oversight"] = []  # Empty oversight list
        agent_config["incident_contact"] = {"name": "", "email": "invalid-email-format", "escalation_path": ""}

    return agent_config, tool_manifest, run_trace
