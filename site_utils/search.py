"""
Search index builder — generates JSON blob embedded in every page for client-side search.
"""

import re

from .config import HYPERSPACE_ROOT
from .file_utils import get_title, nice_name, href_for, extract_dates, sort_date


def _extract_snippet(md_text, max_len=200):
    """Extract a plain-text snippet from markdown, skipping the title and metadata."""
    lines = md_text.splitlines()
    body_lines = []
    past_meta = False
    for line in lines:
        stripped = line.strip()
        # Skip title
        if stripped.startswith("# ") and not body_lines and not past_meta:
            continue
        # Skip metadata lines (- Key: value, Key: value, **Key:** value, frontmatter)
        if not past_meta:
            if re.match(r'^-?\s*\*{0,2}[A-Za-z][A-Za-z_ ]*\*{0,2}\s*:', stripped):
                continue
            if stripped == "" or stripped == "---":
                continue
            past_meta = True
        # Skip headings, blank lines, code fences, HTML, horizontal rules
        if stripped.startswith("#") or stripped.startswith("```") or stripped.startswith("<"):
            continue
        if stripped == "" or stripped == "---":
            continue
        body_lines.append(stripped)
        if len(" ".join(body_lines)) >= max_len:
            break

    snippet = " ".join(body_lines)
    # Strip markdown formatting
    snippet = re.sub(r'\*\*([^*]+)\*\*', r'\1', snippet)  # bold
    snippet = re.sub(r'\*([^*]+)\*', r'\1', snippet)       # italic
    snippet = re.sub(r'`([^`]+)`', r'\1', snippet)         # inline code
    snippet = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', snippet)  # links
    return snippet[:max_len]


def _extract_tags(md_text):
    """Extract tags from markdown metadata (Tags: or - Tags: lines)."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r'(?:Tags|Technologies|Related)\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            # Handle comma-separated, stripping backticks and whitespace
            tags = [t.strip().strip('`').strip() for t in raw.split(",")]
            return [t for t in tags if t]
    return []


def _extract_work_id(md_text):
    """Extract work item ID (e.g., WI-23) from markdown metadata."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r'ID\s*:\s*(WI-\d+)', stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def build_search_index(files):
    """Return a list of {title, path, href, snippet, tags, date} for every doc."""
    entries = []
    for rel in files:
        md_path = HYPERSPACE_ROOT / rel
        md_text = md_path.read_text(encoding="utf-8")
        title = get_title(md_text, nice_name(rel.name))
        snippet = _extract_snippet(md_text)
        tags = _extract_tags(md_text)
        dates = extract_dates(md_text)
        date_str, _ = sort_date(dates)
        entry = {
            "title": title,
            "path": str(rel).replace("\\", "/"),
            "href": href_for(rel),
            "snippet": snippet,
        }
        if tags:
            entry["tags"] = tags
        if date_str != "0000-00-00T00:00":
            entry["date"] = date_str
        # Include work item ID for work items
        work_id = _extract_work_id(md_text)
        if work_id:
            entry["work_id"] = work_id
        entries.append(entry)
    return entries
