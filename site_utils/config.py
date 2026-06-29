"""
Hypervisor configuration — paths, constants, and shared markdown instance.
"""

import markdown
from pathlib import Path

# --- Paths ---
# config.py lives in site_utils/, so .parent.parent gets to .hypervisor/,
# and one more .parent gets to .hyperspace/ (the content root).
_HYPERVISOR_DIR = Path(__file__).resolve().parent.parent
HYPERSPACE_ROOT = _HYPERVISOR_DIR.parent
OUTPUT_DIR = _HYPERVISOR_DIR / "site"
ASSETS_DIR = _HYPERVISOR_DIR / "assets"

# --- Filters ---
SKIP_DIRS = {"__pycache__", "site", "learn", ".scratch", ".hyperagent"}
SKIP_FILES = {".gitkeep"}

# --- Markdown engine ---
MD = markdown.Markdown(
    extensions=["fenced_code", "codehilite", "tables", "toc", "meta", "sane_lists"],
    extension_configs={
        "codehilite": {"css_class": "highlight", "guess_lang": False},
        "toc": {"permalink": False},
    },
)

# --- Category metadata ---
CATEGORY_LABELS = {
    "context": "Context", "diagrams": "Diagrams", "work": "Work",
    "ideas": "Ideas", "patterns": "Patterns", "reference": "Reference",
    "research": "Research", "templates": "Templates", "analysis": "Analysis",
    "done": "Done", "to-do": "To-Do", ".hypervisor": "HV-META",
    ".external": "External", "prototypes": "Prototypes",
}

CATEGORY_DESCRIPTIONS = {
    "context": "Project overviews, architecture docs, and high-level references",
    "diagrams": "ERDs, system flows, and visual documentation",
    "work": "Actionable work items — design, acceptance criteria, tasks, and PR notes in one document",
    "ideas": "Lightweight concept capture for someday/maybe items",
    "patterns": "Reusable architectural patterns and proven solutions",
    "reference": "Quick-lookup cheatsheets, syntax tables, and code snippets",
    "research": "Technical investigations, comparisons, and ADRs",
    "templates": "Boilerplate starting points for new documents",
    "analysis": "Progress analysis, PR reviews, and milestone assessments",
    ".hypervisor": "Build scripts, assets, and configuration for the Hypervisor site generator",
    ".external": "External documents, vendor investigations, and third-party references",
}

CATEGORY_ICONS = {
    "context": "book-open", "diagrams": "git-branch", "work": "briefcase",
    "ideas": "lightbulb", "patterns": "puzzle", "reference": "text-search",
    "research": "microscope", "templates": "file-text", "analysis": "bar-chart-3",
    "done": "check-circle", "to-do": "circle-dot", ".hypervisor": "settings",
    ".external": "external-link", "prototypes": "layout",
}
