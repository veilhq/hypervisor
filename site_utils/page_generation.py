"""
HTML page templates, breadcrumbs, and top bar builders.
"""

import json
from pathlib import Path, PurePosixPath

from .config import OUTPUT_DIR, CATEGORY_ICONS, CATEGORY_LABELS


# ---------------------------------------------------------------------------
# Theme defaults — loaded once at import time from theme-defaults.json
# ---------------------------------------------------------------------------

_THEME_DEFAULTS_PATH = OUTPUT_DIR.parent / "theme-defaults.json"


# DEPRECATED: Theme state now lives in preferences.json, loaded via the JS bridge.
# No inline script needed — the baked-in seeding was the source of palette loss bugs.
# These remain as empty stubs so any import references don't break.
def get_theme_defaults_script():
    return ""


THEME_DEFAULTS_SCRIPT = ""


# ---------------------------------------------------------------------------
# Site navigation rail — populated once per build by set_nav_categories()
# ---------------------------------------------------------------------------

_NAV_CATEGORIES = []  # list of (dir_name, doc_count, children)
# children = list of (child_dir_name, child_count)
_NAV_RECENT_DIRS = set()  # set of dir names with recent activity


def set_nav_categories(categories, recent_dirs=None):
    """Set the global category data used to render the site nav on every page.

    Call this once at the start of a build before generating any pages.
    categories: list of (dir_name, doc_count, children) where children is
                a list of (child_name, child_count) tuples.
    """
    global _NAV_CATEGORIES, _NAV_RECENT_DIRS
    _NAV_CATEGORIES = categories
    _NAV_RECENT_DIRS = recent_dirs or set()


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TOP_BAR = """\
<header class="topbar">
  <div class="topbar-inner">
    <div class="topbar-left">
      <a href="/index.html" class="brand">
        <svg class="brand-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108.28 108.28" fill="currentColor"><path d="M98.58,11.9c-.13-.04-.27-.07-.43-.08-.16-.01-.33-.02-.51-.02-.36,0-.68.01-.94.03-.26.02-.49.08-.7.19-.13.1-.23.23-.31.37-.08.15-.14.29-.2.44-.13.29-.25.58-.35.87-.1.29-.22.58-.35.87-.18.33-.34.67-.47,1.01-.13.34-.26.69-.39,1.05-.34.79-.66,1.58-.98,2.36-.31.78-.64,1.57-.98,2.36-.18.42-.35.83-.49,1.23-.14.41-.32.81-.53,1.2-.05.1-.14.25-.25.44-.12.19-.28.26-.49.22-.18-.04-.31-.15-.39-.31-.08-.17-.14-.32-.2-.47-.21-.37-.38-.75-.51-1.14-.13-.38-.29-.76-.47-1.14-.52-1.12-1-2.25-1.44-3.39-.44-1.13-.92-2.26-1.44-3.39-.13-.29-.25-.58-.35-.87-.1-.29-.23-.58-.39-.87-.08-.17-.15-.33-.21-.48-.07-.16-.19-.29-.37-.39-.23-.12-.57-.19-1.01-.19h-1.25s-.13.03-.31.03c-.18.04-.34.11-.47.22-.1.15-.12.32-.04.53.08.21.14.37.2.5.18.35.34.71.49,1.06.14.35.32.71.53,1.06.05.1.1.21.14.33.04.11.08.22.14.33.16.33.31.66.45.98.14.32.29.65.45.98.52,1,1,2.01,1.42,3.03.43,1.02.9,2.03,1.42,3.03.05.1.09.19.12.27.03.07.06.16.12.27.13.29.27.6.41.92.14.32.29.63.45.92.13.23.23.46.31.7.08.24.21.44.39.61.18.19.47.29.86.3.39.01.79.02,1.21.02h.61c.2,0,.37-.03.53-.09.29-.1.47-.25.57-.45.09-.2.2-.41.33-.64.18-.33.34-.67.47-1,.13-.33.27-.67.43-1,.44-.85.84-1.72,1.19-2.59.35-.87.75-1.74,1.19-2.59.16-.27.29-.55.41-.83.12-.28.24-.56.37-.83.21-.37.38-.75.51-1.12.13-.37.3-.74.51-1.09.05-.1.09-.2.12-.3.03-.09.06-.19.12-.3.21-.35.39-.72.55-1.09.16-.37.31-.74.47-1.09.1-.19.15-.37.14-.56-.01-.19-.14-.32-.37-.41Z"/><path d="M90.15.15c-9.91,0-17.98,8.06-17.98,17.98s8.06,17.98,17.98,17.98,17.98-8.06,17.98-17.98S100.06.15,90.15.15ZM90.15,33.37c-8.4,0-15.24-6.84-15.24-15.24s6.84-15.24,15.24-15.24,15.24,6.84,15.24,15.24-6.84,15.24-15.24,15.24Z"/><path d="M72.23,36.05l-.04-.04h-34.8c-.63,0-1.14-.51-1.14-1.14V1.14c0-.63-.51-1.14-1.14-1.14H1.14C.51,0,0,.51,0,1.14v34.58c0,.3.12.59.33.8l33.56,33.56c.72.72.21,1.94-.8,1.94H1.14c-.63,0-1.14.51-1.14,1.14v33.98c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-33.73c0-.63.51-1.14,1.14-1.14h33.48c.63,0,1.14.51,1.14,1.14v33.73c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-34.58c0-.3-.12-.59-.33-.8l-35.71-35.71Z"/></svg>
      </a>
      <nav class="breadcrumbs" aria-label="Breadcrumb">{{BREADCRUMBS}}</nav>
    </div>
    <div class="search-wrap">
      <i data-lucide="search" class="search-icon"></i>
      <input type="text" id="search" placeholder="search...  ( / )" autocomplete="off" spellcheck="false">
      <div class="search-results" id="search-results"></div>
    </div>
    <div class="topbar-right">
      <div class="nav-menu-wrap">
        <button class="nav-menu-btn" id="nav-menu-btn" aria-label="Menu">
          <i data-lucide="chevrons-left" class="nav-menu-btn-icon"></i>
        </button>
        <div class="nav-backdrop" id="nav-backdrop"></div>
        <aside class="nav-panel" id="nav-panel" role="region" aria-label="Navigation">
          <div class="nav-panel-header">
            <i data-lucide="menu" style="width:11px;height:11px"></i>
            <span>Menu</span>
            <button class="nav-panel-close" id="nav-panel-close" aria-label="Close menu">&times;</button>
          </div>
          <div class="nav-panel-body">
            <div class="nav-group">
              <div class="nav-group-label">Navigate</div>
              <a href="/_pins/index.html" class="nav-link" id="nav-pinboard-link">
                <i data-lucide="pin" class="nav-link-icon"></i>
                <span class="nav-link-text">Pinboard</span>
                <span class="nav-link-desc">Your pinned documents</span>
              </a>
              <a href="/learn/index.html" class="nav-link">
                <i data-lucide="graduation-cap" class="nav-link-icon"></i>
                <span class="nav-link-text">Learn</span>
                <span class="nav-link-desc">How Hypervisor works</span>
              </a>
              <div class="nav-link nav-link-action" id="nav-ref-btn">
                <i data-lucide="text-search" class="nav-link-icon"></i>
                <span class="nav-link-text">Reference</span>
                <span class="nav-link-desc">Quick-access reference docs</span>
              </div>
              <div class="nav-link-sub" id="nav-ref-list"></div>
            </div>
            <div class="nav-group">
              <div class="nav-group-label">Utilities</div>
              <div id="nav-util-list"></div>
            </div>
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
            </div>
            <div class="nav-group">
              <div class="nav-group-label">Theme</div>
              <div class="settings-preset-row" id="preset-selector">
                <select class="preset-select" id="preset-select">
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
                <span class="a11y-toggle-label">Black & White</span>
                <span class="a11y-toggle-desc">Pure black/white greyscale, keeps accent color</span>
              </label>
              <div class="settings-control" id="save-theme-row" style="display:none;margin-top:0.5rem">
                <span class="settings-control-label">Save config as site default</span>
                <button class="settings-toggle-btn" id="save-theme-btn" aria-label="Save current theme as site default">
                  <i data-lucide="save" class="settings-toggle-icon" id="save-theme-icon"></i>
                </button>
              </div>
            </div>
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
        </aside>
      </div>
    </div>
  </div>
  <div class="topbar-clock" id="footer-clock"></div>
</header>"""

