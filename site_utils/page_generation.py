"""
HTML page templates, breadcrumbs, and top bar builders.
"""

import json
import re
from pathlib import Path, PurePosixPath

from .config import (
    OUTPUT_DIR,
    CATEGORY_ICONS,
    CATEGORY_LABELS,
    list_js_modules,
    list_hyperkit_js_modules,
    hypervisor_logo_svg,
    hypervisor_favicon_data_uri,
)


# ---------------------------------------------------------------------------
# Per-module <script> tags (app-local and Hyperkit)
# ---------------------------------------------------------------------------
# We emit one <script src="/js/..."> tag per module (instead of a single
# <script src="/app.js">) so that a parse error in one module does not
# abort execution of the rest of the bundle. Each <script> tag is a
# separate execution context; a SyntaxError or uncaught exception in one
# only kills that tag.
#
# Hyperkit modules (noise-field, greeting, cursor-trail, toast) load first - 
# app-local code (core/00-core.js onward) references window.HvNoiseField /
# HvGreeting / HvCursorTrail / HvToast and must find them already defined.
# They're copied to site/js/kit/ by copy_assets() in build.py.
#
# Order for app-local modules matches the historical concat exactly (see
# list_js_modules). `defer` ensures scripts execute in document order after
# HTML parsing completes, preserving the previous "bottom-of-body" semantics.
def _render_module_script_tags():
    lines = []
    for name in list_hyperkit_js_modules():
        lines.append(f'  <script src="/js/kit/{name}?v={{{{BUILD_ID}}}}" defer></script>')
    modules = list_js_modules()
    for rel in modules:
        lines.append(f'  <script src="/js/{rel}?v={{{{BUILD_ID}}}}" defer></script>')
    return "\n".join(lines)


# Rendered at module import time - build.py runs before page_generation
# is called for individual pages, so list_js_modules() reflects the
# current on-disk source layout.
MODULE_SCRIPT_TAGS = _render_module_script_tags()


# ---------------------------------------------------------------------------
# Theme defaults - loaded once at import time from theme-defaults.json
# ---------------------------------------------------------------------------

_THEME_DEFAULTS_PATH = OUTPUT_DIR.parent / "theme-defaults.json"


# DEPRECATED: Theme state now lives in preferences.json, loaded via the JS bridge.
# No inline script needed - the baked-in seeding was the source of palette loss bugs.
# These remain as empty stubs so any import references don't break.
def get_theme_defaults_script():
    return ""


THEME_DEFAULTS_SCRIPT = ""


# ---------------------------------------------------------------------------
# Site navigation rail - populated once per build by set_nav_categories()
# ---------------------------------------------------------------------------

_NAV_CATEGORIES = []  # list of (dir_name, doc_count, children)
# children = list of (child_dir_name, child_count)
_NAV_RECENT_DIRS = set()  # set of dir names with recent activity
_ACTIVE_LAYOUT = "cyberdeck"  # active layout pack name


