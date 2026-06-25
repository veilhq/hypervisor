"""
Shared configuration: paths, constants, registries, transition maps.
"""

import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — ensure site_utils is importable
# ---------------------------------------------------------------------------
_HYPERVISOR_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_HYPERVISOR_DIR))

from site_utils.config import HYPERSPACE_ROOT, SKIP_DIRS, SKIP_FILES

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HYPERVISOR_DIR = _HYPERVISOR_DIR
CONFIG_DIR = _HYPERVISOR_DIR / "config"
STATE_DIR = _HYPERVISOR_DIR / "state"
TAGS_FILE = CONFIG_DIR / "tags.json"
PROJECTS_FILE = CONFIG_DIR / "projects.json"
WORK_ID_FILE = STATE_DIR / "work-item-counter.json"
INDEX_FILE = HYPERSPACE_ROOT / "_index.md"

# ---------------------------------------------------------------------------
# Status transition map (directed graph)
# ---------------------------------------------------------------------------
VALID_TRANSITIONS = {
    "Planned": {"In Progress", "Complete"},
    "In Progress": {"Complete"},
    "Complete": set(),  # immutable once complete
}

# ---------------------------------------------------------------------------
# Validation skips
# ---------------------------------------------------------------------------
VALIDATION_SKIP_DIRS = {"templates", ".external", ".hypervisor"}
VALIDATION_SKIP_FILES = {"_conventions.md", "_index.md", "_readme.md", "_meta.md"}
VALIDATION_SKIP_PATHS = {
    "context/ui-ux-consistency-content.md",
    "context/ui-ux-core-standards.md",
    "context/ui-ux-interaction-patterns.md",
}

# ---------------------------------------------------------------------------
# Document type → target directory
# ---------------------------------------------------------------------------
TYPE_DIRECTORIES = {
    "work-item": "work/to-do",
    "idea": "ideas",
    "bugfix": "research/bugfixes",
}

# ---------------------------------------------------------------------------
# Registry loaders
# ---------------------------------------------------------------------------

def load_tags() -> dict:
    """Load tag registry from tags.json."""
    if TAGS_FILE.exists():
        return json.loads(TAGS_FILE.read_text(encoding="utf-8"))
    return {}


def save_tags(tags: dict):
    """Persist tag registry to tags.json."""
    TAGS_FILE.write_text(
        json.dumps(tags, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_projects() -> list[str]:
    """Load valid project names from projects.json."""
    if PROJECTS_FILE.exists():
        data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        return data.get("projects", [])
    return []


# ---------------------------------------------------------------------------
# Work Item ID Counter
# ---------------------------------------------------------------------------

def next_work_id() -> str:
    """Allocate and return the next work item ID (e.g., 'WI-27').

    Reads the counter from work-item-counter.json, increments it, and persists.
    Thread-safe for single-process use (MCP server is single-threaded per tool call).
    """
    counter = 1
    if WORK_ID_FILE.exists():
        try:
            data = json.loads(WORK_ID_FILE.read_text(encoding="utf-8"))
            counter = data.get("next_id", 1)
        except (json.JSONDecodeError, OSError):
            counter = 1

    work_id = f"WI-{counter}"

    # Persist incremented counter
    WORK_ID_FILE.write_text(
        json.dumps({"next_id": counter + 1}, indent=2) + "\n",
        encoding="utf-8",
    )

    return work_id