# Legacy full-page template — used for standalone HTML exports and fallback
# rendering. Content is baked directly into the page via {{CONTENT}}.
LEGACY_PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="hv-splash-active">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="build-id" content="{{BUILD_ID}}">
  <title>{{TITLE}} — Hypervisor</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 108.28 108.28'><g fill='%2300ff41'><path d='M98.58,11.9c-.13-.04-.27-.07-.43-.08-.16-.01-.33-.02-.51-.02-.36,0-.68.01-.94.03-.26.02-.49.08-.7.19-.13.1-.23.23-.31.37-.08.15-.14.29-.2.44-.13.29-.25.58-.35.87-.1.29-.22.58-.35.87-.18.33-.34.67-.47,1.01-.13.34-.26.69-.39,1.05-.34.79-.66,1.58-.98,2.36-.31.78-.64,1.57-.98,2.36-.18.42-.35.83-.49,1.23-.14.41-.32.81-.53,1.2-.05.1-.14.25-.25.44-.12.19-.28.26-.49.22-.18-.04-.31-.15-.39-.31-.08-.17-.14-.32-.2-.47-.21-.37-.38-.75-.51-1.14-.13-.38-.29-.76-.47-1.14-.52-1.12-1-2.25-1.44-3.39-.44-1.13-.92-2.26-1.44-3.39-.13-.29-.25-.58-.35-.87-.1-.29-.23-.58-.39-.87-.08-.17-.15-.33-.21-.48-.07-.16-.19-.29-.37-.39-.23-.12-.57-.19-1.01-.19h-1.25s-.13.03-.31.03c-.18.04-.34.11-.47.22-.1.15-.12.32-.04.53.08.21.14.37.2.5.18.35.34.71.49,1.06.14.35.32.71.53,1.06.05.1.1.21.14.33.04.11.08.22.14.33.16.33.31.66.45.98.14.32.29.65.45.98.52,1,1,2.01,1.42,3.03.43,1.02.9,2.03,1.42,3.03.05.1.09.19.12.27.03.07.06.16.12.27.13.29.27.6.41.92.14.32.29.63.45.92.13.23.23.46.31.7.08.24.21.44.39.61.18.19.47.29.86.3.39.01.79.02,1.21.02h.61c.2,0,.37-.03.53-.09.29-.1.47-.25.57-.45.09-.2.2-.41.33-.64.18-.33.34-.67.47-1,.13-.33.27-.67.43-1,.44-.85.84-1.72,1.19-2.59.35-.87.75-1.74,1.19-2.59.16-.27.29-.55.41-.83.12-.28.24-.56.37-.83.21-.37.38-.75.51-1.12.13-.37.3-.74.51-1.09.05-.1.09-.2.12-.3.03-.09.06-.19.12-.3.21-.35.39-.72.55-1.09.16-.37.31-.74.47-1.09.1-.19.15-.37.14-.56-.01-.19-.14-.32-.37-.41Z'/><path d='M90.15.15c-9.91,0-17.98,8.06-17.98,17.98s8.06,17.98,17.98,17.98,17.98-8.06,17.98-17.98S100.06.15,90.15.15ZM90.15,33.37c-8.4,0-15.24-6.84-15.24-15.24s6.84-15.24,15.24-15.24,15.24,6.84,15.24,15.24-6.84,15.24-15.24,15.24Z'/><path d='M72.23,36.05l-.04-.04h-34.8c-.63,0-1.14-.51-1.14-1.14V1.14c0-.63-.51-1.14-1.14-1.14H1.14C.51,0,0,.51,0,1.14v34.58c0,.3.12.59.33.8l33.56,33.56c.72.72.21,1.94-.8,1.94H1.14c-.63,0-1.14.51-1.14,1.14v33.98c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-33.73c0-.63.51-1.14,1.14-1.14h33.48c.63,0,1.14.51,1.14,1.14v33.73c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-34.58c0-.3-.12-.59-.33-.8l-35.71-35.71Z'/></g></svg>">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <div class="hv-splash" id="hv-splash">
    <div class="hv-splash-flag">
      <svg class="hv-splash-eye" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108.28 108.28" fill="currentColor"><path d="M98.58,11.9c-.13-.04-.27-.07-.43-.08-.16-.01-.33-.02-.51-.02-.36,0-.68.01-.94.03-.26.02-.49.08-.7.19-.13.1-.23.23-.31.37-.08.15-.14.29-.2.44-.13.29-.25.58-.35.87-.1.29-.22.58-.35.87-.18.33-.34.67-.47,1.01-.13.34-.26.69-.39,1.05-.34.79-.66,1.58-.98,2.36-.31.78-.64,1.57-.98,2.36-.18.42-.35.83-.49,1.23-.14.41-.32.81-.53,1.2-.05.1-.14.25-.25.44-.12.19-.28.26-.49.22-.18-.04-.31-.15-.39-.31-.08-.17-.14-.32-.2-.47-.21-.37-.38-.75-.51-1.14-.13-.38-.29-.76-.47-1.14-.52-1.12-1-2.25-1.44-3.39-.44-1.13-.92-2.26-1.44-3.39-.13-.29-.25-.58-.35-.87-.1-.29-.23-.58-.39-.87-.08-.17-.15-.33-.21-.48-.07-.16-.19-.29-.37-.39-.23-.12-.57-.19-1.01-.19h-1.25s-.13.03-.31.03c-.18.04-.34.11-.47.22-.1.15-.12.32-.04.53.08.21.14.37.2.5.18.35.34.71.49,1.06.14.35.32.71.53,1.06.05.1.1.21.14.33.04.11.08.22.14.33.16.33.31.66.45.98.14.32.29.65.45.98.52,1,1,2.01,1.42,3.03.43,1.02.9,2.03,1.42,3.03.05.1.09.19.12.27.03.07.06.16.12.27.13.29.27.6.41.92.14.32.29.63.45.92.13.23.23.46.31.7.08.24.21.44.39.61.18.19.47.29.86.3.39.01.79.02,1.21.02h.61c.2,0,.37-.03.53-.09.29-.1.47-.25.57-.45.09-.2.2-.41.33-.64.18-.33.34-.67.47-1,.13-.33.27-.67.43-1,.44-.85.84-1.72,1.19-2.59.35-.87.75-1.74,1.19-2.59.16-.27.29-.55.41-.83.12-.28.24-.56.37-.83.21-.37.38-.75.51-1.12.13-.37.3-.74.51-1.09.05-.1.09-.2.12-.3.03-.09.06-.19.12-.3.21-.35.39-.72.55-1.09.16-.37.31-.74.47-1.09.1-.19.15-.37.14-.56-.01-.19-.14-.32-.37-.41Z"/><path d="M90.15.15c-9.91,0-17.98,8.06-17.98,17.98s8.06,17.98,17.98,17.98,17.98-8.06,17.98-17.98S100.06.15,90.15.15ZM90.15,33.37c-8.4,0-15.24-6.84-15.24-15.24s6.84-15.24,15.24-15.24,15.24,6.84,15.24,15.24-6.84,15.24-15.24,15.24Z"/><path d="M72.23,36.05l-.04-.04h-34.8c-.63,0-1.14-.51-1.14-1.14V1.14c0-.63-.51-1.14-1.14-1.14H1.14C.51,0,0,.51,0,1.14v34.58c0,.3.12.59.33.8l33.56,33.56c.72.72.21,1.94-.8,1.94H1.14c-.63,0-1.14.51-1.14,1.14v33.98c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-33.73c0-.63.51-1.14,1.14-1.14h33.48c.63,0,1.14.51,1.14,1.14v33.73c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-34.58c0-.3-.12-.59-.33-.8l-35.71-35.71Z"/></svg>
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
    <button class="actions-trigger" id="actions-trigger" aria-label="Open actions drawer">actions</button>
  </footer>
  <div class="actions-drawer" id="actions-drawer" aria-hidden="true">
    <div class="actions-drawer-inner">
      <button class="action-item" id="edit-btn" aria-label="Edit document" style="display:none">
        <i data-lucide="pencil" class="action-icon"></i>
        <span class="action-label edit-btn-label">edit</span>
      </button>
      <button class="action-item" id="explorer-btn" aria-label="Open in file explorer" style="display:none">
        <i data-lucide="folder-open" class="action-icon"></i>
        <span class="action-label">explorer</span>
      </button>
      <button class="action-item" id="export-btn" aria-label="Export page as standalone HTML">
        <i data-lucide="package" class="action-icon"></i>
        <span class="action-label export-btn-label">export</span>
      </button>
      <button class="action-item" id="new-window-btn" aria-label="Open in new window" style="display:none">
        <i data-lucide="app-window" class="action-icon"></i>
        <span class="action-label">new window</span>
      </button>
      <button class="action-item" id="hyperagent-btn" aria-label="Launch Hyperagent" style="display:none">
        <i data-lucide="bot" class="action-icon"></i>
        <span class="action-label">hyperagent</span>
      </button>
      <button class="action-item" id="launch-dev-btn" aria-label="Launch dev environment" style="display:none">
        <i data-lucide="terminal" class="action-icon"></i>
        <span class="action-label">launch dev</span>
      </button>
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
  <script src="/app.js"></script>
