"""
Stage 8: Exporter — two output formats.

  export_json(card)
      Returns the AgentCard as a pretty-printed JSON string.
      This is the machine-readable format used for API responses
      and database storage.

  export_html(card, annotated_fields, completeness_report=None)
      Renders the Jinja2 template in app/templates/card.html and
      returns a self-contained HTML string.
      Designed to be readable by a non-technical compliance reviewer.
      Includes a Print / Save as PDF button (window.print()).
      The @media print block in the template hides the button and
      nav chrome when printing, and keeps tables readable across breaks.

Both functions accept an AgentCard Pydantic model instance or a
plain dict (from card.model_dump()).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

# pyrefly: ignore [missing-import]
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATES_DIR = Path(__file__).parent / "templates"

_jinja_env: Optional[Environment] = None


def _get_env() -> Environment:
    """Lazy-initialise the Jinja2 environment (once per process)."""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
    return _jinja_env


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_json(card: Any) -> str:
    """
    Return the card as a pretty-printed JSON string.

    Accepts an AgentCard Pydantic model (uses model_dump_json) or any
    object with a model_dump_json method. Falls back to json.dumps for
    plain dicts.
    """
    if hasattr(card, "model_dump_json"):
        return card.model_dump_json(indent=2)

    import json
    return json.dumps(card, indent=2, default=str)


def export_html(
    card: Any,
    annotated_fields: Dict[str, Any],
    completeness_report: Optional[Any] = None,
    generated_by: str = "Agent Compliance Card Generator v1.0",
) -> str:
    """
    Render the compliance card as an HTML document.

    Parameters
    ----------
    card
        AgentCard Pydantic model or plain dict (model.model_dump()).
    annotated_fields
        Output of regulation_mapper.annotate_card(card.model_dump()).
        Shape: {field_name: {"value": ..., "citations": [...]}}
    completeness_report
        Optional CompletenessReport from completeness.check_card().
        If provided, issues are shown in an amber warning banner.
    generated_by
        Attribution string shown in the document metadata footer.

    Returns
    -------
    str
        Complete self-contained HTML document string.
    """
    # Normalise card to plain dict so the template uses simple attribute access
    if hasattr(card, "model_dump"):
        card_dict: Dict[str, Any] = card.model_dump()
    else:
        card_dict = dict(card)

    # Stringify the datetime for display (Jinja2 can't slice datetime objects)
    if "generated_at" in card_dict and card_dict["generated_at"] is not None:
        card_dict["generated_at"] = str(card_dict["generated_at"])

    template = _get_env().get_template("card.html")
    return template.render(
        card=card_dict,
        annotated=annotated_fields,
        report=completeness_report,
        generated_by=generated_by,
    )


# ---------------------------------------------------------------------------
# Convenience wrapper: generate both formats in one call
# ---------------------------------------------------------------------------

def export_both(
    card: Any,
    annotated_fields: Dict[str, Any],
    completeness_report: Optional[Any] = None,
) -> Dict[str, str]:
    """
    Return a dict with both export formats:
        {"json": "<json string>", "html": "<html string>"}
    """
    return {
        "json": export_json(card),
        "html": export_html(card, annotated_fields, completeness_report),
    }


# ---------------------------------------------------------------------------
# Standalone test — run:
#   python app/document.py
#
# Expected output:
#   - Full card JSON printed to terminal
#   - simple_card.html written to the project root
#   - A file:// URL you can paste into a browser to test the print button
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    from pathlib import Path as P

    sys.path.insert(0, str(P(__file__).parent))

    from generator import generate_agent_card
    from regulation_mapper import annotate_card
    from completeness import check_card

    root = P(__file__).parent.parent
    fixtures = root / "fixtures" / "simple"

    print("Generating card from simple fixture (LLM call in progress)...")
    card = generate_agent_card(
        config_path=fixtures / "agent_config.json",
        manifest_path=fixtures / "tool_manifest.json",
        trace_path=fixtures / "run_trace.json",
    )

    # Annotate + check
    annotated = annotate_card(card.model_dump())
    report = check_card(card)

    # ── JSON export ──────────────────────────────────────────────────
    json_output = export_json(card)
    print("\n" + "=" * 68)
    print("JSON OUTPUT")
    print("=" * 68)
    print(json_output)

    # ── HTML export ──────────────────────────────────────────────────
    html_output = export_html(card, annotated, report)

    out_path = root / "simple_card.html"
    out_path.write_text(html_output, encoding="utf-8")

    print("\n" + "=" * 68)
    print("HTML OUTPUT")
    print("=" * 68)
    print(f"Saved to : {out_path}")
    print(f"Open in browser : file:///{out_path.as_posix()}")
    print(f"HTML size       : {len(html_output):,} bytes")
    print(f"Completeness    : {'PASS' if report.is_complete else f'FAIL ({len(report.issues)} issues)'}")
    print("=" * 68)
    print("\nOpen the file URL above in Chrome or Edge, then click")
    print("'Print / Save as PDF' to test the print layout.")