def set_nav_categories(categories, recent_dirs=None, layout="cyberdeck"):
    """Set the global category data used to render the site nav on every page.

    Call this once at the start of a build before generating any pages.
    categories: list of (dir_name, doc_count, children) where children is
                a list of (child_name, child_count) tuples.
    layout: active layout name (read from preferences.json by build.py).
    """
    global _NAV_CATEGORIES, _NAV_RECENT_DIRS, _ACTIVE_LAYOUT
    _NAV_CATEGORIES = categories
    _NAV_RECENT_DIRS = recent_dirs or set()
    _ACTIVE_LAYOUT = layout


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TOP_BAR = """\
<header class="topbar">
  <div class="topbar-inner">
    <div class="topbar-left">
      <a href="/index.html" class="brand">
        {{BRAND_ICON}}
      </a>
      <nav class="breadcrumbs" aria-label="Breadcrumb">{{BREADCRUMBS}}</nav>
    </div>
    <div class="topbar-right">
      <div class="nav-menu-wrap">
        <button class="nav-menu-btn" id="nav-menu-btn" aria-label="Menu">
          <i data-lucide="chevrons-left" class="nav-menu-btn-icon"></i>
        </button>
        <div class="nav-backdrop" id="nav-backdrop"></div>
        <aside class="nav-panel" id="nav-panel" role="region" aria-label="Navigation">

          <div class="nav-tab-bar" role="tablist">
            <button class="nav-tab" role="tab" aria-selected="false" aria-controls="nav-tab-navigate" id="nav-tab-btn-navigate">Navigate</button>
            <button class="nav-tab active" role="tab" aria-selected="true" aria-controls="nav-tab-settings" id="nav-tab-btn-settings">Settings</button>
            <button class="nav-tab" role="tab" aria-selected="false" aria-controls="nav-tab-a11y" id="nav-tab-btn-a11y">Access</button>
          </div>
          <div class="nav-panel-body">
            <div class="nav-tab-content" id="nav-tab-navigate" role="tabpanel" aria-labelledby="nav-tab-btn-navigate">
            <div class="nav-group">
              <div class="nav-group-label">Navigate</div>
              <a href="/_pins/index.html" class="nav-link" id="nav-pinboard-link">
                <i data-lucide="pin" class="nav-link-icon"></i>
                <span class="nav-link-text">Pinboard</span>
              </a>
              <a href="/learn/index.html" class="nav-link">
                <i data-lucide="graduation-cap" class="nav-link-icon"></i>
                <span class="nav-link-text">Learn</span>
              </a>
              <a href="/_about/index.html" class="nav-link">
                <i data-lucide="info" class="nav-link-icon"></i>
                <span class="nav-link-text">About</span>
              </a>
              <div class="nav-link nav-link-action" id="nav-ref-btn">
                <i data-lucide="text-search" class="nav-link-icon"></i>
                <span class="nav-link-text">Reference</span>
              </div>
              <div class="nav-link-sub" id="nav-ref-list"></div>
            </div>
            <div class="nav-group">
              <div class="nav-group-label">Utilities</div>
              <div id="nav-util-list"></div>
            </div>
            </div>
            <div class="nav-tab-content active" id="nav-tab-settings" role="tabpanel" aria-labelledby="nav-tab-btn-settings">
            <div class="nav-group">
              <div class="nav-group-label">Settings</div>
              <div class="settings-control">
                <span class="settings-control-label">Reading width</span>
                <button class="settings-toggle-btn" id="width-toggle" aria-label="Toggle reading width">
                  <i data-lucide="columns-2" class="settings-toggle-icon" id="width-toggle-icon"></i>
                  <span class="settings-toggle-state" id="width-toggle-state">Full</span>
                </button>
              </div>
              <div class="settings-control">
                <span class="settings-control-label">Zoom</span>
                <div class="settings-zoom">
                  <button class="settings-zoom-btn" id="zoom-out" aria-label="Zoom out">
                    <i data-lucide="minus" class="settings-zoom-icon"></i>
                  </button>
                  <span class="settings-zoom-level" id="zoom-level">100%</span>
                  <button class="settings-zoom-btn" id="zoom-in" aria-label="Zoom in">
                    <i data-lucide="plus" class="settings-zoom-icon"></i>
                  </button>
                </div>
              </div>
              <div class="settings-control" id="fullscreen-row" style="display:none">
                <span class="settings-control-label">Fullscreen</span>
                <button class="settings-toggle-btn fullscreen-toggle" id="fullscreen-toggle" aria-label="Toggle fullscreen">
                  <i data-lucide="maximize" class="settings-toggle-icon" id="fullscreen-toggle-icon"></i>
                </button>
              </div>
              <div class="settings-control" id="rebuild-row" style="display:none">
                <span class="settings-control-label">Rebuild site</span>
                <button class="settings-toggle-btn" id="rebuild-btn" aria-label="Rebuild site">
                  <i data-lucide="refresh-cw" class="settings-toggle-icon" id="rebuild-btn-icon"></i>
                </button>
              </div>
              <div class="settings-control mcp-control" id="mcp-row" style="display:none">
                <span class="settings-control-label">
                  MCP service
                  <span class="status-chip status-chip-outlined-muted mcp-state" id="mcp-state">&hellip;</span>
                </span>
                <div class="mcp-actions">
                  <button class="settings-toggle-btn" id="mcp-restart-btn" aria-label="Restart MCP service" data-tooltip="Restart - picks up code changes">
                    <i data-lucide="rotate-cw" class="settings-toggle-icon" id="mcp-restart-icon"></i>
                  </button>
                  <button class="settings-toggle-btn mcp-stop-btn" id="mcp-stop-btn" aria-label="Stop MCP service" data-tooltip="Stop the service">
                    <i data-lucide="power" class="settings-toggle-icon" id="mcp-stop-icon"></i>
                  </button>
                </div>
              </div>
            </div>
            <div class="nav-group">
              <div class="nav-group-label">Theme</div>
              <div class="settings-preset-row" id="preset-selector">
                <select class="preset-select form-select" id="preset-select">
                  <option value="custom">Custom</option>
                </select>
              </div>
              <div class="settings-theme-row" id="theme-custom-row">
                <input type="color" id="accent-color" class="settings-color-input" value="#00ff41">
                <div class="palette-preview" id="palette-preview">
                  <span class="swatch" data-tooltip="accent"></span>
                  <span class="swatch" data-tooltip="warm"></span>
                  <span class="swatch" data-tooltip="cool"></span>
                  <span class="swatch" data-tooltip="comp"></span>
                </div>
                <button class="settings-palette-mode" id="palette-mode">SPL</button>
              </div>
              <label class="a11y-toggle" style="margin-top: 0.6rem;">
                <input type="checkbox" id="a11y-bw-theme" data-a11y="bw-theme">
                <span class="a11y-toggle-label">Light mode</span>
                <span class="a11y-toggle-desc">Light background with blue accent</span>
              </label>
              <div class="settings-control" id="save-theme-row" style="display:none;margin-top:0.5rem">
                <span class="settings-control-label">Save config as site default</span>
                <button class="settings-toggle-btn" id="save-theme-btn" aria-label="Save current theme as site default">
                  <i data-lucide="save" class="settings-toggle-icon" id="save-theme-icon"></i>
                </button>
              </div>
            </div>
            </div>
            <div class="nav-tab-content" id="nav-tab-a11y" role="tabpanel" aria-labelledby="nav-tab-btn-a11y">
            <div class="nav-group">
              <div class="nav-group-label">Accessibility</div>
              <div class="a11y-panel-body">
                <div class="a11y-group">
                  <div class="a11y-group-label">Vision</div>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-high-contrast" data-a11y="high-contrast">
                    <span class="a11y-toggle-label">High contrast</span>
                    <span class="a11y-toggle-desc">AA contrast ratios for all text</span>
                  </label>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-large-text" data-a11y="large-text">
                    <span class="a11y-toggle-label">Large text</span>
                    <span class="a11y-toggle-desc">18px base, increased line height</span>
                  </label>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-font-smoothing" data-a11y="font-smoothing">
                    <span class="a11y-toggle-label">Font smoothing</span>
                    <span class="a11y-toggle-desc">Antialiased glyph rendering</span>
                  </label>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-focus-indicators" data-a11y="focus-indicators">
                    <span class="a11y-toggle-label">Enhanced focus</span>
                    <span class="a11y-toggle-desc">Thicker, high-contrast focus rings</span>
                  </label>
                </div>
                <div class="a11y-group">
                  <div class="a11y-group-label">Motion</div>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-reduce-motion" data-a11y="reduce-motion">
                    <span class="a11y-toggle-label">Reduce motion</span>
                    <span class="a11y-toggle-desc">Disable animations and transitions</span>
                  </label>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-no-glitch" data-a11y="no-glitch">
                    <span class="a11y-toggle-label">Disable glitch</span>
                    <span class="a11y-toggle-desc">Stop text scramble effect</span>
                  </label>
                </div>
                <div class="a11y-group">
                  <div class="a11y-group-label">Navigation</div>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-system-cursors" data-a11y="system-cursors">
                    <span class="a11y-toggle-label">System cursors</span>
                    <span class="a11y-toggle-desc">Restore default mouse pointers</span>
                  </label>
                  <label class="a11y-toggle">
                    <input type="checkbox" id="a11y-hide-indicators" data-a11y="hide-indicators">
                    <span class="a11y-toggle-label">Hide indicators</span>
                    <span class="a11y-toggle-desc">Turn off recent-update blips</span>
                  </label>
                </div>
                <div class="a11y-reset-wrap">
                  <button class="a11y-reset" id="a11y-reset">Reset all</button>
                </div>
              </div>
            </div>
            </div>
          </div>
        </aside>
      </div>
    </div>
  </div>
  <div class="topbar-clock" id="footer-clock"></div>
</header>"""

