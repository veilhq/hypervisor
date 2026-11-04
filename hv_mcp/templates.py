"""
Document template generators - produce markdown content for each document type.
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


WORK_ITEM_KINDS = ("story", "spike", "bug")

_TBD = "_To be determined._"


def _render_ac(acceptance_criteria: dict) -> str:
    """Render {area: [criteria]} as H3 groups of plain bullets."""
    out = []
    for section_name, criteria in acceptance_criteria.items():
        out.append(f"### {section_name}")
        out.extend(f"- {criterion}" for criterion in criteria)
        out.append("")
    return "\n".join(out).rstrip()


def _kind_sections(
    kind: str, problem, root_cause, location, fix, testing,
    question, time_box, findings, recommendations, acceptance_criteria,
) -> list[tuple[str, str]]:
    """Return the (heading, body) sections that replace Design for bugs and spikes."""
    ac = [("Acceptance Criteria", _render_ac(acceptance_criteria))] if acceptance_criteria else []
    if kind == "bug":
        return [
            ("Problem", _demote_headings(problem or _TBD)),
            ("Root Cause", _demote_headings(root_cause or _TBD)),
            ("Location", location or "Blame unavailable: no file or line range was given."),
            ("Fix", _demote_headings(fix or _TBD)),
            *ac,
            ("Testing", _demote_headings(testing or _TBD)),
        ]
    if kind == "spike":
        return [
            ("Question", _demote_headings(question or _TBD)),
            ("Time-box", time_box or _TBD),
            *ac,
            ("Findings", _demote_headings(findings or _TBD)),
            ("Recommendation", _demote_headings(recommendations or _TBD)),
        ]
    return []


def apply_work_item_template(
    title: str, description: str, tags: list[str], project: str,
    doc_type: str, overview: str, design: str | None = None,
    acceptance_criteria: dict | None = None, tasks: list[str] | None = None,
    work_id: str | None = None, open_questions: list[str] | None = None,
    assignee: str = "Josh Wooten", horizon: str = "Backlog",
    kind: str = "story", feature: str | None = None,
    problem: str | None = None, root_cause: str | None = None,
    location: str | None = None, fix: str | None = None,
    testing: str | None = None, question: str | None = None,
    time_box: str | None = None, findings: str | None = None,
    recommendations: str | None = None,
) -> str:
    """Generate a work-item markdown document (story, spike, or bug)."""
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    overview = _normalize_newlines(overview)
    design = _normalize_newlines(design)
    problem, root_cause, fix, testing, question, findings, recommendations = (
        _normalize_newlines(v) for v in
        (problem, root_cause, fix, testing, question, findings, recommendations)
    )
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
    lines.append(f"- Kind: {kind.title()}")
    lines.append(f"- Type: {doc_type}")
    lines.append("- Status: Planned")
    lines.append(f"- Project: {project}")
    if feature:
        lines.append(f"- Feature: {feature}")
    if assignee:
        lines.append(f"- Assignee: {assignee}")
    lines.append(f"- Horizon: {horizon}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    lines.append(overview)
    lines.append("")

    if kind == "story":
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
            lines.append(_render_ac(acceptance_criteria))
            lines.append("")
    else:
        for heading, body in _kind_sections(
            kind, problem, root_cause, location, fix, testing,
            question, time_box, findings, recommendations, acceptance_criteria,
        ):
            lines.append("---")
            lines.append("")
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(body)
            lines.append("")

    if tasks:
        lines.append("---")
        lines.append("")
        lines.append("## Tasks")
        lines.append("")
        for task in tasks:
            lines.append(f"- [ ] {task}")
        lines.append("")

    if open_questions:
        lines.append("---")
        lines.append("")
        lines.append("## Open Questions")
        lines.append("")
        for question_text in open_questions:
            lines.append(f"- {question_text}")
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
        lines.append("_To be defined - what's broken, missing, or painful today?_")
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
        lines.append("_To be filled in - high-level approach, major steps, or implementation sketch._")
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

    # Append a Sources scaffold for research/analysis docs unless the content
    # already provides its own Sources/References section. Research and analysis
    # content is expected to number sources and cite them inline with [N]; at
    # render time each inline [N] becomes a superscript link to the matching
    # numbered source entry (source-N), and the list renders as the sources
    # area. The stub is a no-op prompt for other document kinds.
    if not re.search(r'(?im)^#{2,6}\s+(sources|references)\b', content):
        lines.append("## Sources")
        lines.append("")
        lines.append(
            "<!-- For research/analysis content: number sources (1., 2., ...) and "
            "cite each substantive claim inline with [N] (or grouped [2][5]). At "
            "render time [N] becomes a link to the matching source below. Web: full "
            "URL + descriptor. Codebase: `path:line` + symbol. Remove this section "
            "for non-analytical docs. -->"
        )
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
