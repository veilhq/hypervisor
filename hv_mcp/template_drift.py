"""
Template drift detection — compares markdown reference templates against
programmatic templates (templates.py) to ensure structural consistency.

Checks section headings, metadata field names, and section order.
Does not compare placeholder content.
"""

import re
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT

from .templates import (
    apply_work_item_template,
    apply_idea_template,
    apply_document_template,
    apply_adr_template,
    apply_bugfix_template,
)

TEMPLATES_DIR = HYPERSPACE_ROOT / "templates"


def _extract_structure(md_text: str) -> dict:
    """Extract structural elements from markdown text.

    Returns:
        dict with 'headings' (ordered list of (level, text)),
        'metadata_fields' (ordered list of field names from dash-prefixed lines).
    """
    lines = md_text.splitlines()
    headings = []
    metadata_fields = []
    past_title = False
    in_metadata = False

    for line in lines:
        stripped = line.strip()

        # Detect headings
        m = re.match(r'^(#{1,6})\s+(.+)', stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            headings.append((level, text))
            if level == 1:
                past_title = True
                in_metadata = True
            else:
                in_metadata = False
            continue

        # Detect horizontal rule (end of metadata block)
        if stripped == "---" and in_metadata:
            in_metadata = False
            continue

        # Detect metadata fields (dash-prefixed: "- Key: value")
        if in_metadata and past_title:
            m = re.match(r'^-\s+([A-Za-z][A-Za-z\s]*?):', stripped)
            if m:
                field_name = m.group(1).strip()
                metadata_fields.append(field_name)

    return {
        "headings": headings,
        "metadata_fields": metadata_fields,
    }


def _normalize_heading(text: str) -> str:
    """Normalize heading text for comparison (strip placeholders, numbers)."""
    # Remove ADR number prefix like "ADR 1: "
    text = re.sub(r'^ADR\s+\d+:\s*', '', text)
    # Remove template placeholders like {Title}, [Title]
    text = re.sub(r'[\{\[].+?[\}\]]', '', text).strip()
    return text.lower()


def _generate_sample(template_type: str) -> str | None:
    """Generate a sample document from the programmatic template."""
    try:
        if template_type == "work-item":
            return apply_work_item_template(
                title="Sample Title",
                description="Sample description.",
                tags=["test"],
                project="General System Development",
                doc_type="Professional",
                overview="As a user, I want something.",
                design="Design details here.",
                acceptance_criteria={"Feature Area": ["Criterion one"]},
                tasks=["Task one"],
                work_id="WI-0",
            )
        elif template_type == "idea":
            return apply_idea_template(
                title="Sample Idea",
                description="Sample idea description.",
                tags=["test"],
                doc_type="Professional",
                concept="The concept goes here.",
                related=["[Link](path.md)"],
            )
        elif template_type == "document":
            return apply_document_template(
                title="Sample Document",
                description="Sample document description.",
                tags=["test"],
                content="## Main Section\n\nContent here.",
                related=["[Link1](a.md)", "[Link2](b.md)", "[Link3](c.md)"],
            )
        elif template_type == "adr":
            return apply_adr_template(
                title="Sample Decision",
                tags=["test"],
                number=1,
                context="Context here.",
                decision="We will do X.",
                rationale="Because Y.",
                consequences="Result Z.",
                related=["[Link](path.md)"],
            )
        elif template_type == "bugfix":
            return apply_bugfix_template(
                title="Sample Bug",
                tags=["test"],
                severity="Medium",
                affected="component/path",
                problem="Problem description.",
                root_cause="Root cause here.",
                fix="Fix description.",
                recommendations="Recommendation here.",
                testing="Test steps here.",
            )
    except Exception:
        return None
    return None


# Map template types to their markdown filenames
TEMPLATE_MAP = {
    "work-item": "work-item-template.md",
    "idea": "idea-template.md",
    "adr": "adr-template.md",
    "bugfix": "bugfix-template.md",
    "document": "hyperspace-document-template.md",
}

# Sections that are intentionally optional in the programmatic output.
# The markdown template includes them as guidance/placeholders, but the MCP
# tool only generates the minimum required structure on creation.
OPTIONAL_SECTIONS = {
    "work-item": {"pr notes"},
    "idea": {"key questions"},
    "adr": {"implementation", "references", "notes"},
    "bugfix": set(),
    "document": {"code examples", "references", "next steps", "document type guidelines"},
}


def check_template_drift() -> dict:
    """Compare markdown templates against programmatic output.

    Returns:
        dict with 'in_sync' (bool), 'drift_detected' (list of issues),
        and 'checked' (count of templates compared).
    """
    drift_issues = []
    checked = 0

    for doc_type, md_filename in TEMPLATE_MAP.items():
        md_path = TEMPLATES_DIR / md_filename
        if not md_path.exists():
            drift_issues.append({
                "type": doc_type,
                "issue": f"Markdown template missing: templates/{md_filename}",
                "severity": "high",
            })
            continue

        # Read markdown template
        md_text = md_path.read_text(encoding="utf-8")
        md_structure = _extract_structure(md_text)

        # Generate programmatic sample
        sample = _generate_sample(doc_type)
        if sample is None:
            drift_issues.append({
                "type": doc_type,
                "issue": "Failed to generate sample from programmatic template.",
                "severity": "high",
            })
            continue

        prog_structure = _extract_structure(sample)
        checked += 1

        # Compare metadata fields
        md_fields = [f.lower() for f in md_structure["metadata_fields"]]
        prog_fields = [f.lower() for f in prog_structure["metadata_fields"]]

        # 'Related' is conditionally placed in metadata (≤2 items) or as a section (>2)
        # so it won't always appear in the metadata block of programmatic output.
        conditional_metadata = {"related"}

        missing_in_prog = [f for f in md_fields if f not in prog_fields and f not in conditional_metadata]
        extra_in_prog = [f for f in prog_fields if f not in md_fields]

        if missing_in_prog:
            drift_issues.append({
                "type": doc_type,
                "issue": f"Metadata fields in markdown template but missing from programmatic: {missing_in_prog}",
                "severity": "medium",
            })
        if extra_in_prog:
            drift_issues.append({
                "type": doc_type,
                "issue": f"Metadata fields in programmatic but missing from markdown template: {extra_in_prog}",
                "severity": "low",
            })

        # Compare H2 section headings (the main structural sections)
        md_h2 = [_normalize_heading(h[1]) for h in md_structure["headings"] if h[0] == 2]
        prog_h2 = [_normalize_heading(h[1]) for h in prog_structure["headings"] if h[0] == 2]

        # Get optional sections for this type
        optional = OPTIONAL_SECTIONS.get(doc_type, set())

        # Check for missing sections (in markdown but not programmatic)
        for section in md_h2:
            if section and section not in prog_h2 and section not in optional:
                drift_issues.append({
                    "type": doc_type,
                    "issue": f"Section '## {section}' in markdown template but missing from programmatic output.",
                    "severity": "medium",
                })

        # Check section order (only compare sections present in both)
        common_sections = [s for s in prog_h2 if s in md_h2]
        md_order = [s for s in md_h2 if s in common_sections]

        if common_sections != md_order:
            drift_issues.append({
                "type": doc_type,
                "issue": f"Section order mismatch. Programmatic: {common_sections}. Markdown template: {md_order}.",
                "severity": "high",
            })

    return {
        "in_sync": len(drift_issues) == 0,
        "checked": checked,
        "drift_detected": drift_issues,
    }
