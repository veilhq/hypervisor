<p align="center">
  <img src="assets/HYPERVISOR-LOGO-i2.png" alt="Hypervisor" width="200">
</p>

<h1 align="center">Hypervisor</h1>

<p align="center">
  A local-only static site generator that turns a folder of markdown into a browsable knowledge base.
</p>

---

## What It Does

Point Hypervisor at a directory of `.md` files and it produces a self-contained HTML site with:

- **Hub-and-spoke navigation** — site nav rail → category indexes → document pages (homepage is a status dashboard)
- **Full-text search** — instant fuzzy search across all documents with tag filtering
- **Live file watching** — edit markdown in your editor, site rebuilds and refreshes automatically
- **Checkbox write-back** — click a task checkbox in the rendered view to toggle it in the source file
- **Backlink graph** — automatic reverse-link tracking between documents
- **Pinboard** — pin frequently-accessed documents for quick access
- **Screensaver engine** — idle-activated canvas animations (particles, starfield, Game of Life, and more)
- **Command palette** — keyboard-driven navigation (Ctrl+K)
- **Tabbed browsing** — open multiple documents in tabs within the app

## Design Philosophy

- **Zero frameworks** — Python + vanilla CSS + vanilla JS. No React, no Node, no bundler.
- **Brutalist terminal aesthetic** — pure black background, monospace everywhere, hard edges, no border-radius.
- **Content-agnostic** — Hypervisor doesn't care what your markdown is about. It renders whatever it finds.
- **Local-only** — no server, no cloud, no accounts. Your files stay on your machine.

## Quick Start

### Static Site (browser)

```bash
pip install markdown pygments
cd .hypervisor
python build.py
```

Opens the generated site in your default browser.

### Desktop App (recommended)

```bash
pip install -r requirements-app.txt
cd .hypervisor
python hypervisor-app.py
```

Launches a native desktop window (PyWebView) with live reload, write-back, and all interactive features.

## Installation

**Requirements:** Python 3.10+

**Core (build only):**
```
markdown
pygments
```

**Desktop app:**
```
pywebview>=5.0
watchdog>=4.0
```

**Optional — MCP server (AI integration):**
```
mcp>=1.0
rapidfuzz>=3.0
```

## How It Works

Hypervisor expects to live one level inside your content directory:

```
your-knowledge-base/        ← content root (any folder of .md files)
├── .hypervisor/            ← this repo
│   ├── build.py
│   ├── hypervisor-app.py
│   ├── assets/
│   ├── site_utils/
│   └── site/              ← generated output (gitignored)
├── context/
├── research/
├── work/
├── ideas/
└── (any markdown files or subdirectories)
```

Content root is resolved automatically — no configuration file needed. Whatever directory `.hypervisor/` sits inside becomes the content root.

## Features

### Build Pipeline

- Markdown → HTML with syntax highlighting (Pygments)
- Auto-generated directory indexes with file metadata
- Post-processing: section panels, code block labels, task list styling, Mermaid diagram support
- Incremental builds — only rebuilds changed files
- Search index generation (JSON, loaded client-side)

### Desktop App

- Native window via PyWebView (Edge/WebView2 on Windows, WebKit on macOS/Linux)
- File watcher with debounced auto-rebuild
- Checkbox write-back (toggle tasks directly in rendered view → updates source `.md`)
- Status metadata write-back (click to cycle status fields)
- Scroll position preservation across rebuilds
- Single-instance enforcement

### Visual

- Configurable accent color with real-time palette generation (complementary, triadic, square, analogous)
- Staggered card animations, hover effects, glass blur topbar
- Floating table of contents with active heading tracking
- Accessibility panel (high contrast, reduced motion, font size, hide indicators)

### Optional: MCP Server

If you use an AI assistant that supports MCP (Model Context Protocol), Hypervisor includes a full MCP server with 21 tools for document CRUD, validation, search, analytics, and intelligent suggestions. This is entirely optional — the site generator and desktop app work without it.

## Development

Edit source files, never generated output:

- **CSS** → `assets/css/` (numbered modules, concatenated in order)
- **JS** → `assets/js/` (subdirectories: `core/` → `features/` → `screensaver/`)
- **Python** → `build.py`, `site_utils/`, `hypervisor-app.py`

After changes, run `python build.py` or let the desktop app's file watcher handle it.

## License

Personal project. Not currently licensed for distribution.
