"""
Work item claim verification — sweeps a work item's Implementation Notes,
Tasks, and Acceptance Criteria for file/line references and checks them
against the actual codebase.

This is heuristic pattern-matching against source, not proof. It surfaces
candidate gaps and open questions for human review — it never auto-completes
a task or deletes an acceptance criterion. All findings are advisory.

Repo roots are resolved directly from the workspace root (the directory
containing .hyperspace/), since work items already write paths in
"{repo-name}/path/to/file.ext" form (e.g. "cyber-portal/api/apps/views.py").
No project → repo-path config mapping is required — the repo name is already
embedded in the claim text itself.
"""

import re
from datetime import datetime
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT

from .config import HYPERVISOR_DIR
from .helpers import trigger_site_build
from .index import refresh_single
from .index_file import regenerate_index_file


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Workspace root — sibling repos (cyber-portal, portal-cms, etc.) live here,
# one level up from .hyperspace/.
WORKSPACE_ROOT = HYPERSPACE_ROOT.parent

# Safety cap — max number of distinct file claims read per run, to avoid
# a runaway scan on a work item with an unusually large Implementation Notes
# section. Claims beyond the cap are reported as "skipped", not silently dropped.
MAX_FILE_READS = 50

# When an exact claimed line doesn't match, search this many lines above/below
# before concluding the reference truly no longer holds. Files get edited and
# lines drift — this distinguishes "moved" from "gone".
LINE_DRIFT_WINDOW = 20

# A claimed line match requires at least this many "identifier-like" tokens
# (function names, decorator names, quoted strings) from the claim text to
# appear in the searched window. Pure prose claims with no extractable
# identifiers are not verifiable and are skipped rather than guessed at.
MIN_MATCH_TOKENS = 1

# Regex: backtick-wrapped path, optionally followed by a line/line-range ref.
# Matches the real variants seen in existing work items:
#   `cyber-portal/api/apps/views.py` lines ~390-396
#   `portal-cms/app/components/layout/DefaultNavbar.js` line ~145
#   `cyber-portal/api/permissions/decorators.py` (~line 105)
#
# Requires at least one "/" inside the backticks — this is what distinguishes
# a real repo-relative path from a bare symbol/filename mention like
# `FAQViewSet.list` or `DefaultNavbar.js`, which show up frequently in prose
# alongside the real path and would otherwise be misidentified as claims.
_PATH_LINE_RE = re.compile(
    r'`([\w\-]+(?:/[\w\-.]+)+\.\w+)`'          # `repo/path/to/file.ext` (>=1 slash required)
    r'(?:\s*\(?~?\s*lines?\s*~?(\d+)(?:\s*-\s*(\d+))?\)?)?',  # optional line/range
    re.IGNORECASE,
)

# Regex: markdown table row containing a backtick-wrapped path in one cell
# and a "line N" / "lines N-M" / bare "N" or "N, M" reference in another cell.
# Matches the real variants seen in Design-section location tables:
#   | `Historic_Session_Log` | `api/historic_logs/models.py` line 16 | `user_id` (CharField) |
#   | `Course_Log` / `Content_Log` | `api/cms_logs/models.py` lines 63, 90 | `created_by_user_id` |
#
# Unlike _PATH_LINE_RE, the path and the line reference are not required to
# be adjacent — they can sit in the same table row (line) separated by other
# cell content (`|`). This regex scans the whole row for a path cell, then
# looks for a line reference anywhere later in the same row. A comma-
# separated list ("lines 63, 90") produces one claim per number; a dash
# range ("lines 16-20") produces a single start-end claim. See
# _extract_table_claims for the full splitting logic.
_TABLE_ROW_RE = re.compile(r'^\s*\|.*\|\s*$')
_TABLE_PATH_CELL_RE = re.compile(r'`([\w\-]+(?:/[\w\-.]+)+\.\w+)`')
_TABLE_LINE_REF_RE = re.compile(
    r'\blines?\s*~?(\d+)(?:\s*[-,]\s*(\d+))*',
    re.IGNORECASE,
)

# Rough identifier extractor for token-overlap verification: function/class
# names, decorator names, and short quoted strings mentioned near a claim.
_IDENTIFIER_RE = re.compile(r'@?\b[A-Za-z_][A-Za-z0-9_]{3,}\b')