</body>
</html>"""


def build_site_nav(categories, recent_dirs=None):
    """Build the vertical site navigation rail HTML.

    Args:
        categories: list of (dir_name, doc_count, children) tuples
        recent_dirs: dict of {directory_name: recent_count}
    """
    if recent_dirs is None:
        recent_dirs = {}

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
        # Render children (shown when parent is active)
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
            site_nav_html = build_site_nav(_NAV_CATEGORIES, _NAV_RECENT_DIRS)
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
                '<div class="hv-panel-header"><i data-lucide="list" class="toc-icon"></i> Contents</div>'
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
        .replace("{{BUILD_ID}}", build_id)
        .replace("{{REL_PATH}}", rel_path_str)
        .replace("{{CONTENT}}", full_content)
    )


# ---------------------------------------------------------------------------
# SPA Shell — single HTML file generated once per build
# ---------------------------------------------------------------------------

SHELL_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en" class="hv-splash-active">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="build-id" content="{{BUILD_ID}}">
  <title>Hypervisor</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 108.28 108.28'><g fill='%2300ff41'><path d='M98.58,11.9c-.13-.04-.27-.07-.43-.08-.16-.01-.33-.02-.51-.02-.36,0-.68.01-.94.03-.26.02-.49.08-.7.19-.13.1-.23.23-.31.37-.08.15-.14.29-.2.44-.13.29-.25.58-.35.87-.1.29-.22.58-.35.87-.18.33-.34.67-.47,1.01-.13.34-.26.69-.39,1.05-.34.79-.66,1.58-.98,2.36-.31.78-.64,1.57-.98,2.36-.18.42-.35.83-.49,1.23-.14.41-.32.81-.53,1.2-.05.1-.14.25-.25.44-.12.19-.28.26-.49.22-.18-.04-.31-.15-.39-.31-.08-.17-.14-.32-.2-.47-.21-.37-.38-.75-.51-1.14-.13-.38-.29-.76-.47-1.14-.52-1.12-1-2.25-1.44-3.39-.44-1.13-.92-2.26-1.44-3.39-.13-.29-.25-.58-.35-.87-.1-.29-.23-.58-.39-.87-.08-.17-.15-.33-.21-.48-.07-.16-.19-.29-.37-.39-.23-.12-.57-.19-1.01-.19h-1.25s-.13.03-.31.03c-.18.04-.34.11-.47.22-.1.15-.12.32-.04.53.08.21.14.37.2.5.18.35.34.71.49,1.06.14.35.32.71.53,1.06.05.1.1.21.14.33.04.11.08.22.14.33.16.33.31.66.45.98.14.32.29.65.45.98.52,1,1,2.01,1.42,3.03.43,1.02.9,2.03,1.42,3.03.05.1.09.19.12.27.03.07.06.16.12.27.13.29.27.6.41.92.14.32.29.63.45.92.13.23.23.46.31.7.08.24.21.44.39.61.18.19.47.29.86.3.39.01.79.02,1.21.02h.61c.2,0,.37-.03.53-.09.29-.1.47-.25.57-.45.09-.2.2-.41.33-.64.18-.33.34-.67.47-1,.13-.33.27-.67.43-1,.44-.85.84-1.72,1.19-2.59.35-.87.75-1.74,1.19-2.59.16-.27.29-.55.41-.83.12-.28.24-.56.37-.83.21-.37.38-.75.51-1.12.13-.37.3-.74.51-1.09.05-.1.09-.2.12-.3.03-.09.06-.19.12-.3.21-.35.39-.72.55-1.09.16-.37.31-.74.47-1.09.1-.19.15-.37.14-.56-.01-.19-.14-.32-.37-.41Z'/><path d='M90.15.15c-9.91,0-17.98,8.06-17.98,17.98s8.06,17.98,17.98,17.98,17.98-8.06,17.98-17.98S100.06.15,90.15.15ZM90.15,33.37c-8.4,0-15.24-6.84-15.24-15.24s6.84-15.24,15.24-15.24,15.24,6.84,15.24,15.24-6.84,15.24-15.24,15.24Z'/><path d='M72.23,36.05l-.04-.04h-34.8c-.63,0-1.14-.51-1.14-1.14V1.14c0-.63-.51-1.14-1.14-1.14H1.14C.51,0,0,.51,0,1.14v34.58c0,.3.12.59.33.8l33.56,33.56c.72.72.21,1.94-.8,1.94H1.14c-.63,0-1.14.51-1.14,1.14v33.98c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-33.73c0-.63.51-1.14,1.14-1.14h33.48c.63,0,1.14.51,1.14,1.14v33.73c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-34.58c0-.3-.12-.59-.33-.8l-35.71-35.71Z'/></g></svg>">
  <link rel="stylesheet" href="/style.css">
</head>
<body>
  <div class="hv-splash" id="hv-splash">
    <div class="hv-splash-flag">
      <svg class="hv-splash-eye" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 108.28 108.28" fill="currentColor"><path d="M98.58,11.9c-.13-.04-.27-.07-.43-.08-.16-.01-.33-.02-.51-.02-.36,0-.68.01-.94.03-.26.02-.49.08-.7.19-.13.1-.23.23-.31.37-.08.15-.14.29-.2.44-.13.29-.25.58-.35.87-.1.29-.22.58-.35.87-.18.33-.34.67-.47,1.01-.13.34-.26.69-.39,1.05-.34.79-.66,1.58-.98,2.36-.31.78-.64,1.57-.98,2.36-.18.42-.35.83-.49,1.23-.14.41-.32.81-.53,1.2-.05.1-.14.25-.25.44-.12.19-.28.26-.49.22-.18-.04-.31-.15-.39-.31-.08-.17-.14-.32-.2-.47-.21-.37-.38-.75-.51-1.14-.13-.38-.29-.76-.47-1.14-.52-1.12-1-2.25-1.44-3.39-.44-1.13-.92-2.26-1.44-3.39-.13-.29-.25-.58-.35-.87-.1-.29-.23-.58-.39-.87-.08-.17-.15-.33-.21-.48-.07-.16-.19-.29-.37-.39-.23-.12-.57-.19-1.01-.19h-1.25s-.13.03-.31.03c-.18.04-.34.11-.47.22-.1.15-.12.32-.04.53.08.21.14.37.2.5.18.35.34.71.49,1.06.14.35.32.71.53,1.06.05.1.1.21.14.33.04.11.08.22.14.33.16.33.31.66.45.98.14.32.29.65.45.98.52,1,1,2.01,1.42,3.03.43,1.02.9,2.03,1.42,3.03.05.1.09.19.12.27.03.07.06.16.12.27.13.29.27.6.41.92.14.32.29.63.45.92.13.23.23.46.31.7.08.24.21.44.39.61.18.19.47.29.86.3.39.01.79.02,1.21.02h.61c.2,0,.37-.03.53-.09.29-.1.47-.25.57-.45.09-.2.2-.41.33-.64.18-.33.34-.67.47-1,.13-.33.27-.67.43-1,.44-.85.84-1.72,1.19-2.59.35-.87.75-1.74,1.19-2.59.16-.27.29-.55.41-.83.12-.28.24-.56.37-.83.21-.37.38-.75.51-1.12.13-.37.3-.74.51-1.09.05-.1.09-.2.12-.3.03-.09.06-.19.12-.3.21-.35.39-.72.55-1.09.16-.37.31-.74.47-1.09.1-.19.15-.37.14-.56-.01-.19-.14-.32-.37-.41Z"/><path d="M90.15.15c-9.91,0-17.98,8.06-17.98,17.98s8.06,17.98,17.98,17.98,17.98-8.06,17.98-17.98S100.06.15,90.15.15ZM90.15,33.37c-8.4,0-15.24-6.84-15.24-15.24s6.84-15.24,15.24-15.24,15.24,6.84,15.24,15.24-6.84,15.24-15.24,15.24Z"/><path d="M72.23,36.05l-.04-.04h-34.8c-.63,0-1.14-.51-1.14-1.14V1.14c0-.63-.51-1.14-1.14-1.14H1.14C.51,0,0,.51,0,1.14v34.58c0,.3.12.59.33.8l33.56,33.56c.72.72.21,1.94-.8,1.94H1.14c-.63,0-1.14.51-1.14,1.14v33.98c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-33.73c0-.63.51-1.14,1.14-1.14h33.48c.63,0,1.14.51,1.14,1.14v33.73c0,.63.51,1.14,1.14,1.14h33.98c.63,0,1.14-.51,1.14-1.14v-34.58c0-.3-.12-.59-.33-.8l-35.71-35.71Z"/></svg>
    </div>
  </div>
  {{TOPBAR}}
  {{SITE_NAV}}
  <nav class="toc-sidebar" id="toc-sidebar" aria-label="Table of contents">
    <div class="hv-panel-header"><i data-lucide="list" class="toc-icon"></i> Contents</div>
    <div class="toc-body" id="toc-body"></div>
  </nav>
  <main class="page" id="page-main">
    <article class="markdown-body" id="content-target">
    </article>
  </main>
  <footer class="page-footer">
    <span class="source-path" id="source-path"></span>
    <span class="footer-sep">|</span>
    <span class="footer-label">hypervisor</span>
    <button class="actions-trigger" id="actions-trigger" aria-label="Open actions drawer">actions</button>
  </footer>
  <div class="actions-drawer" id="actions-drawer" aria-hidden="true">
    <div class="actions-drawer-inner">
      <button class="action-item" id="edit-btn" aria-label="Edit document" style="display:none">
        <i data-lucide="pencil" class="action-icon"></i>
        <span class="action-label edit-btn-label">edit</span>
      </button>
      <button class="action-item" id="explorer-btn" aria-label="Open in file explorer" style="display:none">
        <i data-lucide="folder-open" class="action-icon"></i>
        <span class="action-label">explorer</span>
      </button>
      <button class="action-item" id="export-btn" aria-label="Export page as standalone HTML">
        <i data-lucide="package" class="action-icon"></i>
        <span class="action-label export-btn-label">export</span>
      </button>
      <button class="action-item" id="new-window-btn" aria-label="Open in new window" style="display:none">
        <i data-lucide="app-window" class="action-icon"></i>
        <span class="action-label">new window</span>
      </button>
      <button class="action-item" id="hyperagent-btn" aria-label="Launch Hyperagent" style="display:none">
        <i data-lucide="bot" class="action-icon"></i>
        <span class="action-label">hyperagent</span>
      </button>
      <button class="action-item" id="launch-dev-btn" aria-label="Launch dev environment" style="display:none">
        <i data-lucide="terminal" class="action-icon"></i>
        <span class="action-label">launch dev</span>
      </button>
    </div>
  </div>
  <button class="scroll-top" id="scroll-top" aria-label="Scroll to top"><i data-lucide="arrow-up"></i></button>
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
  <script src="/app.js"></script>
</body>
</html>"""


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
    # Shell uses a minimal breadcrumb (just home) — the router updates it
    home_bc = '<span class="crumb crumb-link" data-crumb-home>~</span>'
    topbar = build_topbar(home_bc)

    if site_nav_html is None:
        if _NAV_CATEGORIES:
            site_nav_html = build_site_nav(_NAV_CATEGORIES, _NAV_RECENT_DIRS)
        else:
            site_nav_html = ""

    return (
        SHELL_TEMPLATE
        .replace("{{TOPBAR}}", topbar)
        .replace("{{SITE_NAV}}", site_nav_html)
        .replace("{{BUILD_ID}}", build_id)
    )
