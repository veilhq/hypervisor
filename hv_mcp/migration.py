"""
Phase 2 Template Evolution & Migration: migrate_document.

Brings older documents up to current schema by:
- Renaming 'Date:' → 'Created:'
- Adding missing 'Updated:' field
- Converting bold metadata (**Key:**) to dash-prefixed ('- Key:')
- Normalizing date formats to include time (YYYY-MM-DDTHH:MM)
- Reordering metadata to canonical order
- Adding missing 'Created:' from file system timestamp as fallback
- Fixing unknown tags (replace with closest match or remove)
- Trimming excess tags (keep top 4 by usage)

Non-destructive: only touches metadata structure, never modifies content sections.
"""

import os
import re
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import collect_files

from .config import VALIDATION_SKIP_DIRS, VALIDATION_SKIP_FILES, VALIDATION_SKIP_PATHS
from .index import refresh_single


# ---------------------------------------------------------------------------
# Schema Changelog
# ---------------------------------------------------------------------------

SCHEMA_VERSIONS = [
    {
        "date": "2026-01-01",
        "changes": ["Added Project field to work items"],
    },
    {
        "date": "2026-03-15",
        "changes": ["Renamed Date → Created", "Added Updated field"],
    },
    {
        "date": "2026-06-08",
        "changes": ["Added doc_type field to work items and ideas"],
    },
]

# Canonical metadata field order
CANONICAL_ORDER = [
    "Created",
    "Updated",
    "Tags",
    "ID",
    "Type",
    "Status",
    "Project",
    "Severity",
    "Affected",
    "Related",
]


# ---------------------------------------------------------------------------
# Migration Engine
# ---------------------------------------------------------------------------

def _parse_metadata_block(lines: list[str]) -> tuple[int, int, list[dict]]:
    """Parse the metadata block from markdown lines.

    Returns:
        (start_index, end_index, parsed_fields)
        start_index: first metadata line index (after title + optional description)
        end_index: index of '---' separator (or last metadata line + 1)
        parsed_fields: list of {'key': str, 'value': str, 'original': str, 'line': int}
    """
    # Find title
    title_idx = None
    for i, line in enumerate(lines[:10]):
        if line.strip().startswith("# "):
            title_idx = i
            break

    if title_idx is None:
        return 0, 0, []

    # Pattern to detect metadata lines (dash-prefixed or bold or bare key: value)
    meta_patterns = [
        # - Key: value
        re.compile(r'^-\s+([A-Za-z][A-Za-z\s]*?)\s*:\s*(.*)$'),
        # **Key:** value (colon inside bold markers)
        re.compile(r'^\*\*([A-Za-z][A-Za-z\s]*?)\s*:\*\*\s*(.*)$'),
        # **Key**: value (colon outside bold markers)
        re.compile(r'^\*\*([A-Za-z][A-Za-z\s]*?)\*\*\s*:\s*(.*)$'),
        # Key: value (bare, no prefix)
        re.compile(r'^([A-Za-z][A-Za-z\s]*?)\s*:\s*(.+)$'),
    ]

    # Known metadata keys to distinguish from content
    KNOWN_KEYS = {
        "created", "updated", "date", "tags", "type", "status", "project",
        "severity", "affected", "related", "last updated", "doc_type", "id",
        "idea doc", "external story", "pr link", "pr author", "pr created",
    }

    def _is_meta_line(text: str) -> bool:
        """Check if a line matches a known metadata pattern."""
        for pat in meta_patterns:
            m = pat.match(text)
            if m and m.group(1).lower().strip() in KNOWN_KEYS:
                return True
        return False

    # Scan forward from title to find where metadata starts.
    # Skip blank lines and non-metadata text (description) until we hit metadata.
    meta_start = None
    i = title_idx + 1
    while i < min(len(lines), title_idx + 15):
        stripped = lines[i].strip()
        if stripped == "":
            i += 1
            continue
        if _is_meta_line(stripped):
            meta_start = i
            break
        # Non-metadata, non-blank line = description line. Skip and keep looking.
        i += 1

    if meta_start is None:
        return 0, 0, []

    # Now parse all consecutive metadata lines starting at meta_start
    fields: list[dict] = []
    meta_end = None
    i = meta_start

    while i < min(len(lines), title_idx + 30):
        stripped = lines[i].strip()

        # End markers
        if stripped == "---":
            meta_end = i
            break
        if stripped.startswith("## "):
            meta_end = i
            break

        # Empty line — check if more metadata follows
        if stripped == "":
            found_more = False
            for j in range(i + 1, min(len(lines), i + 3)):
                next_stripped = lines[j].strip()
                if next_stripped == "---" or next_stripped.startswith("## "):
                    break
                if next_stripped == "":
                    continue
                if _is_meta_line(next_stripped):
                    found_more = True
                    break
                else:
                    break
            if not found_more:
                meta_end = i
                break
            i += 1
            continue

        # Try to parse as metadata
        parsed = False
        for pat in meta_patterns:
            m = pat.match(stripped)
            if m:
                key = m.group(1).strip()
                value = m.group(2).strip()
                if key.lower() in KNOWN_KEYS:
                    fields.append({
                        "key": key,
                        "value": value,
                        "original": lines[i],
                        "line": i,
                    })
                    parsed = True
                    break
        if not parsed:
            # Non-metadata line reached — end of metadata
            meta_end = i
            break

        i += 1

    if meta_end is None:
        meta_end = i

    return meta_start, meta_end, fields