# Common English words to exclude from identifier matching (avoids false
# "match" on words like "this", "that", "line").
_STOPWORDS = {
    "this", "that", "with", "from", "line", "lines", "file", "path", "does",
    "not", "the", "and", "for", "was", "are", "has", "have", "been", "note",
    "notes", "when", "what", "which", "into", "onto", "also", "only", "over",
}


# ---------------------------------------------------------------------------
# Work item resolution (mirrors the lookup pattern in intelligence.py)
# ---------------------------------------------------------------------------

def _resolve_work_item(slug: str) -> tuple[str | None, str | None]:
    """Resolve a slug or WI-N id to a relative path. Returns (rel_path, error)."""
    from .config import normalize_work_id
    from .index import get_index_lock, _index

    norm_id = normalize_work_id(slug)
    if norm_id:
        with get_index_lock():
            entries = list(_index)
        match = next(
            (e for e in entries if e.get("work_id") and e["work_id"].upper() == norm_id.upper()),
            None,
        )
        if match:
            return match["path"], None

        # Fallback: scan disk directly (handles empty index / startup race)
        for subdir in ("work/to-do", "work/done"):
            dir_path = HYPERSPACE_ROOT / subdir.replace("/", "\\")
            if not dir_path.is_dir():
                continue
            for md_file in dir_path.glob("*.md"):
                try:
                    text = md_file.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError):
                    continue
                for line in text.splitlines()[:30]:
                    stripped = line.strip().lstrip("- ")
                    m = re.match(r'ID\s*:\s*(WI-\d+)', stripped, re.IGNORECASE)
                    if m and m.group(1).upper() == norm_id.upper():
                        return f"{subdir}/{md_file.name}", None
        return None, f"No work item found with ID '{slug}'."

    for candidate_dir in ("work/to-do", "work/done"):
        candidate = HYPERSPACE_ROOT / candidate_dir / f"{slug}.md"
        if candidate.exists():
            return f"{candidate_dir}/{slug}.md", None

    return None, f"Work item '{slug}' not found in work/to-do/ or work/done/."


# ---------------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------------

def _extract_section(md_text: str, section_name: str) -> str:
    """Extract the raw text of an H2 section by name (case-insensitive)."""
    lines = md_text.splitlines()
    start = None
    for i, line in enumerate(lines):
        m = re.match(r'^##\s+(.+)', line.strip())
        if m and m.group(1).strip().lower() == section_name.lower():
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for j in range(start, len(lines)):
        if re.match(r'^#{1,2}\s+', lines[j].strip()):
            end = j
            break
    return "\n".join(lines[start:end])


def _extract_claims(text: str, source_section: str) -> list[dict]:
    """Extract file/line claims from a block of markdown text.

    Returns a list of dicts: {path, line_start, line_end, context, section}.
    `context` is the sentence/line the reference was found in, used later for
    token-overlap verification.

    Checks two shapes per line:
    1. Inline prose: `` `path` lines X-Y `` (path and line ref adjacent)
    2. Markdown table rows: a `` `path` `` cell plus a "line N" / "lines N-M"
       reference elsewhere in the same row (location tables in Design/
       Implementation Notes sections use this shape).
    """
    claims = []
    for line in text.splitlines():
        for m in _PATH_LINE_RE.finditer(line):
            path, line_start, line_end = m.group(1), m.group(2), m.group(3)
            claims.append({
                "path": path,
                "line_start": int(line_start) if line_start else None,
                "line_end": int(line_end) if line_end else (int(line_start) if line_start else None),
                "context": line.strip(),
                "section": source_section,
            })
        claims.extend(_extract_table_claims(line, source_section))
    return claims


