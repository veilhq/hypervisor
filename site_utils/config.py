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


# --- Brand SVG (Hypervisor logo) ---
# Loaded once at module import from assets/hypervisor.svg. Exposed via
# hypervisor_logo_svg(css_class) which returns an inline <svg> string with the
# requested class and fill=currentColor (so it inherits accent/text color).
def _load_logo_svg():
    """Read hypervisor.svg, extract the inner path(s), and produce a template."""
    import re
    svg_path = ASSETS_DIR / "hypervisor.svg"
    if not svg_path.exists():
        return ""
    text = svg_path.read_text(encoding="utf-8")
    # Extract viewBox
    m_vb = re.search(r'viewBox="([^"]+)"', text)
    viewbox = m_vb.group(1) if m_vb else "0 0 108.28 108.28"
    # Extract inner content between the first <svg ...> and closing </svg>
    m_inner = re.search(r'<svg[^>]*>(.*)</svg>', text, re.DOTALL)
    inner = m_inner.group(1).strip() if m_inner else ""
    return f'<svg class="{{css_class}}" xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" fill="currentColor" aria-hidden="true">{inner}</svg>'


_LOGO_SVG_TEMPLATE = _load_logo_svg()


def hypervisor_logo_svg(css_class: str = "brand-icon") -> str:
    """Return an inline <svg> element for the Hypervisor logo with the given
    CSS class. The SVG uses fill=currentColor so it inherits the parent text
    color (accent, muted, etc.).
    """
    return _LOGO_SVG_TEMPLATE.replace("{css_class}", css_class)

# --- Filters ---
SKIP_DIRS = {"__pycache__", "site", "learn", ".scratch", ".hyperagent", ".hyperagent-lite"}
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
