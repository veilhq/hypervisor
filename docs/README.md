# HV-DESCRIPTION

Local static site generator that turns `.hyperspace` markdown documents into a browsable HTML knowledge base.

- Created: 2026-04-22T00:00
- Updated: 2026-07-14T09:43

## Quick Start

### Static Site (browser)

```bash
pip install markdown pygments
cd .hyperspace/.hypervisor
python build.py
```

This scans all `.md` documents in `.hyperspace/`, generates a static site in `.hypervisor/site/`, and opens it in your default browser.

### Desktop Application

```bash
pip install markdown pygments
pip install -r requirements-app.txt
cd .hyperspace/.hypervisor
python hypervisor-app.py
```

This launches Hypervisor as a native desktop window with:
- **Live file watching** — edit a `.md` file in your editor and the site rebuilds and refreshes automatically
- **Checkbox write-back** — click a task checkbox in the rendered view to toggle it in the source file
- **Status write-back** — click a Status field in the metadata bar to cycle through valid statuses
- **Scroll preservation** — the page stays at your current position after a rebuild

The desktop app uses PyWebView (Edge/WebView2 on Windows) and watchdog for file monitoring. The existing `python build.py` workflow continues to work independently.

## Overview

Hypervisor is a zero-framework tool: a Python entry point (`build.py`) backed by a `site_utils/` package, modular CSS in `assets/css/`, and modular JS in `assets/js/`. No React, no Node, no build pipeline. The generated site runs entirely from `file://` protocol — no web server needed.

## Directory Structure

