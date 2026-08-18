"""
Stage 7: Completeness checker — rule-based, no LLM.

Iterates every field of an AgentCard (recursing into nested sub-objects and
list items) and flags any of the following:

  NULL        — field value is None (required field not populated)
  EMPTY       — empty string ("") or empty list ([])
  PLACEHOLDER — value exactly matches the blocklist (case-insensitive, stripped):
                "TBD", "N/A", "NA", "PLACEHOLDER", "TODO", "FIXME", "UNKNOWN"

Uses dot-notation paths to precisely identify every issue
(e.g. "incident_contact.name", "known_limitations[0]").

Returns a CompletenessReport Pydantic model so the result is itself
schema-validated and can be serialised directly to the API response.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List

# pyrefly: ignore [missing-import]
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Placeholder blocklist — exact match after strip + lower-case.
# Add words here; do NOT use 'contains' — too many false positives.
# ---------------------------------------------------------------------------

PLACEHOLDER_BLOCKLIST: frozenset[str] = frozenset(
    {"tbd", "n/a", "na", "placeholder", "todo", "fixme", "unknown", "none"}
)


class IssueType(str, Enum):
    NULL = "null"              # field is None where a value is expected
    EMPTY = "empty"            # empty string or empty list
    PLACEHOLDER = "placeholder"  # matches the blocklist


class CompletenessIssue(BaseModel):
    field: str          # dot-notation path, e.g. "incident_contact.name"
    issue_type: IssueType
    value: Any          # the offending value (None, "", [], "TODO", …)
    message: str        # human-readable explanation for the compliance reviewer


class CompletenessReport(BaseModel):
    agent_id: str
    agent_name: str
    is_complete: bool               # True only when issues list is empty
    issues: List[CompletenessIssue]
    checked_at: datetime = None     # set automatically

    def model_post_init(self, __context: Any) -> None:
        if self.checked_at is None:
            self.checked_at = datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _is_placeholder(value: str) -> bool:
    """Return True if value is exactly a known placeholder token."""
    return value.strip().lower() in PLACEHOLDER_BLOCKLIST


# Fields whose None value is explicitly optional in the schema — skipped.
# These are sub-object fields annotated Optional[str] = None by design.
_OPTIONAL_NONE_OK: frozenset[str] = frozenset(
    {
        "llm.hosting",                       # LLMInfo.hosting is Optional
        "human_oversight[*].trigger",        # HumanOversightMechanism.trigger is Optional
        "incident_contact.escalation_path",  # IncidentContact.escalation_path is Optional
    }
)


def _path_matches_optional(path: str) -> bool:
    """
    Return True if the dot-notation path is in the deliberately-optional set.
    Handles wildcard patterns like 'human_oversight[*].trigger'.
    """
    import re
    for pattern in _OPTIONAL_NONE_OK:
        # Convert [*] wildcard to a regex that matches any [N]
        regex = re.escape(pattern).replace(r"\[\*\]", r"\[\d+\]")
        if re.fullmatch(regex, path):
            return True
    return False


def _check_value(value: Any, path: str) -> List[CompletenessIssue]:
    """
    Recursively inspect a value at the given dot-notation path.
    Returns a list of CompletenessIssue objects (empty = clean).
    """
    issues: List[CompletenessIssue] = []

    # ── None ────────────────────────────────────────────────────────────────
    if value is None:
        if not _path_matches_optional(path):
            issues.append(CompletenessIssue(
                field=path,
                issue_type=IssueType.NULL,
                value=None,
                message=f"'{path}' is null — this field must be populated before the card is used for compliance purposes.",
            ))
        return issues  # nothing more to check on None

    # ── String ──────────────────────────────────────────────────────────────
    if isinstance(value, str):
        if value.strip() == "":
            issues.append(CompletenessIssue(
                field=path,
                issue_type=IssueType.EMPTY,
                value=value,
                message=f"'{path}' is an empty string.",
            ))
        elif _is_placeholder(value):
            issues.append(CompletenessIssue(
                field=path,
                issue_type=IssueType.PLACEHOLDER,
                value=value,
                message=(
                    f"'{path}' contains the placeholder value \"{value}\". "
                    "Replace with an actual value before submitting for compliance review."
                ),
            ))
        return issues

    # ── List ─────────────────────────────────────────────────────────────────
    if isinstance(value, list):
        if len(value) == 0:
            issues.append(CompletenessIssue(
                field=path,
                issue_type=IssueType.EMPTY,
                value=[],
                message=(
                    f"'{path}' is an empty list. "
                    "At least one entry is expected for a complete compliance card."
                ),
            ))
            return issues  # no items to recurse into
        # Recurse into each list item
        for idx, item in enumerate(value):
            issues.extend(_check_value(item, f"{path}[{idx}]"))
        return issues

    # ── Dict (sub-object serialised by model_dump) ───────────────────────────
    if isinstance(value, dict):
        for key, sub_value in value.items():
            issues.extend(_check_value(sub_value, f"{path}.{key}"))
        return issues

    # ── Scalar (int, float, bool, datetime) — structurally fine ─────────────
    return issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_card(card: Any) -> CompletenessReport:
    """
    Run the completeness check on an AgentCard (Pydantic model).

    Accepts either an AgentCard instance or a plain dict (card.model_dump()).
    Returns a CompletenessReport with all issues found.
    """
    # Normalise to plain dict so we don't depend on Pydantic internals
    if hasattr(card, "model_dump"):
        card_dict: Dict[str, Any] = card.model_dump()
    else:
        card_dict = dict(card)

    agent_id = card_dict.get("agent_id", "<unknown>")
    agent_name = card_dict.get("agent_name", "<unknown>")

    all_issues: List[CompletenessIssue] = []

    for field_name, value in card_dict.items():
        all_issues.extend(_check_value(value, field_name))

    return CompletenessReport(
        agent_id=agent_id,
        agent_name=agent_name,
        is_complete=len(all_issues) == 0,
        issues=all_issues,
    )


def summarise(report: CompletenessReport) -> str:
    """
    Return a compact human-readable summary of the report for CLI output.
    Does not use any Unicode characters that cp1252 cannot encode.
    """
    lines: List[str] = []
    label = "PASS" if report.is_complete else "FAIL"
    lines.append(f"[{label}] {report.agent_name} ({report.agent_id})")
    lines.append(f"  Complete : {report.is_complete}")
    lines.append(f"  Issues   : {len(report.issues)}")
    if report.issues:
        lines.append("")
        for issue in report.issues:
            lines.append(f"  [{issue.issue_type.upper()}] {issue.field}")
            lines.append(f"         value   : {issue.value!r}")
            lines.append(f"         message : {issue.message}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Standalone test — run:
#   python app/completeness.py
#
# Expected output:
#   simple fixture   → [PASS] 0 issues
#   incomplete fixture → [FAIL] flagging: risk_classification (null),
#                        human_oversight (empty list),
#                        incident_contact.name ("TODO"),
#                        incident_contact.escalation_path ("N/A")
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).parent))
    from generator import generate_agent_card

    root = Path(__file__).parent.parent

    fixtures = [
        (
            "simple",
            root / "fixtures" / "simple" / "agent_config.json",
            root / "fixtures" / "simple" / "tool_manifest.json",
            root / "fixtures" / "simple" / "run_trace.json",
            False,   # expect_issues
        ),
        (
            "incomplete",
            root / "fixtures" / "incomplete" / "agent_config.json",
            root / "fixtures" / "incomplete" / "tool_manifest.json",
            root / "fixtures" / "incomplete" / "run_trace.json",
            True,    # expect_issues
        ),
    ]

    overall_pass = True

    for fixture_name, config, manifest, trace, expect_issues in fixtures:
        print("=" * 68)
        print(f"Fixture: {fixture_name}")
        print("=" * 68)

        card = generate_agent_card(config, manifest, trace)
        report = check_card(card)

        print(summarise(report))
        print()

        # Validate that the checker behaves as expected
        if expect_issues and report.is_complete:
            print(f"  ERROR: expected issues in '{fixture_name}' but found none!")
            overall_pass = False
        elif not expect_issues and not report.is_complete:
            print(f"  ERROR: expected no issues in '{fixture_name}' but found {len(report.issues)}!")
            overall_pass = False
        else:
            print(f"  Result is as expected.")
        print()

    print("=" * 68)
    if overall_pass:
        print("ALL CHECKS PASSED — completeness checker is working correctly.")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED — see details above.")
        sys.exit(1)
