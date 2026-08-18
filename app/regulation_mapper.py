"""
Stage 4: Regulation mapper — static, hand-authored, deterministic.

Maps every AgentCard field name to the regulatory obligations it satisfies.
Three frameworks are cited:
  - EU AI Act (Regulation (EU) 2024/1689) — primarily Article 13 (transparency
    and information for deployers) and Article 14 (human oversight), with
    supporting references to Articles 9, 10, and 73.
  - NIST AI RMF (NIST AI 100-1, 2023) — four core functions: GOVERN, MAP,
    MEASURE, MANAGE.
  - ISO/IEC 42001:2023 — main clauses (6, 7, 8, 9) and Annex A controls
    (A.2–A.9).

WARNING: These citations are hardcoded on purpose. A hallucinated clause number
in a compliance document is a real legal risk. Do NOT replace this dict with
LLM output. If you need to add or correct a citation, edit this file directly
and record why in a comment.

Citation format used throughout:
  EU AI Act  → "EU AI Act Art. <article>(<paragraph>)" or sub-clause
  NIST AI RMF → "NIST AI RMF <FUNCTION> <ID>"
  ISO 42001  → "ISO 42001 Clause <n>" or "ISO 42001 Annex A <control>"
"""

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# The regulation map
# Key   = exact AgentCard field name (must match schema.py)
# Value = list of citation strings (EU AI Act, NIST AI RMF, ISO 42001)
# ---------------------------------------------------------------------------

