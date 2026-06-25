"""
Document validation — single file and batch modes.
"""

import os
import re
from difflib import get_close_matches

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import collect_files

from .config import (
    VALIDATION_SKIP_DIRS, VALIDATION_SKIP_FILES, VALIDATION_SKIP_PATHS,
    load_tags, load_projects,
)

# Required H2 sections per document type.
# If a section is listed here, the file must contain it.
REQUIRED_SECTIONS = {
    "idea": ["problem", "concept", "rough solution plan", "related"],
    "work-item": ["overview", "tasks", "implementation notes"],
    "adr": ["context", "decision", "rationale", "related"],
    "bugfix": ["problem description", "root cause", "the fix"],
}

# Acceptable aliases for required sections (legacy naming conventions).
# Key is the canonical name, value is a set of alternatives that satisfy the requirement.
SECTION_ALIASES = {
    "concept": {"purpose", "overview", "idea", "vision", "proposal",
                "proposed approach", "background"},
}


def _detect_doc_type(rel_path: str) -> str | None:
    """Infer document type from its path within hyperspace."""
    parts = rel_path.replace("\\", "/").split("/")
    if not parts:
        return None
    top = parts[0]
    if top == "ideas":
        return "idea"
    elif top == "work":
        return "work-item"
    # ADRs are typically named adr-*.md in research/
    if any(p.startswith("adr-") for p in parts):
        return "adr"
    # Bugfixes live in research/bugfixes/
    if "bugfixes" in parts:
        return "bugfix"
    return None


def _extract_h2_sections(md_text: str) -> list[str]:
    """Extract normalized H2 heading text from markdown content."""
    sections = []
    for line in md_text.splitlines():
        m = re.match(r'^##\s+(.+)', line.strip())
        if m:
            sections.append(m.group(1).strip().lower())
    return sections


def _find_empty_sections(lines: list[str]) -> list[tuple[str, int]]:
    """Find H2 sections that have no meaningful content beneath them.

    Returns a list of (section_name, line_number) tuples for empty sections.
    A section is considered empty if there is no non-blank, non-heading content
    between its H2 heading and the next H2/H1 heading (or end of file).
    """
    # Sections that are commonly left empty intentionally (populated later).
    EXEMPT_SECTIONS = {"related"}

    empty = []
    i = 0
    while i < len(lines):
        m = re.match(r'^##\s+(.+)', lines[i].strip())
        if m:
            section_name = m.group(1).strip()
            section_line = i + 1  # 1-indexed
            # Skip exempt sections
            if section_name.lower() in EXEMPT_SECTIONS:
                i += 1
                continue
            # Scan forward for content
            j = i + 1
            has_content = False
            while j < len(lines):
                stripped = lines[j].strip()
                # Stop at next H1 or H2
                if re.match(r'^#{1,2}\s+', stripped):
                    break
                # Horizontal rules and blank lines don't count as content
                if stripped and stripped != "---":
                    has_content = True
                    break
                j += 1
            if not has_content:
                empty.append((section_name, section_line))
        i += 1
    return empty