def _extract_table_claims(line: str, source_section: str) -> list[dict]:
    """Extract claims from a single markdown table row.

    A table row may reference a path once but list multiple line numbers
    (e.g. "lines 63, 90" covering two sibling models in the same row) — each
    number produces its own claim so a stale reference to just one of them
    is still caught. Rows with a path cell but no line reference are treated
    as existence-only claims (line_start/line_end = None), matching the
    "unverifiable" / existence-check behavior of _verify_claim.

    May produce claims that duplicate ones already found by the inline-prose
    regex in _extract_claims (e.g. when a table cell happens to also satisfy
    the adjacent `` `path` line N `` shape) — this is intentional. The caller
    (validate_work_item_claims) de-dupes by (path, line_start, line_end), so
    an overlapping single-number match collapses harmlessly while additional
    numbers in a comma-separated list (like the "90" in "lines 63, 90") still
    surface as their own claims.
    """
    if not _TABLE_ROW_RE.match(line):
        return []

    path_match = _TABLE_PATH_CELL_RE.search(line)
    if not path_match:
        return []
    path = path_match.group(1)

    ref_match = _TABLE_LINE_REF_RE.search(line)
    if not ref_match:
        return [{
            "path": path,
            "line_start": None,
            "line_end": None,
            "context": line.strip(),
            "section": source_section,
        }]

    # Collect every distinct number mentioned in the line-ref phrase
    # ("lines 63, 90" -> [63, 90]; "lines 16-20" -> range handled as one claim).
    numbers = [int(n) for n in re.findall(r'\d+', ref_match.group(0))]
    if len(numbers) >= 2 and '-' in ref_match.group(0):
        # Range form: one claim spanning start-end
        return [{
            "path": path,
            "line_start": numbers[0],
            "line_end": numbers[-1],
            "context": line.strip(),
            "section": source_section,
        }]

    # Comma-separated or single form: one claim per number
    return [
        {
            "path": path,
            "line_start": n,
            "line_end": n,
            "context": line.strip(),
            "section": source_section,
        }
        for n in numbers
    ]


def _extract_unchecked_tasks(md_text: str) -> list[str]:
    """Extract unchecked task bullets from the Tasks section."""
    tasks_text = _extract_section(md_text, "tasks")
    tasks = []
    for line in tasks_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [ ]"):
            tasks.append(stripped[5:].strip())
    return tasks


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _identifier_tokens(text: str) -> set[str]:
    """Extract meaningful identifier-like tokens from claim context text."""
    tokens = {t for t in _IDENTIFIER_RE.findall(text)}
    return {t for t in tokens if t.lower() not in _STOPWORDS}


def _verify_claim(claim: dict) -> dict:
    """Check a single file/line claim against the actual codebase.

    Returns the claim dict augmented with a 'result' key:
        - "file_missing"   — path does not exist under the workspace root
        - "verified"       — line content plausibly matches the claim
        - "line_moved"      — file exists, exact line didn't match, but a
                              matching window was found nearby
        - "unverifiable"   — file exists but no identifier tokens could be
                              checked (claim has no extractable content), or
                              no line number was given
        - "gap"            — file exists, line given, no match found within
                              the drift window — claim likely stale
    """
    full_path = WORKSPACE_ROOT / claim["path"]

    if not full_path.exists():
        claim["result"] = "file_missing"
        return claim

    if claim["line_start"] is None:
        claim["result"] = "unverifiable"
        claim["reason"] = "No line number given — existence-only check passed."
        return claim

    tokens = _identifier_tokens(claim["context"])
    if len(tokens) < MIN_MATCH_TOKENS:
        claim["result"] = "unverifiable"
        claim["reason"] = "No extractable identifiers in claim text to verify against."
        return claim

    try:
        file_lines = full_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError as e:
        claim["result"] = "unverifiable"
        claim["reason"] = f"Could not read file: {e}"
        return claim

    line_start = claim["line_start"]
    line_end = claim["line_end"] or line_start

    def _window_matches(lo: int, hi: int) -> bool:
        lo = max(0, lo - 1)
        hi = min(len(file_lines), hi)
        window_text = "\n".join(file_lines[lo:hi])
        window_tokens = _identifier_tokens(window_text)
        return len(tokens & window_tokens) >= MIN_MATCH_TOKENS

    # Exact claimed range (small padding for off-by-one line numbering)
    if _window_matches(line_start - 2, line_end + 2):
        claim["result"] = "verified"
        return claim

    # Drift window — content may have shifted
    if _window_matches(line_start - LINE_DRIFT_WINDOW, line_end + LINE_DRIFT_WINDOW):
        claim["result"] = "line_moved"
        return claim

    claim["result"] = "gap"
    return claim


# ---------------------------------------------------------------------------
# Document update
# ---------------------------------------------------------------------------

