# Architecture Overview

How Hypervisor is structured — the big picture of how files become a browsable site.

---

## What Hypervisor Does

Hypervisor is a **static site generator**. It takes a folder full of markdown files (`.hyperspace/`) and converts them into a browsable HTML website (`site/`). That's it at the highest level.

```
Input:  .hyperspace/**/*.md  (your markdown documents)
Output: .hypervisor/site/    (browsable HTML pages)
```

Every time you run `python build.py`, the entire site is regenerated from scratch. The `site/` folder is ephemeral — it can be deleted and rebuilt at any time.

## Project Layout

```
.hypervisor/
├── build.py              ← Entry point. Run this to generate the site.
├── hypervisor-app.py     ← Desktop app entry point (PyWebView wrapper)
├── mcp-server.py         ← MCP server entry point (AI tool interface)
├── watcher.py            ← File watcher for live rebuilds
├── site_utils/           ← Python modules that do the actual work
│   ├── config.py         ← Paths, constants, markdown engine setup
│   ├── file_utils.py     ← File discovery, path helpers, date extraction
│   ├── markdown_processing.py  ← Markdown → HTML + post-processing
│   ├── page_generation.py      ← HTML templates, topbar, breadcrumbs
│   ├── directory_index.py      ← Auto-generated index pages
│   ├── search.py               ← Search index builder
│   └── backlinks.py            ← Reverse-link tracking
├── hv_mcp/               ← MCP server package (convention-as-code tools)
│   ├── config.py         ← Registries, paths, status transitions
│   ├── index.py          ← In-memory document index + file watcher
│   ├── crud.py           ← create/update/move document operations
│   ├── templates.py      ← Document template generators
│   ├── validation.py     ← Convention enforcement engine
│   ├── analytics.py      ← Health report, stale docs, tag analytics
│   ├── intelligence.py   ← Session brief, next-action suggestions
│   └── generation.py     ← Tag suggestion, duplicate detection
├── assets/               ← CSS and JS source files
│   ├── css/              ← Modular CSS (concatenated during build)
│   └── js/               ← Modular JS (concatenated during build)
├── learn/                ← These files (you're reading one now)
└── site/                 ← Generated output (don't edit directly)
```

## The Build Pipeline

When you run `python build.py`, here's what happens in order:

### 1. Scan

`collect_files()` walks the `.hyperspace/` directory tree and finds every `.md` file. It skips certain directories (`__pycache__`, `site`, `learn`) and returns a sorted list of relative paths.

**Key concept:** The file's path relative to `.hyperspace/` determines its URL in the generated site. `context/cms-architecture.md` becomes `site/context/cms-architecture/index.html`.

### 2. Index

Two indexes are built from the collected files:

- **Search index** — extracts title, path, tags, snippet, and date from each document. Embedded as JSON in every page for client-side search.
- **Backlink index** — scans each document for links to other `.md` files and builds a reverse map ("who links to this document?").

### 3. Prepare Output

The `site/` directory is deleted and recreated fresh. Then CSS and JS assets are concatenated and copied in.

### 4. Render Pages

Each markdown file is processed through this chain:

```
.md file → markdown library → raw HTML → post-processing transforms → final HTML
```

The post-processing step is where the magic happens — it adds section wrappers, code block labels, task list styling, metadata bars, and more. (Covered in detail in [Post-Processing](../05-post-processing/index.html).)

### 5. Generate Indexes

For every directory that contains documents, an index page is auto-generated. These show subcategory cards and a date-sorted list of documents in that directory.

### 6. Generate Homepage

The homepage is built last. It shows:
- A hero band (ASCII logo + flag-style tagline)
- A KPI strip (docs, pages, indexes, active count, build timestamp)
- The **Workspace Pulse** panel — active work items with WI-ID pills, task-progress bars, days-in-progress, plus a day-grouped stream of the 10 most recently updated documents
- The **Pinned** panel — client-side rendered from localStorage on page load
- Root-level documents (any `.md` files directly in `.hyperspace/`)

## Three Entry Points

Hypervisor can run in three modes:

### CLI Mode (`build.py`)

One-shot full build. Generates the site and opens it in a browser tab. Good for quick checks.

### Desktop App Mode (`hypervisor-app.py`)

Launches a native window via [PyWebView](https://pywebview.flowrl.com/) that wraps the generated site. Adds:

- **Live file watching** — edits to `.md` files trigger incremental rebuilds
- **Write-back** — clicking checkboxes or changing metadata in the UI writes changes back to the source `.md` file
- **Preferences** — accent color, reading width, etc. persist across sessions

Both modes use the exact same build functions from `site_utils/`.

### MCP Server Mode (`mcp-server.py`)

A long-running process that exposes hyperspace operations to AI assistants via Model Context Protocol. Adds:

- **Convention enforcement** — tag validation, status transitions, template compliance
- **In-memory index** — instant search and analytics without disk I/O
- **Automated write-back** — creates/updates documents with structural guarantees
- **Health monitoring** — validation snapshots, trend tracking, template drift detection

The MCP server uses `site_utils/` for shared utilities (file discovery, date extraction) but has its own package (`hv_mcp/`) for tool logic. It also triggers `build.py` site rebuilds after write operations.

See [The MCP Server](../10-mcp-server/index.html) for the full walkthrough.

## Key Design Decisions

### Why static generation?

The site runs from `file://` protocol (no web server needed in CLI mode). This means:
- No server to install or configure
- Works offline
- Opens instantly
- Can be hosted anywhere (S3, GitHub Pages, local folder)

### Why regenerate everything?

A full rebuild of ~130 documents takes under 2 seconds. At this scale, incremental builds add complexity without meaningful speed gains. The desktop app does use incremental rebuilds for responsiveness during editing, but a full rebuild is always the fallback.

### Why no framework?

No React, no Vue, no build tools. The frontend is vanilla HTML + CSS + JS. This keeps the project:
- Zero-dependency on the frontend
- Instantly understandable (view source = what you see)
- Fast to load (no hydration, no virtual DOM)

## Reference Links

- [Python `pathlib`](https://docs.python.org/3/library/pathlib.html) — used throughout for file path manipulation
- [Python `markdown` library](https://python-markdown.github.io/) — the markdown-to-HTML engine
- [PyWebView documentation](https://pywebview.flowrl.com/) — the desktop wrapper library
- [Static site generators (concept)](https://www.cloudflare.com/learning/performance/static-site-generator/) — general background on the pattern

## Next

→ [The Build Script](../02-build-script/index.html) — a line-by-line walkthrough of `build.py`