def _normalize_key(key: str) -> str:
    """Normalize a metadata key to canonical casing."""
    key_map = {
        "date": "Created",
        "created": "Created",
        "updated": "Updated",
        "last updated": "Updated",
        "tags": "Tags",
        "id": "ID",
        "type": "Type",
        "doc_type": "Type",
        "status": "Status",
        "project": "Project",
        "severity": "Severity",
        "affected": "Affected",
        "related": "Related",
        "idea doc": "Idea Doc",
        "external story": "External Story",
        "pr link": "PR Link",
        "pr author": "PR Author",
        "pr created": "PR Created",
    }
    return key_map.get(key.lower(), key.title())


def _normalize_date_value(value: str) -> str:
    """Normalize a date value to YYYY-MM-DDTHH:MM format."""
    # Already has time component
    if re.match(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}', value):
        return value

    # Date only: YYYY-MM-DD → append T00:00
    m = re.match(r'(\d{4}-\d{2}-\d{2})', value)
    if m:
        return f"{m.group(1)}T00:00"

    # Leave non-standard formats untouched
    return value


def _get_file_created_time(full_path: Path) -> str:
    """Get file creation time as YYYY-MM-DDTHH:MM."""
    try:
        stat = full_path.stat()
        # Use the earlier of ctime and mtime
        ts = min(stat.st_ctime, stat.st_mtime)
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%dT%H:%M")
    except OSError:
        return datetime.now().strftime("%Y-%m-%dT%H:%M")


def _get_tag_usage_counts() -> dict[str, int]:
    """Get tag usage counts across all indexed documents.

    Returns a dict mapping tag name to number of documents using it.
    """
    try:
        from .index import _index, _index_lock
        counts: dict[str, int] = {}
        with _index_lock:
            for entry in _index:
                for tag in entry.get("tags", []):
                    counts[tag] = counts.get(tag, 0) + 1
        return counts
    except Exception:
        return {}