REGULATION_MAP: Dict[str, List[str]] = {

    # ------------------------------------------------------------------
    # Identity & versioning fields
    # ------------------------------------------------------------------

    "agent_id": [
        # Art. 13(3)(a): provider/system identity must be documented
        "EU AI Act Art. 13(3)(a) — identity of the AI system and its provider",
        # Accountability requires a uniquely identifiable system
        "NIST AI RMF GOVERN 1.2 — accountability structures assign responsibility to identifiable systems",
        # Documented information must identify the AI system unambiguously
        "ISO 42001 Clause 7.5 — documented information shall include identification of the AI system",
        "ISO 42001 Annex A.9.1 — AI system documentation shall enable traceability",
    ],

    "agent_name": [
        "EU AI Act Art. 13(3)(a) — the name and contact details of the provider",
        "NIST AI RMF GOVERN 1.2 — organizational accountability requires named systems",
        "ISO 42001 Clause 7.5 — documented information shall identify the subject AI system",
    ],

    "version": [
        # Art. 13(3)(c): any pre-determined changes must be documented at
        # the time of conformity assessment; versioning is the mechanism
        "EU AI Act Art. 13(3)(c) — pre-determined changes to the high-risk AI system shall be documented",
        "NIST AI RMF GOVERN 1.1 — policies and processes shall track system versions over time",
        # ISO 42001 requires controlled documents; version is the control mechanism
        "ISO 42001 Clause 7.5.3 — control of documented information includes version management",
        "ISO 42001 Annex A.3.2 — AI system lifecycle documentation shall record version history",
    ],

    "generated_at": [
        "EU AI Act Art. 13(3)(c) — documentation shall reflect the state of the system at assessment time",
        "NIST AI RMF GOVERN 1.1 — dated documentation is required for audit and accountability",
        "ISO 42001 Clause 7.5.3 — documented information shall carry date of creation or revision",
    ],

    # ------------------------------------------------------------------
    # Core purpose & capability fields
    # ------------------------------------------------------------------

    "purpose_and_scope": [
        # Art. 13(3)(b)(i): the intended purpose of the high-risk AI system
        # must be clearly described so deployers understand what it is for
        "EU AI Act Art. 13(3)(b)(i) — documentation shall describe the intended purpose of the AI system",
        # Art. 13(1): transparency to enable deployers to interpret outputs correctly
        "EU AI Act Art. 13(1) — system shall be transparent enough for deployers to use appropriately",
        "NIST AI RMF MAP 1.1 — context for AI use, including intended purpose, shall be established and documented",
        # Annex A.4.1 covers documentation of intended use and context of use
        "ISO 42001 Annex A.4.1 — intended use and context of the AI system shall be documented",
        # A.9.2 requires that information given to users describes what the system does
        "ISO 42001 Annex A.9.2 — information provided to users shall accurately describe system purpose",
    ],

    "llm": [
        # Art. 13(3)(b): characteristics and capabilities of the system must be
        # described; the underlying model is a core capability characteristic
        "EU AI Act Art. 13(3)(b) — characteristics and technical capabilities of the AI system shall be documented",
        # Art. 13(3)(d): hardware and software requirements (the LLM is the primary software component)
        "EU AI Act Art. 13(3)(d) — hardware and software requirements, including the AI model, shall be specified",
        "NIST AI RMF MEASURE 1.1 — approaches for measurement of AI risks require knowing the model in use",
        # A.4.2 requires the specification of the AI system including its components
        "ISO 42001 Annex A.4.2 — specification of the AI system shall identify the model and its version",
        "ISO 42001 Annex A.9.1 — documentation shall identify the AI system components and their versions",
    ],

    "tool_inventory": [
        # Art. 13(3)(b): capabilities include what the system can do via tools
        "EU AI Act Art. 13(3)(b) — the capabilities and limitations of the AI system shall be documented",
        # Art. 13(3)(b)(i): intended purpose includes the actions the agent can take
        "EU AI Act Art. 13(3)(b)(i) — the intended purpose encompasses the operations the agent performs",
        # MAP 2.1: scientific context includes the tools and integrations in scope
        "NIST AI RMF MAP 2.1 — the AI system's technical context, including tools and integrations, shall be documented",
        "ISO 42001 Annex A.4.2 — the specification of the AI system shall enumerate its functional components and capabilities",
        "ISO 42001 Annex A.9.1 — AI system documentation shall cover all components relevant to its operation",
    ],

    "data_sources": [
        # Art. 13(3)(b)(vii): input data specifications must be described,
        # including provenance, to allow deployers to assess reliability
        "EU AI Act Art. 13(3)(b)(vii) — input data specifications, including data types and sources, shall be documented",
        # Art. 10: training, validation, and test data governance applies to
        # data the system ingests at runtime as well as at training time
        "EU AI Act Art. 10 — data governance practices shall cover all data processed by the AI system",
        # MAP 1.5: organisational risk tolerance is informed by data sensitivity levels
        "NIST AI RMF MAP 1.5 — organizational risk tolerances shall be informed by the sensitivity and provenance of data inputs",
        # A.5.1: data management for AI systems
        "ISO 42001 Annex A.5.1 — data for AI systems shall be identified, documented, and governed",
        # A.5.4: data quality criteria must be stated
        "ISO 42001 Annex A.5.4 — data quality criteria applicable to each data source shall be documented",
    ],

    # ------------------------------------------------------------------
    # Authority & oversight fields
    # ------------------------------------------------------------------

    "decision_authority": [
        # Art. 14: human oversight requirements depend directly on the level
        # of autonomy — autonomous agents carry stronger oversight obligations
        "EU AI Act Art. 14(1) — high-risk AI systems shall enable effective human oversight commensurate with their decision authority",
        # Art. 14(4): humans must retain the ability to override the system
        "EU AI Act Art. 14(4) — deployers shall be able to decide not to use or to override the AI system's output",
        # GOVERN 4.1 covers policies for autonomous vs. human-in-the-loop decisions
        "NIST AI RMF GOVERN 4.1 — organizational policies shall define the level of human agency for each AI decision type",
        # A.2.2: impact assessment considers the degree of automation
        "ISO 42001 Annex A.2.2 — AI system impact assessment shall consider the degree of autonomous decision-making",
    ],

    "human_oversight": [
        # Art. 14(1): systems must be designed so humans can oversee them
        "EU AI Act Art. 14(1) — high-risk AI systems shall be designed to be effectively overseen by natural persons",
        # Art. 14(3): documentation must describe the measures enabling oversight
        "EU AI Act Art. 14(3) — technical measures enabling human oversight shall be documented in the instructions for use",
        # Art. 14(3)(b): humans must be able to detect and address AI failures
        "EU AI Act Art. 14(3)(b) — the AI system shall enable humans to detect and address anomalies, failures, and unexpected behaviour",
        # MANAGE 2.2: mechanisms to sustain oversight must be operational, not just documented
        "NIST AI RMF MANAGE 2.2 — mechanisms to sustain and monitor identified AI risks shall be implemented and tracked",
        # A.6.1: risk management includes human controls as risk treatments
        "ISO 42001 Annex A.6.1 — risk management measures shall include human oversight mechanisms where appropriate",
        # Clause 8.3: risk treatment plans must be implemented and maintained
        "ISO 42001 Clause 8.3 — the organization shall implement the AI risk treatment plan",
    ],

    # ------------------------------------------------------------------
    # Risk & limitations fields
    # ------------------------------------------------------------------

    "risk_classification": [
        # Art. 9(2): a risk management system is mandatory for high-risk AI;
        # the classification determines which obligations apply
        "EU AI Act Art. 9(2) — a risk management system shall be established covering the full lifecycle of the AI system",
        # Art. 6: the classification rules for high-risk AI determine the regulatory tier
        "EU AI Act Art. 6 — classification of high-risk AI systems shall follow the criteria in Annex III",
        # MAP 5.1: likelihood and magnitude of harm must be estimated per risk class
        "NIST AI RMF MAP 5.1 — likelihood and magnitude of each identified harm shall be estimated and documented",
        # Clause 6.1.2: the AI risk assessment process produces a classification
        "ISO 42001 Clause 6.1.2 — the organization shall conduct an AI risk assessment and document risk levels",
        # A.6.2: risk treatment choices follow from the classification
        "ISO 42001 Annex A.6.2 — AI risk treatment shall be proportionate to the identified risk classification",
    ],

    "known_limitations": [
        # Art. 13(3)(b)(iii): known or foreseeable circumstances that may
        # affect accuracy or reliability must be disclosed to deployers
        "EU AI Act Art. 13(3)(b)(iii) — known or foreseeable limitations affecting performance shall be disclosed",
        # Art. 13(3)(b)(v): circumstances related to use that could affect the system must be stated
        "EU AI Act Art. 13(3)(b)(v) — foreseeable circumstances of use that could affect system output shall be documented",
        # MEASURE 2.5: regular evaluation must surface and record limitations
        "NIST AI RMF MEASURE 2.5 — the AI system shall be regularly evaluated for trustworthiness; identified limitations shall be recorded",
        # A.4.2: specification shall include out-of-scope conditions
        "ISO 42001 Annex A.4.2 — the AI system specification shall document known limitations and conditions of use",
    ],

    # ------------------------------------------------------------------
    # Accountability & incident fields
    # ------------------------------------------------------------------

    "incident_contact": [
        # Art. 13(3)(a): provider identity and contact details are mandatory
        "EU AI Act Art. 13(3)(a) — the identity and contact details of the provider shall be included in the system documentation",
        # Art. 73: providers of high-risk AI must report serious incidents;
        # the contact is the operational entry-point for that obligation
        "EU AI Act Art. 73 — providers shall report serious incidents to the relevant national authority; an incident contact is required",
        # MANAGE 1.1: a risk treatment plan includes escalation and incident response contacts
        "NIST AI RMF MANAGE 1.1 — a risk treatment plan shall identify responsible parties and escalation paths for AI incidents",
        # A.7.1: incident management requires a named contact and escalation procedure
        "ISO 42001 Annex A.7.1 — the organization shall establish an AI incident management process with documented contacts and escalation paths",
    ],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def annotate_card(card_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Takes a card serialised as a plain dict (e.g. card.model_dump()) and
    returns an annotated version where every top-level field is paired with
    its regulatory citations.

    Fields not present in REGULATION_MAP are included with an empty list so
    the caller can detect coverage gaps.

    Example output shape:
    {
      "purpose_and_scope": {
        "value": "Reads incoming support tickets...",
        "citations": ["EU AI Act Art. 13(3)(b)(i) — ...", ...]
      },
      ...
    }
    """
    annotated: Dict[str, Any] = {}
    for field_name, value in card_dict.items():
        annotated[field_name] = {
            "value": value,
            "citations": REGULATION_MAP.get(field_name, []),
        }
    return annotated


def get_citations(field_name: str) -> List[str]:
    """Return the citation list for a single field. Returns [] if unmapped."""
    return REGULATION_MAP.get(field_name, [])


def unmapped_fields(card_dict: Dict[str, Any]) -> List[str]:
    """Return field names present in the card but absent from REGULATION_MAP."""
    return [f for f in card_dict if f not in REGULATION_MAP]


# ---------------------------------------------------------------------------
# Quick standalone check — run:
#   python app/regulation_mapper.py
# Expected output: every AgentCard field printed with ≥1 citation.
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

    from schema import AgentCard

    # Collect every field name declared in the AgentCard schema
    all_fields = list(AgentCard.model_fields.keys())

    print("=" * 70)
    print(f"Regulation coverage check — {len(all_fields)} AgentCard fields")
    print("=" * 70)

    missing: list[str] = []
    for field in all_fields:
        citations = REGULATION_MAP.get(field, [])
        status = "OK" if citations else "MISSING"
        if not citations:
            missing.append(field)
        print(f"\n[{status}] {field}")
        for c in citations:
            print(f"    • {c}")

    print("\n" + "=" * 70)
    if missing:
        print(f"FAIL — {len(missing)} field(s) have no citations: {missing}")
        sys.exit(1)
    else:
        print(f"PASS — all {len(all_fields)} fields have at least one citation.")
        print(f"Total citations across all fields: "
              f"{sum(len(v) for v in REGULATION_MAP.values())}")
