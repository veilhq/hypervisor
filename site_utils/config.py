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
JS_DIR = ASSETS_DIR / "js"

# Hyperkit — shared design system package (WI-142 Phase 1). Canonical source
# for tokens.css / primitives.css and the ecosystem JS modules (HvNoiseField,
# HvGreeting, HvCursorTrail, HvToast). Lives one level up from .hypervisor/,
# alongside .hyperagent/ — a sibling app dir, not owned by either consumer.
HYPERKIT_DIR = HYPERSPACE_ROOT / ".hyperkit"
HYPERKIT_CSS_DIR = HYPERKIT_DIR / "css"
HYPERKIT_JS_DIR = HYPERKIT_DIR / "js"
HYPERKIT_PYTHON_DIR = HYPERKIT_DIR / "python"

# Make Hyperkit Python modules importable from site_utils submodules.
# This runs before __init__.py imports directory_index / markdown_processing,
# both of which import from chips (now in .hyperkit/python/).
import sys
sys.path.insert(0, str(HYPERKIT_PYTHON_DIR))

# Hyperkit JS modules, in load order. These must run before any app-local
# module that references window.HvNoiseField / HvGreeting / HvCursorTrail /
# HvToast (i.e. before core/00-core.js and features/*), so they are
# prepended ahead of everything list_js_modules() would otherwise return.
HYPERKIT_JS_MODULES = ["utils.js", "noise-field.js", "greeting.js", "cursor-trail.js", "toast.js", "cursor-box.js", "context-menu.js"]


def list_js_modules():
    """Return ordered list of JS module paths (relative to JS_DIR) in concat order.

    Order matches the historical bundle concat:
    core/ → features/ (non-zz) → webgl/ → screensaver/ (non-zz) →
    screensaver/zz-* → features/zz-*

    Each entry is a PurePosixPath relative to JS_DIR, e.g. 'core/00-core.js'.
    This is used by build.py (to copy + concat) and by page_generation.py
    (to emit per-module <script> tags for parse-error isolation — WI-118).

    Note: Hyperkit JS modules are NOT included here — they live outside
    JS_DIR and are emitted separately via list_hyperkit_js_modules() /
    copy_assets(), always ordered before this list's output.
    """
    from pathlib import PurePosixPath
    if not JS_DIR.exists():
        return []
    modules = []

    def _rel(p):
        return PurePosixPath(p.relative_to(JS_DIR).as_posix())

    def _add_sorted(subdir, skip_zz=False, only_zz=False):
        d = JS_DIR / subdir
        if not d.exists():
            return
        for f in sorted(d.glob("*.js")):
            is_zz = f.name.startswith("zz-")
            if skip_zz and is_zz:
                continue
            if only_zz and not is_zz:
                continue
            modules.append(_rel(f))

    _add_sorted("core")
    _add_sorted("features", skip_zz=True)
    _add_sorted("webgl", skip_zz=True)
    _add_sorted("screensaver", skip_zz=True)
    _add_sorted("screensaver", only_zz=True)
    _add_sorted("features", only_zz=True)
    return modules


def list_hyperkit_js_modules():
    """Return the Hyperkit JS module filenames that exist on disk, in load order.

    Missing files are skipped rather than raising — lets partial Hyperkit
    checkouts still build (a warning is logged by the caller in build.py).
    """
    if not HYPERKIT_JS_DIR.exists():
        return []
    return [name for name in HYPERKIT_JS_MODULES if (HYPERKIT_JS_DIR / name).exists()]


# --- Brand SVG (Hypervisor logo) ---
# Loaded once at module import from assets/hypervisor.svg. Exposed via
# hypervisor_logo_svg(css_class) which returns an inline <svg> string with the
# requested class and fill=currentColor (so it inherits accent/text color).
#
# Every surface that renders the brand mark — topbar, splash screen, favicon —
# derives from this single file. Dropping a new logo into assets/hypervisor.svg
# is the only step needed to rebrand; nothing downstream hardcodes path data.
def _load_logo_svg():
    """Read hypervisor.svg and return (viewbox, inner_markup)."""
    import re
    svg_path = ASSETS_DIR / "hypervisor.svg"
    if not svg_path.exists():
        return "0 0 35.95 35.95", ""
    text = svg_path.read_text(encoding="utf-8")
    # Extract viewBox
    m_vb = re.search(r'viewBox="([^"]+)"', text)
    viewbox = m_vb.group(1) if m_vb else "0 0 35.95 35.95"
    # Extract inner content between the first <svg ...> and closing </svg>
    m_inner = re.search(r'<svg[^>]*>(.*)</svg>', text, re.DOTALL)
    inner = m_inner.group(1).strip() if m_inner else ""
    # Collapse whitespace between tags so the markup inlines cleanly into
    # HTML templates and (URL-encoded) into the favicon data URI.
    inner = re.sub(r">\s+<", "><", inner)
    return viewbox, inner


