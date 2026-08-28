"""
Sprint operations — end_sprint cascade for relative horizon management.
"""

import re
from datetime import datetime
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import read_md

from .config import VALID_HORIZONS
from .helpers import trigger_site_build
from .index import rebuild_index
from .index_file import regenerate_index_file


# Cascade map: current horizon -> new horizon after end_sprint
_CASCADE = {
    "Sprint": "Sprint",       # Rolled over — still active work
    "Sprint+1": "Sprint",
    "Sprint+2": "Sprint+1",
    "Sprint+3": "Sprint+2",
    "Backlog": "Backlog",     # Unchanged
}


def _extract_horizon(md_text: str) -> str | None:
    """Extract the Horizon value from work item metadata."""
    for line in md_text.splitlines()[:30]:
        m = re.match(r'^-\s*Horizon\s*:\s*(.+)', line.strip(), re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def end_sprint() -> dict:
    """Cascade Horizon values forward for all open work items.

    Returns a summary dict with counts per transition.
    """
    todo_dir = HYPERSPACE_ROOT / "work" / "to-do"
    if not todo_dir.exists():
        return {"error": "work/to-do/ directory not found."}

    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    horizon_re = re.compile(r'^(-\s*Horizon\s*:\s*)(.+)$', re.IGNORECASE)
    updated_re = re.compile(r'^(-\s*Updated\s*:\s*)(.+)$', re.IGNORECASE)

    # Track transitions
    moved = {
        "Sprint+1 -> Sprint": 0,
        "Sprint+2 -> Sprint+1": 0,
        "Sprint+3 -> Sprint+2": 0,
        "Sprint (rolled over)": 0,
        "Backlog (unchanged)": 0,
        "No horizon (unchanged)": 0,
    }
    affected_files = []

    for md_file in sorted(todo_dir.glob("*.md")):
        if md_file.name.startswith("_"):
            continue

        md_text = read_md(md_file)
        current_horizon = _extract_horizon(md_text)

        # Items without a Horizon field are treated as Backlog — no change needed
        if current_horizon is None:
            moved["No horizon (unchanged)"] += 1
            continue

        # Normalize to canonical casing
        canonical = None
        for h in VALID_HORIZONS:
            if current_horizon.lower() == h.lower():
                canonical = h
                break

        if canonical is None:
            # Invalid horizon value — skip
            continue

        new_horizon = _CASCADE.get(canonical, canonical)

        if new_horizon == canonical:
            # No change needed (Sprint stays Sprint, Backlog stays Backlog)
            if canonical == "Sprint":
                moved["Sprint (rolled over)"] += 1
            else:
                moved["Backlog (unchanged)"] += 1
            continue

        # Apply the cascade — rewrite the file
        lines = md_text.splitlines()
        new_lines = []
        changed = False
        for line in lines:
            m = horizon_re.match(line.strip())
            if m:
                new_lines.append(f"- Horizon: {new_horizon}")
                changed = True
                continue
            m = updated_re.match(line.strip())
            if m:
                new_lines.append(f"- Updated: {now}")
                continue
            new_lines.append(line)

        if changed:
            final_content = "\n".join(new_lines)
            if not final_content.endswith("\n"):
                final_content += "\n"
            md_file.write_text(final_content, encoding="utf-8")

            transition_key = f"{canonical} -> {new_horizon}"
            if transition_key in moved:
                moved[transition_key] += 1
            else:
                moved[transition_key] = 1
            affected_files.append(str(md_file.relative_to(HYPERSPACE_ROOT)).replace("\\", "/"))

    # Rebuild index and trigger site build
    rebuild_index()
    regenerate_index_file()
    if affected_files:
        trigger_site_build(changed_path=affected_files[0])

    return {
        "success": True,
        "summary": moved,
        "files_updated": len(affected_files),
        "affected_files": affected_files,
    }
