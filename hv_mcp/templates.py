"""
Document template generators — produce markdown content for each document type.
"""

import re
from datetime import datetime


def _normalize_newlines(text: str | None) -> str | None:
    """Replace literal backslash-n sequences with real newlines.

    MCP tool inputs sometimes arrive with escaped newline characters (the two-char
    sequence '\\n') instead of actual newline bytes. This normalises both forms so
    template output always contains real line breaks.
    """
    if text is None:
        return None
    return text.replace("\\n", "\n")


def _demote_headings(text: str) -> str:
    """Demote markdown headings by one level so they nest inside their parent section.

    H2 (##) becomes H3 (###), H3 becomes H4, etc. This prevents freeform content
    from breaking out of its parent H2 section in the rendered site (which wraps
    each H2 in a collapsible <details> block).
    """
    # Process line-by-line; only lines starting with # are headings
    lines = text.split("\n")
    result = []
    for line in lines:
        match = re.match(r'^(#{2,6})\s', line)
        if match:
            # Add one more # to demote by one level (cap at H6)
            hashes = match.group(1)
            if len(hashes) < 6:
                line = "#" + line
        result.append(line)
    return "\n".join(result)


def apply_work_item_template(
    title: str, description: str, tags: list[str], project: str,
    doc_type: str, overview: str, design: str | None = None,
    acceptance_criteria: dict | None = None, tasks: list[str] | None = None,
    work_id: str | None = None,
) -> str:
    """Generate a work-item markdown document."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    overview = _normalize_newlines(overview)
    design = _normalize_newlines(design)
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(description)
    lines.append("")
    lines.append(f"- Created: {now}")
    lines.append(f"- Updated: {now}")
    lines.append(f"- Tags: {', '.join(tags)}")
    if work_id:
        lines.append(f"- ID: {work_id}")
    lines.append(f"- Type: {doc_type}")
    lines.append("- Status: Planned")
    lines.append(f"- Project: {project}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(overview)
    lines.append("")

    if design:
        design = _demote_headings(design)
        lines.append("---")
        lines.append("")
        lines.append("## Design")
        lines.append("")
        lines.append(design)
        lines.append("")

    if acceptance_criteria:
        lines.append("---")
        lines.append("")
        lines.append("## Acceptance Criteria")
        lines.append("")
        for section_name, criteria in acceptance_criteria.items():
            lines.append(f"### {section_name}")
            for criterion in criteria:
                lines.append(f"- {criterion}")
            lines.append("")

    if tasks:
        lines.append("---")
        lines.append("")
        lines.append("## Tasks")
        lines.append("")
        for task in tasks:
            lines.append(f"- [ ] {task}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Implementation Notes")
    lines.append("")
    lines.append("> [!NOTE]")
    lines.append("> Populate this section during implementation. Capture decisions that differ from the original design.")
    lines.append("")

    return "\n".join(lines)


def apply_idea_template(
    title: str, description: str, tags: list[str], doc_type: str, concept: str,
    key_questions: list[str] | None = None, related: list[str] | None = None,
    solution_plan: str | None = None, problem: str | None = None,
) -> str:
    """Generate an idea markdown document."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    concept = _normalize_newlines(concept)
    concept = _demote_headings(concept)
    problem = _normalize_newlines(problem)
    if problem:
        problem = _demote_headings(problem)
    solution_plan = _normalize_newlines(solution_plan)
    if solution_plan:
        solution_plan = _demote_headings(solution_plan)
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(description)
    lines.append("")
    lines.append(f"- Created: {now}")
    lines.append(f"- Updated: {now}")
    lines.append(f"- Tags: {', '.join(tags)}")
    lines.append(f"- Type: {doc_type}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Problem")
    lines.append("")
    if problem:
        lines.append(problem)
    else:
        lines.append("_To be defined — what's broken, missing, or painful today?_")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Concept")
    lines.append("")
    lines.append(concept)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Rough Solution Plan")
    lines.append("")
    if solution_plan:
        lines.append(solution_plan)
    else:
        lines.append("_To be filled in — high-level approach, major steps, or implementation sketch._")
    lines.append("")
    if key_questions:
        lines.append("---")
        lines.append("")
        lines.append("## Key Questions")
        lines.append("")
        for q in key_questions:
            lines.append(f"- {q}")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Related")
    lines.append("")
    if related:
        for link in related:
            lines.append(f"- {link}")
        lines.append("")

    return "\n".join(lines)