_LOGO_VIEWBOX, _LOGO_INNER = _load_logo_svg()
_LOGO_SVG_TEMPLATE = (
    f'<svg class="{{css_class}}" xmlns="http://www.w3.org/2000/svg" '
    f'viewBox="{_LOGO_VIEWBOX}" fill="currentColor" aria-hidden="true">{_LOGO_INNER}</svg>'
)


def hypervisor_logo_svg(css_class: str = "brand-icon") -> str:
    """Return an inline <svg> element for the Hypervisor logo with the given
    CSS class. The SVG uses fill=currentColor so it inherits the parent text
    color (accent, muted, etc.).
    """
    return _LOGO_SVG_TEMPLATE.replace("{css_class}", css_class)


def hypervisor_favicon_data_uri(color: str = "#00ff41") -> str:
    """Return a `data:image/svg+xml,...` favicon URI for the Hypervisor logo.

    The markup uses single-quoted attributes (double quotes would terminate the
    surrounding href="...") and percent-encodes `#` so the hex color survives
    as a URI. Callers embed the result directly in <link rel="icon" href="...">.
    """
    inner = _LOGO_INNER.replace('"', "'")
    fill = color.replace("#", "%23")
    return (
        "data:image/svg+xml,"
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='{_LOGO_VIEWBOX}'>"
        f"<g fill='{fill}'>{inner}</g></svg>"
    )

# --- Eco-app SVG icons (orchestrator launcher row) ---
# Each app has a custom brand SVG. Loaded once at import, exposed via
# eco_app_icon_svg(app_name, css_class) for inline rendering.

def _load_eco_svg(path):
    """Read an SVG file and return (viewbox, inner_markup). Same logic as _load_logo_svg."""
    import re
    if not path.exists():
        return "", ""
    text = path.read_text(encoding="utf-8")
    m_vb = re.search(r'viewBox="([^"]+)"', text)
    viewbox = m_vb.group(1) if m_vb else ""
    m_inner = re.search(r'<svg[^>]*>(.*)</svg>', text, re.DOTALL)
    inner = m_inner.group(1).strip() if m_inner else ""
    inner = re.sub(r">\s+<", "><", inner)
    return viewbox, inner


_ECO_APP_SVGS = {}
_ECO_APP_PATHS = {
    "hypervisor": ASSETS_DIR / "hypervisor.svg",
    "hyperagent": HYPERSPACE_ROOT / ".hyperagent" / "assets" / "hyperagent.svg",
    "hypereye": HYPERSPACE_ROOT / ".hypereye" / "assets" / "hypereye.svg",
    "hyperfield": HYPERSPACE_ROOT / ".hyperfield" / "assets" / "hyperfield.svg",
    "hyperline": ASSETS_DIR / "SVG" / "hyperline.svg",
    "hypercycle": HYPERSPACE_ROOT / ".hypercycle" / "assets" / "icons" / "hypercycle.svg",
    "launchdev": ASSETS_DIR / "SVG" / "launchdev.svg",
}

for _app_name, _svg_path in _ECO_APP_PATHS.items():
    _vb, _inner = _load_eco_svg(_svg_path)
    if _vb:
        _ECO_APP_SVGS[_app_name] = (
            f'<svg class="{{css_class}}" xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="{_vb}" fill="currentColor" aria-hidden="true">{_inner}</svg>'
        )


def eco_app_icon_svg(app_name: str, css_class: str = "launcher-icon") -> str:
    """Return an inline <svg> for the given eco-app's brand mark.

    Returns empty string if the app SVG was not found at build time.
    """
    template = _ECO_APP_SVGS.get(app_name, "")
    return template.replace("{css_class}", css_class) if template else ""


# --- Filters ---
SKIP_DIRS = {
    "__pycache__", "site", "learn", ".scratch", ".kb",
    ".hyperagent", ".hyperkit", ".hypereye", ".events",
}
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
    "done": "Done", "to-do": "To-Do", ".hypervisor": "Metadata",
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
