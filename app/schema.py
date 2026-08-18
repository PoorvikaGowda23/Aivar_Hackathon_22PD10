"""
Step 1: Agent Compliance Card schema.

This defines the structure every generated card must follow. Every other
module (generator, regulation mapper, completeness checker, exporter)
reads and writes objects that conform to this schema — get this right
first and everything downstream gets validation for free.

Covers exactly the fields the problem statement asks for:
purpose and scope, LLM used with version, tool inventory (operations +
data access), data sources, decision authority, human oversight
mechanisms, risk classification, known limitations, incident contact.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

# pyrefly: ignore [missing-import]
from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Enums — controlled vocabularies keep the card machine-checkable, not just
# human-readable. Free-text fields are used only where the value is
# genuinely open-ended (e.g. a limitation description).
# ---------------------------------------------------------------------------

class DecisionAuthority(str, Enum):
    INFORMATIONAL = "informational"   # agent only surfaces information
    ADVISORY = "advisory"             # agent recommends, a human decides
    AUTONOMOUS = "autonomous"         # agent acts without human sign-off


class RiskClassification(str, Enum):
    MINIMAL = "minimal"
    LIMITED = "limited"
    HIGH = "high"
    UNACCEPTABLE = "unacceptable"     # mirrors EU AI Act risk tiers


# ---------------------------------------------------------------------------
# Sub-objects
# ---------------------------------------------------------------------------

class LLMInfo(BaseModel):
    provider: str = Field(..., examples=["Anthropic", "OpenAI", "AWS Bedrock"])
    model_name: str = Field(..., examples=["claude-sonnet-4-6"])
    version: str = Field(..., examples=["4.6", "2024-10-01"])
    hosting: Optional[str] = Field(
        None, examples=["Anthropic API", "AWS Bedrock (us-east-1)"]
    )


class ToolEntry(BaseModel):
    name: str
    description: str
    operations: List[str] = Field(
        default_factory=list,
        description="What the tool can DO, e.g. ['read_email', 'send_email']",
    )
    data_accessed: List[str] = Field(
        default_factory=list,
        description="What data the tool touches, e.g. ['customer PII', 'order history']",
    )


class DataSource(BaseModel):
    name: str
    data_type: str = Field(..., examples=["structured DB", "document store", "live API"])
    sensitivity: str = Field(..., examples=["public", "internal", "confidential", "PII"])


class HumanOversightMechanism(BaseModel):
    description: str = Field(..., examples=["All autonomous actions require manager approval"])
    trigger: Optional[str] = Field(
        None, description="What condition triggers human review, if any"
    )


class IncidentContact(BaseModel):
    name: str
    email: EmailStr
    escalation_path: Optional[str] = Field(
        None, examples=["Slack #ai-incidents, then on-call via PagerDuty"]
    )


# ---------------------------------------------------------------------------
# Top-level Agent Card
# ---------------------------------------------------------------------------

class AgentCard(BaseModel):
    agent_id: str
    agent_name: str
    version: int = 1
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    purpose_and_scope: str = Field(
        ..., description="Plain-language description of what the agent does and its boundaries"
    )
    llm: LLMInfo
    tool_inventory: List[ToolEntry] = Field(default_factory=list)
    data_sources: List[DataSource] = Field(default_factory=list)
    decision_authority: Optional[DecisionAuthority] = None
    human_oversight: List[HumanOversightMechanism] = Field(default_factory=list)
    risk_classification: Optional[RiskClassification] = None
    known_limitations: List[str] = Field(default_factory=list)
    incident_contact: Optional[IncidentContact] = None

    model_config = ConfigDict(use_enum_values=True)


# ---------------------------------------------------------------------------
# Quick manual check — run this file directly to confirm the schema works
# before wiring it into anything else.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    example = AgentCard(
        agent_id="agent-001",
        agent_name="Customer Support Triage Agent",
        purpose_and_scope=(
            "Reads incoming support tickets, classifies urgency, and drafts "
            "a first-response reply for human review. Does not send replies "
            "or modify customer records directly."
        ),
        llm=LLMInfo(provider="Anthropic", model_name="claude-sonnet-4-6", version="4.6"),
        tool_inventory=[
            ToolEntry(
                name="ticket_reader",
                description="Reads ticket content and metadata",
                operations=["read_ticket"],
                data_accessed=["customer name", "ticket body"],
            ),
            ToolEntry(
                name="draft_writer",
                description="Drafts a reply for a human agent to review",
                operations=["create_draft"],
                data_accessed=["ticket body"],
            ),
        ],
        data_sources=[
            DataSource(name="Zendesk", data_type="live API", sensitivity="confidential"),
        ],
        decision_authority=DecisionAuthority.ADVISORY,
        human_oversight=[
            HumanOversightMechanism(
                description="A human agent must approve every draft before it is sent",
                trigger="Every ticket",
            )
        ],
        risk_classification=RiskClassification.LIMITED,
        known_limitations=[
            "May misclassify urgency for tickets in languages other than English",
        ],
        incident_contact=IncidentContact(
            name="AI Platform Team",
            email="ai-incidents@example.com",
            escalation_path="Slack #ai-incidents, then on-call via PagerDuty",
        ),
    )

    print(example.model_dump_json(indent=2))