"""
_index.md regeneration logic — generates the navigable index from in-memory state.
"""

from datetime import datetime

from .config import INDEX_FILE
from .index import get_index_lock


def regenerate_index_file():
    """Regenerate _index.md entirely from the in-memory index."""
    # Import here to avoid circular import at module level
    from .index import _index as index_list

    with get_index_lock():
        entries = list(index_list)

    now = datetime.now().strftime("%Y-%m-%d")

    # Group entries by section
    work_todo = [e for e in entries if e["directory"] == "work/to-do"]
    work_done = [e for e in entries if e["directory"] == "work/done"]
    ideas = [e for e in entries if e["type"] == "idea" and not e["path"].startswith("ideas/_")]
    ideas_conventions = [e for e in entries if e["path"] == "ideas/_conventions.md"]
    context_entries = [e for e in entries if e["type"] == "context"]
    patterns_entries = [e for e in entries if e["type"] == "pattern"]
    reference_entries = [e for e in entries if e["type"] == "reference"]
    research_entries = [e for e in entries if e["type"] == "research"]
    template_entries = [e for e in entries if e["type"] == "template"]
    analysis_entries = [e for e in entries if e["type"] == "analysis"]
    external_entries = [e for e in entries if e["type"] == "external"]

    def _link(e):
        desc = f" - {e['description']}" if e.get("description") else ""
        return f"- [{e['title']}]({e['path']}){desc}"

    def _work_link(e):
        """Link formatter for work items — includes WI-N ID prefix."""
        wi_id = e.get("work_id")
        prefix = f"**{wi_id}** — " if wi_id else ""
        desc = f" - {e['description']}" if e.get("description") else ""
        return f"- {prefix}[{e['title']}]({e['path']}){desc}"

    def _sorted(entries):
        return sorted(entries, key=lambda e: e["title"].lower())

    def _group_by_project(items):
        groups = {}
        for item in items:
            proj = item.get("project") or "Uncategorized"
            groups.setdefault(proj, []).append(item)
        return groups

    lines = []
    lines.append("# Hyperspace Knowledge Index")
    lines.append("")
    lines.append(f"Last updated: {now}")
    lines.append("")
    lines.append("This index provides a navigable map of all content in hyperspace. Use it to discover related documents and understand what knowledge exists across the workspace.")
    lines.append("")
    lines.append("## Quick Navigation")
    lines.append("")
    lines.append("- [Work](#work) - Actionable work items with design, AC, tasks, and PR notes")
    lines.append("- [Ideas](#ideas) - Lightweight concept capture for someday/maybe items")
    lines.append("- [Context](#context) - Project overviews, architecture, and diagrams")
    lines.append("- [Patterns](#patterns) - Reusable solutions")
    lines.append("- [Reference](#reference) - Cheatsheets and quick-lookup tables")
    lines.append("- [Research](#research) - Technical investigations")
    lines.append("- [Templates](#templates) - Boilerplate starting points")
    lines.append("- [Analysis](#analysis) - Progress analysis, PR reviews, and milestone assessments")
    lines.append("- [External](#external) - Documents brought in from outside hyperspace")
    lines.append("")
    lines.append("---")
    lines.append("")

    # --- Work section ---
    lines.append("## Work")
    lines.append("")
    lines.append("Actionable work items. Each file is a unified document containing design, acceptance criteria, tasks, and PR notes. Pending items in `to-do/`, completed in `done/`.")
    lines.append("")

    work_conventions = [e for e in entries if e["path"] == "work/_conventions.md"]
    if work_conventions:
        lines.append("- [Conventions](work/_conventions.md)")
        lines.append("")

    todo_groups = _group_by_project(work_todo)
    for project_name in sorted(todo_groups.keys()):
        lines.append(f"### To-Do: {project_name}")
        lines.append("")
        for item in _sorted(todo_groups[project_name]):
            lines.append(_work_link(item))
        lines.append("")

    if work_done:
        lines.append("### Done")
        lines.append("")
        for item in _sorted(work_done):
            lines.append(_work_link(item))
        lines.append("")

    lines.append("---")
    lines.append("")

    # --- Ideas section ---
    lines.append("## Ideas")
    lines.append("")
    lines.append("Lightweight concept capture. Someday/maybe items that may become work items when ready.")
    lines.append("")
    if ideas_conventions:
        lines.append("- [Conventions](ideas/_conventions.md)")
        lines.append("")

    cms_ideas = [e for e in ideas if any("cms" in t for t in e.get("tags", []))]
    portal_ideas = [e for e in ideas if "portal" in e.get("tags", []) and e not in cms_ideas]
    terraform_ideas = [e for e in ideas if any(t in ["terraform", "infrastructure"] for t in e.get("tags", []))]
    hypervisor_ideas = [e for e in ideas if any(t in ["hypervisor", "hyperspace"] for t in e.get("tags", []))]
    personal_ideas = [e for e in ideas if "personal" in (e.get("doc_type") or "").lower()]

    grouped = set(id(e) for group in [cms_ideas, portal_ideas, terraform_ideas, hypervisor_ideas, personal_ideas] for e in group)
    other_ideas = [e for e in ideas if id(e) not in grouped]

    if cms_ideas:
        lines.append("### CMS Ideas")
        lines.append("")
        for item in _sorted(cms_ideas):
            lines.append(_link(item))
        lines.append("")

    if portal_ideas:
        lines.append("### Portal Ideas")
        lines.append("")
        for item in _sorted(portal_ideas):
            lines.append(_link(item))
        lines.append("")

    if terraform_ideas:
        lines.append("### Terraform Ideas")
        lines.append("")
        for item in _sorted(terraform_ideas):
            lines.append(_link(item))
        lines.append("")

    if hypervisor_ideas:
        lines.append("### Hypervisor & Hyperspace Ideas")
        lines.append("")
        for item in _sorted(hypervisor_ideas):
            lines.append(_link(item))
        lines.append("")

    if personal_ideas:
        lines.append("### Personal Project Ideas")
        lines.append("")
        for item in _sorted(personal_ideas):
            lines.append(_link(item))
        lines.append("")

    if other_ideas:
        lines.append("### Other Ideas")
        lines.append("")
        for item in _sorted(other_ideas):
            lines.append(_link(item))
        lines.append("")

    lines.append("---")
    lines.append("")

    # --- Simple sections ---
    def _simple_section(title, description, entries_list):
        lines.append(f"## {title}")
        lines.append("")
        if description:
            lines.append(description)
            lines.append("")
        for item in _sorted(entries_list):
            lines.append(_link(item))
        lines.append("")
        lines.append("---")
        lines.append("")

    _simple_section("Context", "High-level project documentation, architectural overviews, and visual diagrams.", context_entries)
    _simple_section("Patterns", "Reusable architectural patterns and proven solutions organized by topic.", patterns_entries)
    _simple_section("Reference", "Quick-lookup cheatsheets, syntax tables, and code snippets.", reference_entries)
    _simple_section("Research", "Technical investigations, comparisons, and design explorations.", research_entries)
    _simple_section("Templates", "Boilerplate files and starting points for common tasks.", template_entries)
    _simple_section("Analysis", "Progress analysis, PR reviews, milestone assessments, and project health.", analysis_entries)
    _simple_section("External", "Documents brought in from outside hyperspace.", external_entries)

    # --- Statistics ---
    lines.append("## Statistics")
    lines.append("")
    lines.append("| Section | Count |")
    lines.append("|---------|-------|")
    lines.append(f"| Work (to-do) | {len(work_todo)} |")
    lines.append(f"| Work (done) | {len(work_done)} |")
    lines.append(f"| Ideas | {len(ideas)} |")
    lines.append(f"| Context | {len(context_entries)} |")
    lines.append(f"| Patterns | {len(patterns_entries)} |")
    lines.append(f"| Reference | {len(reference_entries)} |")
    lines.append(f"| Research | {len(research_entries)} |")
    lines.append(f"| Templates | {len(template_entries)} |")
    lines.append(f"| Analysis | {len(analysis_entries)} |")
    lines.append(f"| External | {len(external_entries)} |")
    total = (len(work_todo) + len(work_done) + len(ideas) + len(context_entries) +
             len(patterns_entries) + len(reference_entries) + len(research_entries) +
             len(template_entries) + len(analysis_entries) + len(external_entries))
    lines.append(f"| **Total** | **{total}** |")
    lines.append("")

    INDEX_FILE.write_text("\n".join(lines), encoding="utf-8")
