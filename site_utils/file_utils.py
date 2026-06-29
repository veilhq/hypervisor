"""
File collection, path helpers, and naming utilities.
"""

import re
from pathlib import Path, PurePosixPath

from .config import HYPERSPACE_ROOT, SKIP_DIRS, SKIP_FILES, CATEGORY_LABELS


def collect_files(root: Path):
    """Walk the hyperspace root and return a sorted list of relative .md paths."""
    files = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(p in SKIP_DIRS for p in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        files.append(rel)
    return files


def html_dir_for(rel_path):
    """_index.md → _index, context/foo.md → context/foo"""
    return str(PurePosixPath(str(rel_path).replace("\\", "/")).with_suffix(""))


def href_for(rel_path):
    return "/" + html_dir_for(rel_path) + "/index.html"


def nice_name(fname):
    specials = {"_index.md": "Index", "_readme.md": "Readme",
                "_meta.md": "Meta", "_conventions.md": "Conventions"}
    if fname in specials:
        return specials[fname]
    return fname.replace(".md", "").replace("-", " ").replace("_", " ").title()


def dir_label(name):
    return CATEGORY_LABELS.get(name, name.replace("-", " ").replace("_", " ").title())


def get_title(md_text, fallback):
    m = re.match(r"^#\s+(.+)$", md_text, re.MULTILINE)
    return m.group(1).strip() if m else fallback


def extract_dates(md_text):
    """Extract Created/Updated/Date metadata from markdown text.

    Returns dict with 'created' and 'updated' keys (datetime strings or None).
    Supported formats:
      Created: 2026-02-17              → 2026-02-17T00:00
      Created: 2026-02-17T14:30       → 2026-02-17T14:30
      - Created: 2026-02-17            → 2026-02-17T00:00
      Date: 2026-02-26                 → 2026-02-26T00:00
      Updated: 2026-02-18T09:15       → 2026-02-18T09:15
      Last updated: 2026-04-20 (...)   → 2026-04-20T00:00
      **Last Updated:** February 13, 2026 → 2026-02-13T00:00
    """
    MONTHS = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    dates = {"created": None, "updated": None}

    # ISO datetime pattern: YYYY-MM-DD or YYYY-MM-DDTHH:MM
    iso_pat = r"(\d{4}-\d{2}-\d{2})(?:T(\d{2}:\d{2}))?"
    # "Month DD, YYYY" pattern
    long_pat = r"([A-Z][a-z]+)\s+(\d{1,2}),?\s+(\d{4})"

    def _normalize(date_str, time_str=None):
        """Normalize to YYYY-MM-DDTHH:MM format."""
        return f"{date_str}T{time_str}" if time_str else f"{date_str}T00:00"

    for line in md_text.splitlines()[:30]:  # only scan top of document
        stripped = line.strip().lstrip("- *")

        # Created / Date → created
        m = re.match(r"(?:Created|Date)\s*:\s*" + iso_pat, stripped, re.IGNORECASE)
        if m:
            dates["created"] = _normalize(m.group(1), m.group(2))
            continue

        # Updated / Last updated → updated (ISO)
        m = re.match(r"(?:Last\s+)?Updated\s*:\s*" + iso_pat, stripped, re.IGNORECASE)
        if m:
            dates["updated"] = _normalize(m.group(1), m.group(2))
            continue

        # Updated with long date: **Last Updated:** February 13, 2026
        m = re.match(r"(?:\*\*)?(?:Last\s+)?Updated(?:\*\*)?\s*:?\s*" + long_pat, stripped, re.IGNORECASE)
        if m:
            month_str = m.group(1).lower()
            if month_str in MONTHS:
                dates["updated"] = _normalize(f"{m.group(3)}-{MONTHS[month_str]}-{int(m.group(2)):02d}")
            continue

    return dates


def sort_date(dates_dict):
    """Return the best datetime string for sorting (prefer updated over created).
    Returns a tuple (datetime_str, label) where label is 'updated' or 'created'.
    Undated docs get ('0000-00-00T00:00', None) so they sort last in descending order.
    """
    if dates_dict["updated"]:
        return (dates_dict["updated"], "updated")
    if dates_dict["created"]:
        return (dates_dict["created"], "created")
    return ("0000-00-00T00:00", None)


def display_date(datetime_str):
    """Format a datetime string for HTML display.

    '2026-04-29T15:30' → '2026-04-29 15:30'
    '2026-04-29T00:00' → '2026-04-29 00:00'
    '0000-00-00T00:00' → ''
    """
    if not datetime_str or datetime_str.startswith("0000"):
        return ""
    date_part, _, time_part = datetime_str.partition("T")
    if time_part:
        return f"{date_part} {time_part}"
    return date_part


def count_docs_under(files, dir_prefix):
    """Count total .md documents under a directory prefix."""
    prefix = PurePosixPath(dir_prefix)
    count = 0
    for rel in files:
        p = PurePosixPath(str(rel).replace("\\", "/"))
        try:
            p.relative_to(prefix)
            count += 1
        except ValueError:
            pass
    return count


def get_dir_snippet(root, dir_prefix, max_len=120):
    """Extract a description snippet for a subdirectory.

    Looks for idea.md first, then story.md, then any .md file in the directory.
    Returns the first body paragraph as plain text, or empty string.
    """
    candidates = ["idea.md", "story.md"]
    md_text = None

    for candidate in candidates:
        path = root / dir_prefix / candidate
        if path.exists():
            md_text = path.read_text(encoding="utf-8")
            break

    if md_text is None:
        # Fall back to first .md file found
        dir_path = root / dir_prefix
        if dir_path.is_dir():
            for f in sorted(dir_path.iterdir()):
                if f.suffix == ".md" and f.is_file():
                    md_text = f.read_text(encoding="utf-8")
                    break

    if not md_text:
        return ""

    # Extract first body paragraph (skip title, metadata, blanks)
    past_meta = False
    body_lines = []
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# ") and not body_lines and not past_meta:
            continue
        if not past_meta:
            if re.match(r'^-?\s*\*{0,2}[A-Za-z][A-Za-z_ ]*\*{0,2}\s*:', stripped):
                continue
            if stripped == "" or stripped == "---":
                continue
            past_meta = True
        if stripped.startswith("#") or stripped.startswith("```") or stripped.startswith("<"):
            break
        if stripped == "" or stripped == "---":
            if body_lines:
                break
            continue
        body_lines.append(stripped)
        if len(" ".join(body_lines)) >= max_len:
            break

    if not body_lines:
        return ""

    snippet = " ".join(body_lines)
    # Strip markdown formatting
    snippet = re.sub(r'\*\*([^*]+)\*\*', r'\1', snippet)
    snippet = re.sub(r'\*([^*]+)\*', r'\1', snippet)
    snippet = re.sub(r'`([^`]+)`', r'\1', snippet)
    snippet = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', snippet)
    if len(snippet) > max_len:
        snippet = snippet[:max_len].rsplit(" ", 1)[0] + "..."
    return snippet


def _extract_tags_from_text(md_text):
    """Extract tags from markdown metadata (Tags:, Technologies:, or Related: lines)."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r'(?:Tags|Technologies|Related)\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            tags = [t.strip().strip('`').strip() for t in raw.split(",")]
            return [t.lower() for t in tags if t]
    return []


def get_dir_tags(root, dir_prefix):
    """Extract tags for a subdirectory from its primary doc.

    Checks idea.md → story.md → first .md, returns lowercase tag list.
    """
    candidates = ["idea.md", "story.md"]
    for candidate in candidates:
        path = root / dir_prefix / candidate
        if path.exists():
            return _extract_tags_from_text(path.read_text(encoding="utf-8"))

    # Fallback to first .md
    dir_path = root / dir_prefix
    if dir_path.is_dir():
        for f in sorted(dir_path.iterdir()):
            if f.suffix == ".md" and f.is_file():
                return _extract_tags_from_text(f.read_text(encoding="utf-8"))
    return []


def _extract_status_from_text(md_text):
    """Extract Status metadata from markdown text header."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r'Status\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_type_from_text(md_text):
    """Extract Type metadata (Personal/Professional) from markdown text header."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r'Type\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def get_dir_status(root, dir_prefix):
    """Extract status for a subdirectory from its primary doc.

    Checks idea.md → story.md → first .md, returns status string or None.
    """
    candidates = ["idea.md", "story.md"]
    for candidate in candidates:
        path = root / dir_prefix / candidate
        if path.exists():
            return _extract_status_from_text(path.read_text(encoding="utf-8"))

    dir_path = root / dir_prefix
    if dir_path.is_dir():
        for f in sorted(dir_path.iterdir()):
            if f.suffix == ".md" and f.is_file():
                return _extract_status_from_text(f.read_text(encoding="utf-8"))
    return None


def get_dir_type(root, dir_prefix):
    """Extract type (Personal/Professional) for a subdirectory from its primary doc.

    Checks idea.md → story.md → first .md, returns type string or None.
    """
    candidates = ["idea.md", "story.md"]
    for candidate in candidates:
        path = root / dir_prefix / candidate
        if path.exists():
            return _extract_type_from_text(path.read_text(encoding="utf-8"))

    dir_path = root / dir_prefix
    if dir_path.is_dir():
        for f in sorted(dir_path.iterdir()):
            if f.suffix == ".md" and f.is_file():
                return _extract_type_from_text(f.read_text(encoding="utf-8"))
    return None


# --- App-group inference from tags ---

_APP_GROUP_RULES = [
    # (group_label, group_key, matching_tags)
    ("Portal CMS", "portal-cms", {"portal-cms"}),
    ("Portal", "portal", {"portal"}),
    ("Hyperspace", "hyperspace", {"hypervisor", "hyperspace"}),
    ("Infrastructure", "infrastructure", {"terraform", "infrastructure", "devops", "azure-devops", "rds"}),
]


def infer_app_group(tags):
    """Infer an app group from a tag list. Returns (label, key) or ('Other', 'other')."""
    tag_set = set(tags) if tags else set()
    for label, key, match_tags in _APP_GROUP_RULES:
        if tag_set & match_tags:
            return (label, key)
    return ("Other", "other")


# --- Computed metadata badges ---

STALE_THRESHOLD_DAYS = 30


def compute_badges(md_text, updated_str=None):
    """Compute metadata badges from markdown content.

    Returns dict with:
      - tasks: (done, total) or None if no checkboxes
      - stale_days: int days since updated, or None if not stale
      - words: int word count of body content

    Args:
        md_text: Full markdown text of the document
        updated_str: Updated date string (YYYY-MM-DDTHH:MM format) or None
    """
    from datetime import datetime

    # --- Task progress ---
    done = md_text.count("- [x]") + md_text.count("- [X]")
    total = done + md_text.count("- [ ]")
    tasks = (done, total) if total > 0 else None

    # --- Staleness ---
    stale_days = None
    if updated_str:
        try:
            updated_dt = datetime.fromisoformat(updated_str)
            delta = datetime.now() - updated_dt
            if delta.days > STALE_THRESHOLD_DAYS:
                stale_days = delta.days
        except (ValueError, TypeError):
            pass

    # --- Word count (body only, skip metadata header) ---
    lines = md_text.splitlines()
    body_started = False
    body_lines = []
    for line in lines:
        if not body_started:
            # Skip until we hit the first --- after metadata
            if line.strip() == "---":
                body_started = True
            continue
        body_lines.append(line)

    body_text = " ".join(body_lines)
    words = len(body_text.split())

    return {"tasks": tasks, "stale_days": stale_days, "words": words}


def format_badge_html(badges):
    """Generate HTML badge spans from compute_badges() output.

    Returns HTML string with badge spans, or empty string if no badges.
    """
    parts = []

    if badges["tasks"]:
        done, total = badges["tasks"]
        if done == total:
            cls = "badge-tasks-done"
        elif done > 0:
            cls = "badge-tasks-partial"
        else:
            cls = "badge-tasks-none"
        parts.append(f'<span class="hv-badge {cls}">{done}/{total} tasks</span>')

    if badges["stale_days"]:
        days = badges["stale_days"]
        cls = "badge-stale-warn" if days < 60 else "badge-stale-crit"
        parts.append(f'<span class="hv-badge {cls}">stale: {days}d</span>')

    if badges["words"]:
        w = badges["words"]
        if w >= 1000:
            label = f"~{w / 1000:.1f}k words"
        else:
            label = f"~{w} words"
        parts.append(f'<span class="hv-badge badge-words">{label}</span>')

    return "".join(parts)