```
.hyperspace/.hypervisor/
├── build.py                    # Entry point — orchestrator, CLI, incremental rebuild
├── hypervisor-app.py           # Desktop app entry point (PyWebView)
├── mcp-server.py              # MCP server entry point (Kiro AI integration)
├── hv_mcp/                    # MCP server logic package (19 tools)
├── watcher.py                  # File watcher with debouncing (watchdog)
├── requirements-app.txt        # Desktop app dependencies (pywebview, watchdog)
├── site_utils/                 # Build modules package
│   ├── __init__.py
│   ├── config.py               # Paths, constants, MD engine, category metadata
│   ├── file_utils.py           # File collection, path helpers, naming, dates
│   ├── markdown_processing.py  # Rendering + post-processing transforms
│   ├── page_generation.py      # HTML templates, breadcrumbs, topbar
│   ├── page_builders.py        # Homepage, pinboard, 404, utility, learn pages
│   ├── fragment.py             # Content fragment JSON schema, serialization
│   ├── directory_index.py      # Dir tree, home page, index generators
│   ├── search.py               # Search index builder
│   ├── build_cache.py          # Content hash caching for incremental builds
│   ├── backlinks.py            # Reverse-link index from .md cross-references
│   ├── ideas.py                # Idea delete/dismiss operations
│   ├── external_files.py       # .external/ import and delete operations
│   └── work_items.py           # Work item mark-done operations
├── assets/
│   ├── css/                    # Modular CSS (numbered files sorted, zz-* last)
│   │   ├── 00-variables.css    # Custom properties, resets, component base classes
│   │   ├── 01-layout.css       # Topbar, page, footer, breadcrumbs
│   │   ├── 02-search.css       # Search input, results, tag filtering, work item filters
│   │   ├── 03-menus.css        # Dropdowns, width toggle, accent picker
│   │   ├── 04-content.css      # Markdown body, code, tables
│   │   ├── 05-cards.css        # Card grid, doc lists, build stats
│   │   ├── 06-pinboard.css     # Pin cards, pin button, pinboard page
│   │   ├── 07-toc.css          # Floating table of contents
│   │   ├── 08-utilities.css    # Shared utility page container, 404 page
│   │   ├── utilities/          # Per-utility-page styles (loaded after numbered modules)
│   │   │   ├── password-gen.css
│   │   │   ├── quiz.css
│   │   │   ├── regex-editor.css
│   │   │   ├── screensaver-settings.css
│   │   │   ├── health-dashboard.css
│   │   │   └── palette-gen.css
│   │   ├── 09-effects.css      # Cursor companion, shortcuts overlay
│   │   ├── 10-splash.css       # Loading splash screen
│   │   ├── 11-tabs.css         # Tabbed document interface
│   │   ├── 12-drop-import.css  # Drag-and-drop file import zone
│   │   ├── 13-ideas-dismiss.css # Idea dismiss button
│   │   ├── 14-editor.css       # Inline markdown editor
│   │   ├── 15-command-palette.css # Command palette (Ctrl+K)
│   │   ├── 16-scratch.css      # Scratch buffer / daily journal
│   │   └── zz-accessibility.css # A11y panel, contrast, motion (loads last)
│   └── js/                     # Modular JS (core/ → features/ → webgl/ → screensaver/)
│       ├── core/               # Foundation (load first, order matters)
│       │   ├── 00-core.js      # IIFE open, bridge, preferences, toasts
│       │   ├── 01-router.js    # SPA router, fragment fetch, history, lifecycle
│       │   ├── navigation.js   # Search, menus, code copy, scroll-to-top
│       │   ├── toc.js          # Floating table of contents
│       │   └── theme.js        # Accent color, palette modes, hover effects
│       ├── features/           # Self-contained features (order-independent)
│       │   ├── actions-drawer.js # Footer actions drawer
│       │   ├── command-palette.js # Command palette (Ctrl+K)
│       │   ├── content.js      # Filters, section copy, zoom, width toggle
│       │   ├── drop-import.js  # Drag-and-drop .md import
│       │   ├── editor.js       # Inline markdown editor
│       │   ├── effects.js      # Glitch, clock, cursor companion
│       │   ├── ideas-dismiss.js # Idea dismiss buttons
│       │   ├── live-reload.js  # Auto-reload on build
│       │   ├── pins.js         # Pinboard pin management
│       │   ├── scratch.js      # Scratch buffer / daily journal
│       │   ├── shortcuts.js    # Keyboard shortcuts overlay
│       │   ├── splash.js       # Initial load splash screen
│       │   ├── tabs.js         # Tabbed document interface
│       │   ├── writeback.js    # Task/status write-back (desktop app)
│       │   └── zz-accessibility.js  # A11y panel + IIFE close (must be last)
│       ├── webgl/              # WebGL2 integration layer
│       │   └── 00-hypergl.js   # HyperGL runtime for GPU shader effects
│       └── screensaver/        # Screensaver engine + modes
│           ├── 00-engine-head.js    # Engine open, helpers, overlay
│           ├── particles.js    # Mode: SPH fluid particles (CPU)
│           ├── starfield.js    # Mode: Starfield fly-through
│           ├── worm.js         # Mode: Wandering worm trails
│           ├── dither.js       # Mode: Bayer-dithered gradients (CPU)
│           ├── bounce.js       # Mode: Bouncing text (DVD-style)
│           ├── life.js         # Mode: Conway's Game of Life
│           ├── grid.js         # Mode: Infinite perspective grid
│           ├── gl-dither.js    # Mode: GPU Bayer dither (WebGL2)
│           ├── gl-noise.js     # Mode: GPU FBM noise (WebGL2)
│           ├── gl-particles.js # Mode: GPU fluid particles (WebGL2)
│           └── zz-engine-tail.js    # Engine tail: API, idle timer
├── docs/                       # Hypervisor documentation
│   ├── README.md               # This file
│   ├── SETUP.md                # Setup guide for new workspaces
│   ├── architecture.md         # Build pipeline, modules, asset pipeline, navigation
│   ├── design.md               # Visual style, color system, palette modes
│   ├── configuration.md        # Dependencies, config constants, extending
│   ├── mcp-server.md           # MCP server: tools, architecture, configuration
│   └── technical-reference.md
└── site/                       # Generated output (not version-controlled)
```

## See Also

- `architecture.md` — how the build works, module responsibilities, post-processing pipeline, navigation model
- `design.md` — brutalist terminal aesthetic, color system, palette harmony modes, component polish
- `configuration.md` — dependencies, CDN resources, config constants, extending hypervisor
- `mcp-server.md` — MCP server tools, architecture, package structure, configuration