def apply_document_template(
    title: str, description: str, tags: list[str], content: str,
    related: list[str] | None = None,
) -> str:
    """Generate a general document (research, context, patterns)."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    content = _normalize_newlines(content)
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(description)
    lines.append("")
    lines.append(f"- Created: {now}")
    lines.append(f"- Updated: {now}")
    lines.append(f"- Tags: {', '.join(tags)}")
    if related and len(related) <= 2:
        lines.append(f"- Related: {', '.join(related)}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(content)
    lines.append("")

    if related and len(related) > 2:
        lines.append("---")
        lines.append("")
        lines.append("## Related")
        lines.append("")
        for link in related:
            lines.append(f"- {link}")
        lines.append("")

    return "\n".join(lines)


def apply_adr_template(
    title: str, tags: list[str], number: int, context: str,
    decision: str, rationale: str, consequences: str | None = None,
    related: list[str] | None = None,
) -> str:
    """Generate an ADR document."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    context = _normalize_newlines(context)
    decision = _normalize_newlines(decision)
    rationale = _normalize_newlines(rationale)
    consequences = _normalize_newlines(consequences)
    lines = []
    lines.append(f"# ADR {number}: {title}")
    lines.append("")
    lines.append(f"Architecture decision record for {title.lower()}.")
    lines.append("")
    lines.append(f"- Created: {now}")
    lines.append(f"- Updated: {now}")
    lines.append(f"- Tags: {', '.join(tags)}")
    lines.append("- Status: Proposed")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Context")
    lines.append("")
    lines.append(context)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Decision")
    lines.append("")
    lines.append(decision)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Rationale")
    lines.append("")
    lines.append(rationale)
    lines.append("")

    if consequences:
        lines.append("---")
        lines.append("")
        lines.append("## Consequences")
        lines.append("")
        lines.append(consequences)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Related")
    lines.append("")
    if related:
        for link in related:
            lines.append(f"- {link}")
        lines.append("")

    return "\n".join(lines)


def apply_bugfix_template(
    title: str, tags: list[str], severity: str, affected: str,
    problem: str, root_cause: str, fix: str,
    testing: str | None = None, recommendations: str | None = None,
) -> str:
    """Generate a bugfix investigation document."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    problem = _normalize_newlines(problem)
    root_cause = _normalize_newlines(root_cause)
    fix = _normalize_newlines(fix)
    testing = _normalize_newlines(testing)
    recommendations = _normalize_newlines(recommendations)
    lines = []
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Bug investigation: {title.lower()}.")
    lines.append("")
    lines.append(f"- Created: {now}")
    lines.append(f"- Updated: {now}")
    lines.append(f"- Tags: {', '.join(tags)}")
    lines.append("- Status: Identified")
    lines.append(f"- Severity: {severity}")
    lines.append(f"- Affected: {affected}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Problem Description")
    lines.append("")
    lines.append(problem)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Root Cause")
    lines.append("")
    lines.append(root_cause)
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## The Fix")
    lines.append("")
    lines.append(fix)
    lines.append("")

    if recommendations:
        lines.append("---")
        lines.append("")
        lines.append("## Additional Recommendations")
        lines.append("")
        lines.append(recommendations)
        lines.append("")

    if testing:
        lines.append("---")
        lines.append("")
        lines.append("## Testing")
        lines.append("")
        lines.append(testing)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Related")
    lines.append("")

    return "\n".join(lines)