# Legacy full-page template - used for standalone HTML exports and fallback
# rendering. Content is baked directly into the page via {{CONTENT}}.
LEGACY_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="splash-screen-active">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="build-id" content="{{BUILD_ID}}">
  <title>{{TITLE}} - Hypervisor</title>
  <link rel="icon" href="{{FAVICON}}">
  <link rel="stylesheet" href="/style.css?v={{BUILD_ID}}">
</head>
<body>
  <div class="splash-screen" id="splash-screen">
    <div class="splash-screen-flag">
      {{SPLASH_EYE}}
    </div>
  </div>
  {{TOPBAR}}
  {{SITE_NAV}}
  {{TOC_SIDEBAR}}
  <main class="page">
    <article class="markdown-body">
      {{CONTENT}}
    </article>
  </main>
  <footer class="page-footer">
    <span class="source-path">{{REL_PATH}}</span>
    <span class="footer-sep">|</span>
    <span class="footer-label">hypervisor</span>
  </footer>
  <div class="modal-overlay search-overlay" id="search-overlay">
    <div class="modal-panel search-modal" id="search-modal" role="dialog" aria-label="Search hyperspace">
      <div class="search-input-row">
        <i data-lucide="search" class="search-input-icon"></i>
        <input type="text" id="search" aria-label="Search hyperspace" placeholder="search hyperspace..." autocomplete="off" spellcheck="false">
        <span class="search-input-shortcut">esc</span>
      </div>
      <div class="search-results" id="search-results" aria-live="polite"></div>
    </div>
  </div>
  <button class="scroll-top" id="scroll-top" aria-label="Scroll to top"><i data-lucide="arrow-up"></i></button>
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>
    mermaid.initialize({
      startOnLoad: true,
      theme: 'dark',
      themeVariables: {
        darkMode: true,
        background: '#000000',
        primaryColor: '#0a2a0a',
        primaryTextColor: '#00ff41',
        primaryBorderColor: '#00ff41',
        lineColor: '#00ff41',
        secondaryColor: '#1a1a00',
        secondaryTextColor: '#ffb000',
        secondaryBorderColor: '#ffb000',
        tertiaryColor: '#001a1a',
        tertiaryTextColor: '#00cccc',
        tertiaryBorderColor: '#00cccc',
        noteBkgColor: '#0a0a0a',
        noteTextColor: '#b0b0b0',
        noteBorderColor: '#333333',
        fontFamily: "'Departure Mono', 'JetBrains Mono', 'Cascadia Code', monospace",
        fontSize: '14px'
      },
      flowchart: { curve: 'linear', padding: 15 },
      er: { useMaxWidth: true },
      sequence: { useMaxWidth: true, mirrorActors: false }
    });
  </script>
{{MODULE_SCRIPTS}}
</body>
</html>"""


def build_site_nav(categories, recent_dirs=None, layout="cyberdeck"):
    """Build the vertical site navigation rail HTML.

    Args:
        categories: list of (dir_name, doc_count, children) tuples
        recent_dirs: dict of {directory_name: recent_count}
        layout: active layout name (reserved for future use)
    """
    if recent_dirs is None:
        recent_dirs = {}

    return _build_cyberdeck_nav(categories, recent_dirs)


def _build_cyberdeck_nav(categories, recent_dirs):
    """Standard cyberdeck nav rail - compact items with border-bottom."""
    html = ['<nav class="site-nav" id="site-nav" aria-label="Categories">']
    for item in categories:
        dir_name, count = item[0], item[1]
        children = item[2] if len(item) > 2 else []
        if dir_name == "reference":
            continue
        label = CATEGORY_LABELS.get(dir_name, dir_name.replace("-", " ").replace("_", " ").title())
        icon = CATEGORY_ICONS.get(dir_name, "folder")
        recent_cls = " site-nav-item-recent" if dir_name in recent_dirs else ""
        html.append(
            f'<a href="/{dir_name}/index.html" class="site-nav-item{recent_cls}" data-category="{dir_name}">'
            f'<i data-lucide="{icon}" class="site-nav-icon"></i>'
            f'<span class="site-nav-label">{label}</span>'
            f'<span class="site-nav-count">{count}</span>'
            f'</a>'
        )
        if children:
            html.append(f'<div class="site-nav-children" data-parent="{dir_name}">')
            for child_name, child_count in children:
                child_label = CATEGORY_LABELS.get(child_name, child_name.replace("-", " ").replace("_", " ").title())
                child_icon = CATEGORY_ICONS.get(child_name, "folder")
                child_key = f"{dir_name}/{child_name}"
                child_recent = " site-nav-child-recent" if child_key in recent_dirs else ""
                html.append(
                    f'<a href="/{dir_name}/{child_name}/index.html" class="site-nav-child{child_recent}" data-category="{dir_name}/{child_name}">'
                    f'<i data-lucide="{child_icon}" class="site-nav-child-icon"></i>'
                    f'<span class="site-nav-label">{child_label}</span>'
                    f'<span class="site-nav-count">{child_count}</span>'
                    f'</a>'
                )
            html.append('</div>')
    # Pinboard shortcut
    html.append(
        f'<a href="/_pins/index.html" class="site-nav-item site-nav-item-pins" data-category="_pins">'
        f'<i data-lucide="pin" class="site-nav-icon"></i>'
        f'<span class="site-nav-label">Pinboard</span>'
        f'<span class="site-nav-count site-nav-pin-count"></span>'
        f'</a>'
    )
    html.append('</nav>')
    return "\n".join(html)


def make_breadcrumbs(rel_path_str):
    """Build breadcrumb HTML with links. Each segment links to its directory index."""
    parts = PurePosixPath(rel_path_str).parts
    crumbs = [f'<a href="/index.html" class="crumb crumb-link">~</a>']
    accumulated = ""
    for i, part in enumerate(parts):
        label = part.replace("-", " ").replace("_", " ").replace(".md", "")
        accumulated = f"{accumulated}/{part}" if accumulated else part
        if i < len(parts) - 1:
            # Link to directory index
            link = f"/{accumulated}/index.html"
            crumbs.append(f'<a href="{link}" class="crumb crumb-link">{label}</a>')
        else:
            crumbs.append(f'<span class="crumb">{label}</span>')
    return '<span class="crumb-sep"><i data-lucide="chevron-right"></i></span>'.join(crumbs)


def build_topbar(breadcrumbs_html):
    return TOP_BAR.replace("{{BREADCRUMBS}}", breadcrumbs_html)


def build_page(content_html, title, rel_path_str, toc_html="", backlinks_html="", build_id="0", site_nav_html=None):
    bc = make_breadcrumbs(rel_path_str)
    topbar = build_topbar(bc)

    # Auto-generate site nav if not explicitly provided
    if site_nav_html is None:
        if _NAV_CATEGORIES:
            site_nav_html = build_site_nav(_NAV_CATEGORIES, _NAV_RECENT_DIRS, _ACTIVE_LAYOUT)
        else:
            site_nav_html = ""

    # Build TOC sidebar if there are enough headings
    toc_sidebar = ""
    if toc_html and toc_html.strip() and '<li>' in toc_html:
        # Only show TOC if there are at least 3 items
        li_count = toc_html.count('<li>')
        if li_count >= 3:
            toc_sidebar = (
                '<nav class="toc-sidebar" id="toc-sidebar" aria-label="Table of contents">'
                '<div class="panel-header"><i data-lucide="list" class="toc-icon"></i> Table of Contents</div>'
                '<div class="toc-body">' + toc_html + '</div>'
                '</nav>'
            )

    # Append backlinks to content if present
    full_content = content_html
    if backlinks_html:
        full_content += "\n" + backlinks_html

    return (
        LEGACY_PAGE_TEMPLATE
        .replace("{{TITLE}}", title)
        .replace("{{TOPBAR}}", topbar)
        .replace("{{SITE_NAV}}", site_nav_html)
        .replace("{{TOC_SIDEBAR}}", toc_sidebar)
        .replace("{{REL_PATH}}", rel_path_str)
        .replace("{{CONTENT}}", full_content)
        .replace("{{MODULE_SCRIPTS}}", MODULE_SCRIPT_TAGS)
        .replace("{{BUILD_ID}}", build_id)
    )


# ---------------------------------------------------------------------------
# Standalone export - a single self-contained HTML file
# ---------------------------------------------------------------------------
# The export reuses the real page template (build_page / LEGACY_PAGE_TEMPLATE)
# so the exported layout can never drift from the live site. It then makes the
# page stand alone: the external /style.css link is replaced with an inline
# <style> block, the module <script> tags are dropped (a static snapshot has no
# router to fetch fragments), and an export-mode override sheet hides the
# interactive chrome that only makes sense in the running app (nav menu, search,
# scroll-top, TOC drawer). The Lucide + Mermaid CDN scripts in the template are
# left in place so icons and diagrams still render when the file is opened with
# a network connection.

# Rules that neutralize the interactive chrome baked into the shared template.
# Kept here (not in the site CSS) because they are export-only.
_EXPORT_OVERRIDES = """
/* Export overrides - static single-file snapshot */
body.export-mode, body.export-mode * { cursor: auto !important; user-select: auto !important; -webkit-user-select: auto !important; }
body.export-mode { animation: none; }
body.export-mode .topbar::before { backdrop-filter: none; -webkit-backdrop-filter: none; background: #050505; }
body.export-mode .page { animation: none; }
body.export-mode .splash-screen { display: none !important; }
body.export-mode .site-nav { display: none !important; }
body.export-mode .nav-menu-wrap { display: none !important; }
body.export-mode .topbar-clock { display: none !important; }
body.export-mode .search-overlay, body.export-mode .search-wrap { display: none !important; }
body.export-mode .scroll-top { display: none !important; }
body.export-mode .toc-flag-wrap, body.export-mode .toc-flag-hit, body.export-mode .toc-drawer { display: none !important; }
body.export-mode .toc-sidebar { display: none !important; }
body.export-mode .code-copy, body.export-mode .section-copy { display: none !important; }
body.export-mode .page-footer { display: none !important; }

/* Scroll - the static file scrolls at the document level; the SPA's fixed
   viewport assumptions and the pageIn transform don't apply without the router. */
html, body { overflow-y: auto !important; height: auto !important; }

/* No nav rail in the export, so the recessed surface runs edge-to-edge
   symmetrically. The layout reserves a left inset for the rail (padding-left:
   --site-nav-width) - zero it so the surface is flush on both sides. The inner
   .markdown-body keeps its own reading padding. */
body.export-mode .page { padding-left: 0 !important; --site-nav-width: 0px; }
body.export-mode .page-doc-surface { padding-left: 0 !important; }

/* The recessed reading surface's entrance (dirSurfaceIn) is driven by the
   router adding .animate-in; a static file never gets that class, so force the
   surface visible at rest instead of leaving it stuck at its opacity:0 base. */
body.export-mode .page-doc-surface .markdown-body { opacity: 1 !important; animation: none !important; }

/* Wider reading inset - the live surface uses --surface-inset (3rem) all round, which
   reads tight against a full-width edge-to-edge surface. Give the content more
   horizontal breathing room from the surface border in the standalone export. */
body.export-mode .page-doc-surface .markdown-body { padding-left: 5rem !important; padding-right: 5rem !important; }

/* Align section heading text flush-left with body content. The section-icon
   (an <i data-lucide> that renders from the Lucide CDN) occupies width + a
   right margin inside the summary, pushing the heading text right of the body
   paragraphs and list items below it - the boxes align but the visible text
   doesn't. Hiding the icon in the static export restores a single left edge. */
body.export-mode .doc-section-summary .section-icon { display: none !important; }

/* Neutral export palette - the live site's bright accent is pure identity
   flourish, not state/category encoding, so a standalone snapshot reads better
   in a restrained desaturated tone. Remapping the base accent family cascades
   through the semantic roles (--success/--warning/etc.) that resolve via var().
   The grey ink scale and surfaces are left untouched. */
body.export-mode {
  --accent:        #8a97a8;
  --accent-dim:    #6b7686;
  --accent-glow:   rgba(138, 151, 168, 0.06);
  --accent-border: rgba(138, 151, 168, 0.18);
  --warm:          #b0a890;
  --cool:          #90a0a8;
  --comp:          #b08a8a;
}
"""


def build_export_page(content_html, title, rel_path_str, toc_html="", build_id="export"):
    """Render a document into a self-contained standalone HTML page.

    Reuses build_page so the layout matches the live site exactly, then inlines
    the built CSS and strips the runtime so the result opens as a single static
    file.

    Args:
        content_html: Rendered article HTML (inner content).
        title: Document title.
        rel_path_str: Source relative path (for breadcrumbs and footer).
        toc_html: Table of contents HTML (optional).
        build_id: Build id string for cache-busting (unused once CSS is inlined).

    Returns:
        Complete self-contained HTML string.
    """
    # Render through the real template with no nav rail and no backlinks - 
    # a single-doc snapshot has nowhere for those links to go.
    page = build_page(
        content_html, title, rel_path_str,
        toc_html=toc_html, backlinks_html="", build_id=build_id,
        site_nav_html="",
    )

    # Tag the body so the export overrides apply.
    page = page.replace('<body>', '<body class="export-mode">', 1)

    # The template marks <html class="splash-screen-active">; the live app's JS
    # removes it once the splash animation ends. A static export has no JS, so
    # the class would persist - and its `overflow: hidden` rule locks the page
    # from scrolling. Drop the class so the document scrolls normally.
    page = page.replace('<html lang="en" class="splash-screen-active">', '<html lang="en">', 1)

    # The recessed reading surface is applied at runtime by the router
    # (page-doc-surface on <main>, animate-in on the article). A static export
    # has no router, so bake both classes in - otherwise the surface never
    # renders and the content stays at its opacity:0 pre-animation state.
    page = page.replace(
        '<main class="page">',
        '<main class="page page-doc-surface">', 1,
    )
    page = page.replace(
        '<article class="markdown-body">',
        '<article class="markdown-body animate-in">', 1,
    )

    # Drop the site footer - not meaningful in a standalone single-page export.
    page = re.sub(
        r'\s*<footer class="page-footer">.*?</footer>',
        '', page, count=1, flags=re.DOTALL,
    )

    # Inline the built stylesheet in place of the external link so the file is
    # self-contained. The href carries a ?v=BUILD_ID query, so match by prefix.
    css_text = ""
    css_path = OUTPUT_DIR / "style.css"
    try:
        css_text = css_path.read_text(encoding="utf-8")
    except OSError:
        css_text = ""

    style_block = "<style>\n" + css_text + "\n" + _EXPORT_OVERRIDES + "\n</style>"
    link_re = re.compile(r'<link rel="stylesheet" href="/style\.css[^"]*">')
    if link_re.search(page):
        page = link_re.sub(style_block, page, count=1)
    else:
        # Fallback: inject before </head> if the link shape ever changes.
        page = page.replace("</head>", style_block + "\n</head>", 1)

    # Drop the per-module script tags - a static snapshot has no router and the
    # /js/* paths would 404. MODULE_SCRIPT_TAGS is a known block; remove each tag.
    for name in list_hyperkit_js_modules():
        page = re.sub(r'\s*<script src="/js/kit/' + re.escape(name) + r'[^"]*"[^>]*></script>', '', page)
    for rel in list_js_modules():
        rel_str = str(rel).replace("\\", "/")
        page = re.sub(r'\s*<script src="/js/' + re.escape(rel_str) + r'[^"]*"[^>]*></script>', '', page)

    return page


# ---------------------------------------------------------------------------
# SPA Shell - single HTML file generated once per build
# ---------------------------------------------------------------------------

SHELL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="splash-screen-active">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="build-id" content="{{BUILD_ID}}">
  <title>Hypervisor</title>
  <link rel="icon" href="{{FAVICON}}">
  <link rel="stylesheet" href="/style.css?v={{BUILD_ID}}">
</head>
<body>
  <div class="splash-screen" id="splash-screen">
    <div class="splash-screen-flag">
      {{SPLASH_EYE}}
    </div>
  </div>
  {{TOPBAR}}
  {{SITE_NAV}}
  <main class="page" id="page-main">
    <article class="markdown-body" id="content-target">
    </article>
  </main>
  <div class="toc-flag-wrap" id="toc-flag-wrap">
    <button class="toc-flag" id="toc-flag" aria-expanded="false" aria-controls="toc-drawer" aria-label="Open table of contents">
      <i data-lucide="list" class="toc-icon"></i> Contents
    </button>
  </div>
  <button class="toc-flag-hit" id="toc-flag-hit" tabindex="-1" aria-hidden="true"></button>
  <aside class="toc-drawer" id="toc-drawer" aria-hidden="true" aria-label="Table of contents">
    <div class="toc-body" id="toc-body"></div>
  </aside>
  <footer class="page-footer">
    <span class="source-path" id="source-path"></span>
    <span class="footer-sep">|</span>
    <span class="footer-label">hypervisor</span>
  </footer>
  <div class="modal-overlay search-overlay" id="search-overlay">
    <div class="modal-panel search-modal" id="search-modal" role="dialog" aria-label="Search hyperspace">
      <div class="search-input-row">
        <i data-lucide="search" class="search-input-icon"></i>
        <input type="text" id="search" aria-label="Search hyperspace" placeholder="search hyperspace..." autocomplete="off" spellcheck="false">
        <span class="search-input-shortcut">esc</span>
      </div>
      <div class="search-results" id="search-results" aria-live="polite"></div>
    </div>
  </div>
  <button class="scroll-top" id="scroll-top" aria-label="Scroll to top"><i data-lucide="arrow-up"></i></button>
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
{{MODULE_SCRIPTS}}
</body>
</html>"""


# ---------------------------------------------------------------------------
# Brand mark injection
# ---------------------------------------------------------------------------
# The topbar icon, splash-screen eye, and favicon all derive from a single
# source file: assets/hypervisor.svg. Templates carry {{BRAND_ICON}},
# {{SPLASH_EYE}}, and {{FAVICON}} placeholders which are resolved once here at
# import time. To rebrand, replace assets/hypervisor.svg - no template edits.
def _inject_brand(template: str) -> str:
    """Resolve brand-mark placeholders in a page template."""
    return (
        template
        .replace("{{BRAND_ICON}}", hypervisor_logo_svg("brand-icon"))
        .replace("{{SPLASH_EYE}}", hypervisor_logo_svg("splash-screen-eye"))
        .replace("{{FAVICON}}", hypervisor_favicon_data_uri())
    )


TOP_BAR = _inject_brand(TOP_BAR)
LEGACY_PAGE_TEMPLATE = _inject_brand(LEGACY_PAGE_TEMPLATE)
SHELL_TEMPLATE = _inject_brand(SHELL_TEMPLATE)



def build_shell(build_id, site_nav_html=None):
    """Generate the single SPA shell HTML.

    The shell contains the topbar, nav rail, TOC sidebar (empty container),
    main content area (empty), footer, and all scripts. Content is loaded
    dynamically via the client-side router.

    Args:
        build_id: Unique build identifier string.
        site_nav_html: Pre-rendered site navigation HTML. If None, generated
                       from current _NAV_CATEGORIES state.

    Returns:
        Complete HTML string for the shell page.
    """
    # Shell uses a minimal breadcrumb (just home) - the router updates it
    home_bc = '<span class="crumb crumb-link" data-crumb-home>~</span>'
    topbar = build_topbar(home_bc)

    if site_nav_html is None:
        if _NAV_CATEGORIES:
            site_nav_html = build_site_nav(_NAV_CATEGORIES, _NAV_RECENT_DIRS, _ACTIVE_LAYOUT)
        else:
            site_nav_html = ""

    return (
        SHELL_TEMPLATE
        .replace("{{TOPBAR}}", topbar)
        .replace("{{SITE_NAV}}", site_nav_html)
        .replace("{{MODULE_SCRIPTS}}", MODULE_SCRIPT_TAGS)
        .replace("{{BUILD_ID}}", build_id)
    )