def _build_findings_block(findings: dict, now: str) -> str:
    """Render a markdown block summarizing findings for insertion into
    Implementation Notes."""
    lines = [f"**Claim verification sweep ({now}):**", ""]

    gaps = findings["gaps"]
    moved = findings["line_moved"]
    missing = findings["file_missing"]

    if missing:
        lines.append("- **Missing files** (referenced path no longer exists):")
        for c in missing:
            lines.append(f"  - `{c['path']}` — referenced in {c['section']}: \"{c['context'][:120]}\"")
        lines.append("")

    if gaps:
        lines.append("- **Stale line references** (file exists, claimed content not found nearby):")
        for c in gaps:
            rng = f"line {c['line_start']}" if c['line_start'] == c['line_end'] else f"lines {c['line_start']}-{c['line_end']}"
            lines.append(f"  - `{c['path']}` {rng} — referenced in {c['section']}: \"{c['context'][:120]}\"")
        lines.append("")

    if moved:
        lines.append("- **Line drift** (content found nearby, but not at the claimed line — file was likely edited):")
        for c in moved:
            rng = f"line {c['line_start']}" if c['line_start'] == c['line_end'] else f"lines {c['line_start']}-{c['line_end']}"
            lines.append(f"  - `{c['path']}` claimed {rng}, content found within {LINE_DRIFT_WINDOW} lines — verify and update the reference.")
        lines.append("")

    if findings.get("possibly_done_tasks"):
        lines.append("- **Open questions — unchecked tasks with matching code found:**")
        for t in findings["possibly_done_tasks"]:
            lines.append(f"  - \"{t}\" — related identifiers found in the codebase; confirm whether this task is actually complete.")
        lines.append("")

    lines.append("_Generated by validate_work_item_claims — heuristic pattern match, not proof. Review before acting._")
    return "\n".join(lines)


def _apply_document_update(rel_path: str, md_text: str, findings_block: str) -> str:
    """Insert the findings block into the Implementation Notes section,
    creating the section if it doesn't exist. Never touches other sections."""
    lines = md_text.splitlines()
    section_header_idx = None
    for i, line in enumerate(lines):
        m = re.match(r'^##\s+(.+)', line.strip())
        if m and m.group(1).strip().lower() == "implementation notes":
            section_header_idx = i
            break

    if section_header_idx is not None:
        # Find end of section (next H1/H2) and insert findings block just before it,
        # separated by a blank line from existing content.
        insert_at = len(lines)
        for j in range(section_header_idx + 1, len(lines)):
            if re.match(r'^#{1,2}\s+', lines[j].strip()):
                insert_at = j
                break
        # Trim trailing blank lines within the section before inserting
        while insert_at > section_header_idx + 1 and lines[insert_at - 1].strip() == "":
            insert_at -= 1
        new_lines = lines[:insert_at] + ["", findings_block, ""] + lines[insert_at:]
    else:
        # No Implementation Notes section — append one before PR Notes if present,
        # otherwise at the end of the file.
        pr_notes_idx = None
        for i, line in enumerate(lines):
            if re.match(r'^##\s+pr notes', line.strip(), re.IGNORECASE):
                pr_notes_idx = i
                break
        block = ["## Implementation Notes", "", findings_block, ""]
        if pr_notes_idx is not None:
            new_lines = lines[:pr_notes_idx] + block + [""] + lines[pr_notes_idx:]
        else:
            new_lines = lines + [""] + block

    return "\n".join(new_lines)