def validate_single(rel_path: str) -> dict:
    """Validate a single document against conventions."""
    full_path = HYPERSPACE_ROOT / rel_path.replace("/", os.sep)
    if not full_path.exists():
        return {"error": f"File not found: {rel_path}"}

    md_text = full_path.read_text(encoding="utf-8")
    violations = []
    registry = load_tags()
    projects = load_projects()

    lines_list = md_text.splitlines()

    # Check: has title (H1)
    has_title = any(line.strip().startswith("# ") for line in lines_list[:5])
    if not has_title:
        violations.append({
            "rule": "structure-missing-title",
            "message": "Document is missing an H1 title.",
            "line": 1,
        })

    # Check metadata
    has_created = False
    has_updated = False
    tags_found = []
    past_title = False

    for i, line in enumerate(lines_list[:30], 1):
        stripped = line.strip()

        if stripped.startswith("# ") and not past_title:
            past_title = True
            continue

        if stripped == "---" and past_title:
            break

        stripped = stripped.lstrip("- ")

        # Created
        m = re.match(r'Created\s*:\s*(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?)', stripped, re.IGNORECASE)
        if m:
            has_created = True
            date_val = m.group(1)
            if "T" not in date_val:
                violations.append({
                    "rule": "metadata-date-format",
                    "message": f"Created date should include time (YYYY-MM-DDTHH:MM). Got: '{date_val}'",
                    "line": i,
                })

        # Check for "Date:" instead of "Created:"
        if re.match(r'Date\s*:', stripped, re.IGNORECASE) and not re.match(r'Updated', stripped, re.IGNORECASE):
            violations.append({
                "rule": "metadata-key-format",
                "message": "Uses 'Date:' instead of 'Created:'. Convention requires 'Created:'.",
                "line": i,
            })

        # Updated
        m = re.match(r'(?:Last\s+)?Updated\s*:\s*(\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?)', stripped, re.IGNORECASE)
        if m:
            has_updated = True
            date_val = m.group(1)
            if "T" not in date_val:
                violations.append({
                    "rule": "metadata-date-format",
                    "message": f"Updated date should include time (YYYY-MM-DDTHH:MM). Got: '{date_val}'",
                    "line": i,
                })

        # Tags
        m = re.match(r'Tags\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m:
            raw_tags = [t.strip().lower() for t in m.group(1).split(",")]
            tags_found = [t for t in raw_tags if t]

        # Project validation
        m = re.match(r'Project\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m and projects:
            proj = m.group(1).strip()
            if proj not in projects:
                violations.append({
                    "rule": "project-unknown",
                    "message": f"Project '{proj}' is not in the registry. Valid: {projects}",
                    "line": i,
                })

        # Bold metadata check
        if re.match(r'\*\*[A-Za-z]+\*\*\s*:', stripped):
            violations.append({
                "rule": "metadata-format-bold",
                "message": "Uses bold metadata format (**Key:**). Convention requires dash-prefixed: '- Key: value'.",
                "line": i,
            })

    if not has_created:
        violations.append({
            "rule": "metadata-missing-created",
            "message": "Missing 'Created:' metadata field.",
            "line": None,
        })

    if not has_updated:
        violations.append({
            "rule": "metadata-missing-updated",
            "message": "Missing 'Updated:' metadata field.",
            "line": None,
        })

    # Validate tags against registry
    if tags_found and registry:
        tag_names = set(registry.keys())
        for tag in tags_found:
            if tag not in tag_names:
                suggestions = get_close_matches(tag, list(tag_names), n=3, cutoff=0.6)
                sug_str = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
                violations.append({
                    "rule": "tag-unknown",
                    "message": f"Tag '{tag}' is not in the canonical registry.{sug_str}",
                    "line": None,
                })

    # Tag count warning
    if tags_found:
        if len(tags_found) < 2:
            violations.append({
                "rule": "tag-count-low",
                "message": f"Only {len(tags_found)} tag(s). Convention recommends 2-4 tags.",
                "line": None,
            })
        elif len(tags_found) > 4:
            violations.append({
                "rule": "tag-count-high",
                "message": f"{len(tags_found)} tags. Convention recommends 2-4 tags.",
                "line": None,
            })

    # Structure check — verify required H2 sections for document type
    doc_type = _detect_doc_type(rel_path)
    if doc_type and doc_type in REQUIRED_SECTIONS:
        h2_sections = _extract_h2_sections(md_text)
        for required in REQUIRED_SECTIONS[doc_type]:
            # Check canonical name or any alias
            aliases = SECTION_ALIASES.get(required, set())
            if required not in h2_sections and not aliases.intersection(h2_sections):
                violations.append({
                    "rule": "structure-missing-section",
                    "message": f"Missing required section '## {required.title()}' for {doc_type} documents.",
                    "line": None,
                })

    # Check for empty H2 sections (heading present but no content beneath it)
    empty_sections = _find_empty_sections(lines_list)
    for section_name, line_num in empty_sections:
        violations.append({
            "rule": "structure-empty-section",
            "message": f"Section '## {section_name}' is empty (no content beneath heading).",
            "line": line_num,
        })

    return {
        "path": rel_path,
        "valid": len(violations) == 0,
        "violations": violations,
    }


def validate_all() -> dict:
    """Validate all hyperspace documents and return a summary."""
    files = collect_files(HYPERSPACE_ROOT)
    total = 0
    all_violations = []
    valid_count = 0
    skipped = 0
    by_directory: dict[str, dict] = {}

    for rel in files:
        rel_str = str(rel).replace("\\", "/")
        parts = rel_str.split("/")

        if parts[0] in VALIDATION_SKIP_DIRS:
            skipped += 1
            continue
        if rel.name in VALIDATION_SKIP_FILES:
            skipped += 1
            continue
        if rel_str in VALIDATION_SKIP_PATHS:
            skipped += 1
            continue

        total += 1
        result = validate_single(rel_str)
        if "error" in result:
            continue

        dir_key = parts[0] if len(parts) > 1 else "root"
        if dir_key not in by_directory:
            by_directory[dir_key] = {"total": 0, "violations": 0}
        by_directory[dir_key]["total"] += 1

        if result["valid"]:
            valid_count += 1
        else:
            by_directory[dir_key]["violations"] += 1
            for v in result["violations"]:
                v["file"] = rel_str
                all_violations.append(v)

    # Top issues by frequency
    rule_counts: dict[str, int] = {}
    rule_messages: dict[str, str] = {}
    for v in all_violations:
        rule = v["rule"]
        rule_counts[rule] = rule_counts.get(rule, 0) + 1
        rule_messages[rule] = v["message"]

    top_issues = sorted(
        [{"rule": r, "count": c, "message": rule_messages[r]} for r, c in rule_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    # Group violations by file for detailed reporting
    violations_by_file = {}
    for v in all_violations:
        fpath = v["file"]
        if fpath not in violations_by_file:
            violations_by_file[fpath] = []
        violations_by_file[fpath].append({
            "rule": v["rule"],
            "message": v["message"],
            "line": v.get("line"),
        })

    return {
        "total_documents": total,
        "valid": valid_count,
        "violations": total - valid_count,
        "skipped": skipped,
        "top_issues": top_issues,
        "by_directory": by_directory,
        "violations_by_file": violations_by_file,
    }