def migrate_single(rel_path: str, dry_run: bool = True) -> dict:
    """Migrate a single document to current schema conventions.

    Applies fixes:
    - 'Date:' → 'Created:'
    - Bold metadata → dash-prefixed
    - Missing 'Updated:' → add with same value as Created
    - Missing 'Created:' → add from file timestamp
    - Date-only values → include time (T00:00)
    - Reorder metadata to canonical order

    Args:
        rel_path: Relative path to the document.
        dry_run: If True, returns what would change without writing. Default True.

    Returns:
        Dict with 'path', 'changes' list, 'migrated' bool, and 'diff' (old→new lines).
    """
    full_path = HYPERSPACE_ROOT / rel_path.replace("/", os.sep)
    if not full_path.exists():
        return {"error": f"File not found: {rel_path}"}

    try:
        content = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return {"error": f"Cannot read file: {e}"}

    lines = content.splitlines()
    meta_start, meta_end, fields = _parse_metadata_block(lines)

    if not fields:
        return {
            "path": rel_path,
            "migrated": False,
            "changes": [],
            "reason": "No metadata block found to migrate.",
        }

    changes: list[str] = []
    new_fields: dict[str, str] = {}

    # Process each field
    for field in fields:
        key = field["key"]
        value = field["value"]
        norm_key = _normalize_key(key)

        # Track key renames
        if key.lower() == "date":
            changes.append(f"Renamed 'Date:' → 'Created:'")
            norm_key = "Created"

        if key.lower() == "last updated":
            changes.append(f"Renamed 'Last Updated:' → 'Updated:'")
            norm_key = "Updated"

        # Bold format detection (already handled by parser but note the change)
        if "**" in field["original"]:
            changes.append(f"Converted bold metadata '{key}' to dash-prefixed format")

        # Normalize date values
        if norm_key in ("Created", "Updated"):
            new_value = _normalize_date_value(value)
            if new_value != value:
                changes.append(f"Normalized {norm_key} date: '{value}' → '{new_value}'")
                value = new_value

        new_fields[norm_key] = value

    # Add missing Created from file timestamp
    if "Created" not in new_fields:
        created_ts = _get_file_created_time(full_path)
        new_fields["Created"] = created_ts
        changes.append(f"Added missing Created: {created_ts} (from file timestamp)")

    # Add missing Updated (default to same as Created)
    if "Updated" not in new_fields:
        new_fields["Updated"] = new_fields.get("Created", datetime.now().strftime("%Y-%m-%dT%H:%M"))
        changes.append(f"Added missing Updated: {new_fields['Updated']}")

    # --- Tag fixes ---
    if "Tags" in new_fields and new_fields["Tags"]:
        from .config import load_tags
        registry = load_tags()
        tag_names = set(registry.keys())

        raw_tags = [t.strip().lower() for t in new_fields["Tags"].split(",")]
        raw_tags = [t for t in raw_tags if t]
        fixed_tags = []
        tags_changed = False

        # Fix unknown tags: replace with closest match or remove
        for tag in raw_tags:
            if tag in tag_names:
                fixed_tags.append(tag)
            else:
                matches = get_close_matches(tag, list(tag_names), n=1, cutoff=0.6)
                if matches:
                    changes.append(f"Replaced unknown tag '{tag}' → '{matches[0]}'")
                    fixed_tags.append(matches[0])
                    tags_changed = True
                else:
                    changes.append(f"Removed unknown tag '{tag}' (no close match)")
                    tags_changed = True

        # Trim excess tags: keep top 4 by registry usage count
        if len(fixed_tags) > 4:
            # Get usage counts from the index
            tag_usage = _get_tag_usage_counts()
            # Sort by usage (descending), keep top 4
            scored = sorted(fixed_tags, key=lambda t: tag_usage.get(t, 0), reverse=True)
            dropped = scored[4:]
            fixed_tags = scored[:4]
            changes.append(f"Trimmed tags to 4 (dropped least-used: {', '.join(dropped)})")
            tags_changed = True

        if tags_changed:
            new_fields["Tags"] = ", ".join(fixed_tags)

    # Check if canonical reordering is needed
    current_keys = [_normalize_key(f["key"]) for f in fields]
    desired_order = [k for k in CANONICAL_ORDER if k in new_fields]
    # Include any keys not in CANONICAL_ORDER at the end
    extra_keys = [k for k in new_fields if k not in CANONICAL_ORDER]
    desired_order.extend(extra_keys)

    if current_keys != desired_order:
        # Only note reordering if something actually moved (not just added fields)
        existing_keys = [k for k in desired_order if k in set(current_keys)]
        original_existing = [k for k in current_keys if k in set(existing_keys)]
        if existing_keys != original_existing:
            changes.append("Reordered metadata to canonical order")

    # If no changes, return early
    if not changes:
        return {
            "path": rel_path,
            "migrated": False,
            "changes": [],
            "reason": "Document already conforms to current schema.",
        }

    # Build new metadata block
    new_meta_lines = []
    for key in desired_order:
        value = new_fields[key]
        new_meta_lines.append(f"- {key}: {value}")

    # Build the new file content
    # Lines before metadata
    before = lines[:meta_start]
    # Lines after metadata (including --- separator and content)
    after = lines[meta_end:]

    new_lines = before + new_meta_lines + after

    # Compute diff for display
    old_meta = lines[meta_start:meta_end]
    diff = {
        "old_metadata": old_meta,
        "new_metadata": new_meta_lines,
    }

    result = {
        "path": rel_path,
        "migrated": not dry_run,
        "changes": changes,
        "diff": diff,
        "dry_run": dry_run,
    }

    # Write if not dry run
    if not dry_run:
        new_content = "\n".join(new_lines)
        # Preserve trailing newline if original had one
        if content.endswith("\n"):
            new_content += "\n"
        full_path.write_text(new_content, encoding="utf-8")
        # Refresh index for this file
        refresh_single(rel_path)
        result["written"] = True

    return result