def _bump_updated_timestamp(md_text: str, now: str) -> str:
    """Bump the 'Updated:' metadata field to now, matching update_document's pattern."""
    lines = md_text.splitlines()
    new_lines = []
    updated_line_found = False
    for line in lines:
        stripped = line.strip().lstrip("- ")
        if re.match(r'(?:Last\s+)?Updated\s*:', stripped, re.IGNORECASE):
            new_lines.append(f"- Updated: {now}")
            updated_line_found = True
        else:
            new_lines.append(line)
    if not updated_line_found:
        for i, line in enumerate(new_lines):
            if re.match(r'^- Created:', line.strip(), re.IGNORECASE):
                new_lines.insert(i + 1, f"- Updated: {now}")
                break
    return "\n".join(new_lines)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def validate_work_item_claims(slug: str, apply_updates: bool = False) -> dict:
    """Sweep a work item's claims against the codebase and surface gaps.

    Args:
        slug: Work item filename (without .md) or WI-N id.
        apply_updates: If True, write findings into the document's
                       Implementation Notes section and bump Updated.
                       Defaults to False (dry-run / review-first).

    Returns:
        On error: {"error": ...}
        When clean: {"clean": True, "message": ..., "claims_checked": N}
        When gaps found: {"clean": False, "findings": {...}, "claims_checked": N,
                           "applied": bool, "diff_preview": str | None}
    """
    rel_path, error = _resolve_work_item(slug)
    if error:
        return {"error": error}

    full_path = HYPERSPACE_ROOT / rel_path.replace("/", "\\")
    try:
        md_text = full_path.read_text(encoding="utf-8")
    except OSError as e:
        return {"error": f"Could not read {rel_path}: {e}"}

    # --- Extract claims from the sections that carry file/line references ---
    design_text = _extract_section(md_text, "design")
    impl_notes = _extract_section(md_text, "implementation notes")
    tasks_text = _extract_section(md_text, "tasks")
    ac_text = _extract_section(md_text, "acceptance criteria")

    all_claims = (
        _extract_claims(design_text, "Design")
        + _extract_claims(impl_notes, "Implementation Notes")
        + _extract_claims(tasks_text, "Tasks")
        + _extract_claims(ac_text, "Acceptance Criteria")
    )

    # De-dupe identical (path, line_start, line_end) claims — same reference
    # often appears more than once in prose.
    seen = set()
    deduped = []
    for c in all_claims:
        key = (c["path"], c["line_start"], c["line_end"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    truncated = False
    if len(deduped) > MAX_FILE_READS:
        deduped = deduped[:MAX_FILE_READS]
        truncated = True

    verified_claims = [_verify_claim(c) for c in deduped]

    findings = {
        "file_missing": [c for c in verified_claims if c["result"] == "file_missing"],
        "gaps": [c for c in verified_claims if c["result"] == "gap"],
        "line_moved": [c for c in verified_claims if c["result"] == "line_moved"],
        "verified": [c for c in verified_claims if c["result"] == "verified"],
        "unverifiable": [c for c in verified_claims if c["result"] == "unverifiable"],
        "possibly_done_tasks": [],
    }

    # --- Secondary heuristic: unchecked tasks that mention identifiers
    # findable in the codebase — surfaced as open questions, never auto-checked ---
    unchecked = _extract_unchecked_tasks(md_text)
    for task in unchecked:
        task_claims = _extract_claims(task, "Tasks")
        for tc in task_claims:
            verified = _verify_claim(tc)
            if verified["result"] in ("verified", "line_moved"):
                findings["possibly_done_tasks"].append(task)
                break

    has_gaps = bool(
        findings["file_missing"] or findings["gaps"]
        or findings["line_moved"] or findings["possibly_done_tasks"]
    )

    result = {
        "path": rel_path,
        "claims_checked": len(verified_claims),
        "claims_truncated": truncated,
    }

    if not has_gaps:
        result["clean"] = True
        result["message"] = (
            f"No implementation gaps found. All {len(verified_claims)} verifiable "
            f"claim(s) in {rel_path} were checked against the codebase and hold up "
            f"(or carried no verifiable line reference)."
        )
        return result

    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    findings_block = _build_findings_block(findings, now)

    result["clean"] = False
    result["findings"] = {
        "file_missing": [
            {"path": c["path"], "section": c["section"], "context": c["context"]}
            for c in findings["file_missing"]
        ],
        "gaps": [
            {"path": c["path"], "line_start": c["line_start"], "line_end": c["line_end"],
             "section": c["section"], "context": c["context"]}
            for c in findings["gaps"]
        ],
        "line_moved": [
            {"path": c["path"], "line_start": c["line_start"], "line_end": c["line_end"],
             "section": c["section"], "context": c["context"]}
            for c in findings["line_moved"]
        ],
        "possibly_done_tasks": findings["possibly_done_tasks"],
    }
    result["summary"] = {
        "file_missing": len(findings["file_missing"]),
        "gaps": len(findings["gaps"]),
        "line_moved": len(findings["line_moved"]),
        "possibly_done_tasks": len(findings["possibly_done_tasks"]),
        "verified": len(findings["verified"]),
        "unverifiable": len(findings["unverifiable"]),
    }
    result["note"] = (
        "Findings are heuristic pattern matches against the codebase, not proof. "
        "Review before treating any item as confirmed."
    )

    if apply_updates:
        updated_text = _apply_document_update(rel_path, md_text, findings_block)
        updated_text = _bump_updated_timestamp(updated_text, now)
        if not updated_text.endswith("\n"):
            updated_text += "\n"
        try:
            full_path.write_text(updated_text, encoding="utf-8")
        except OSError as e:
            result["applied"] = False
            result["write_error"] = str(e)
            return result

        refresh_single(rel_path)
        regenerate_index_file()
        trigger_site_build(changed_path=rel_path)

        result["applied"] = True
        result["updated_timestamp"] = now
    else:
        result["applied"] = False
        result["diff_preview"] = findings_block

    return result