def migrate_document(path: str = "all", dry_run: bool = True) -> dict:
    """Migrate documents to current schema.

    Args:
        path: Relative path to a single document, or "all" for batch migration.
        dry_run: If True, preview changes without writing. Default True.

    Returns:
        For single: migration result with changes and diff.
        For batch: summary with counts and per-file results.
    """
    if path and path != "all":
        return migrate_single(path, dry_run=dry_run)

    # Batch mode
    files = collect_files(HYPERSPACE_ROOT)
    results: list[dict] = []
    needs_migration = 0
    total_changes = 0
    change_types: dict[str, int] = {}

    for rel in files:
        rel_str = str(rel).replace("\\", "/")
        parts = rel_str.split("/")

        # Skip excluded paths
        if parts[0] in VALIDATION_SKIP_DIRS:
            continue
        if rel.name in VALIDATION_SKIP_FILES:
            continue
        if rel_str in VALIDATION_SKIP_PATHS:
            continue

        result = migrate_single(rel_str, dry_run=dry_run)
        if "error" in result:
            continue

        if result.get("changes"):
            needs_migration += 1
            total_changes += len(result["changes"])
            for change in result["changes"]:
                # Extract change type (first word or key phrase)
                change_key = _categorize_change(change)
                change_types[change_key] = change_types.get(change_key, 0) + 1
            results.append(result)

    # Sort change types by frequency
    sorted_types = sorted(change_types.items(), key=lambda x: x[1], reverse=True)

    return {
        "dry_run": dry_run,
        "total_scanned": len(files),
        "needs_migration": needs_migration,
        "total_changes": total_changes,
        "change_breakdown": [
            {"type": t, "count": c} for t, c in sorted_types
        ],
        "results": results if dry_run else [
            {"path": r["path"], "changes": r["changes"]} for r in results
        ],
        "summary": (
            f"{needs_migration} docs need migration. "
            + ", ".join(f"{c} {t}" for t, c in sorted_types[:5])
        ) if needs_migration > 0 else "All documents conform to current schema.",
    }


def _categorize_change(change: str) -> str:
    """Categorize a change description into a summary type."""
    lower = change.lower()
    if "renamed" in lower and "created" in lower:
        return "Date→Created rename"
    if "renamed" in lower and "updated" in lower:
        return "Last Updated→Updated rename"
    if "bold" in lower:
        return "bold→dash-prefixed format"
    if "added missing created" in lower:
        return "missing Created added"
    if "added missing updated" in lower:
        return "missing Updated added"
    if "normalized" in lower and "date" in lower:
        return "date format normalized"
    if "reorder" in lower:
        return "metadata reordered"
    if "replaced unknown tag" in lower:
        return "unknown tag replaced"
    if "removed unknown tag" in lower:
        return "unknown tag removed"
    if "trimmed tags" in lower:
        return "excess tags trimmed"
    return "other"


def get_schema_changelog() -> dict:
    """Return the schema changelog and current version info.

    Returns:
        Schema versions with dates and changes, plus current conventions summary.
    """
    return {
        "versions": SCHEMA_VERSIONS,
        "current_conventions": {
            "date_format": "YYYY-MM-DDTHH:MM",
            "metadata_format": "- Key: value (dash-prefixed)",
            "required_fields": ["Created", "Updated", "Tags"],
            "optional_fields": ["Type", "Status", "Project", "Severity", "Affected", "Related"],
            "canonical_order": CANONICAL_ORDER,
        },
        "total_versions": len(SCHEMA_VERSIONS),
        "latest_change_date": SCHEMA_VERSIONS[-1]["date"] if SCHEMA_VERSIONS else None,
    }
