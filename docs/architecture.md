# HV-ARCHITECTURE

How the Hypervisor build pipeline works — from markdown source to browsable static site.

- Created: 2026-04-22T00:00
- Updated: 2026-07-14T09:43

## Project Structure

```
.hypervisor/
├── build.py                    # CLI entry point — orchestrator, full build, single-file rebuild
├── hypervisor-app.py           # Desktop app entry point — PyWebView + file watcher
├── mcp-server.py              # MCP server entry point — AI tool integration (Kiro)
├── hv_mcp/                    # MCP server logic package
│   ├── __init__.py            # Package docstring
│   ├── config.py              # Paths, constants, registries (config/tags.json, config/projects.json)
│   ├── index.py               # In-memory index: build, refresh, remove, file watcher
│   ├── index_file.py          # _index.md regeneration
│   ├── backlinks.py           # Backlink graph (eager build, incremental updates)
│   ├── dates.py               # Date parsing utilities
│   ├── health.py              # Health history snapshot storage
│   ├── helpers.py             # Slug generation, validation helpers, backlink rewriting
│   ├── templates.py           # Document template generators
│   ├── validation.py          # Single-file and batch validation
│   ├── crud.py                # create_document, update_document, move_work_item
│   ├── search.py              # search_hyperspace, recent_activity, get_work_items
│   ├── tags.py                # get_tags, add_tag
│   ├── analytics.py           # stale_documents, health_report, tag_analytics
│   ├── intelligence.py        # session_brief, suggest_next_action, context_for_work_item
│   ├── migration.py           # migrate_document, get_schema_changelog
│   ├── generation.py          # suggest_tags, similar_documents, outline_work_item
│   ├── template_drift.py     # Template drift detection (markdown vs programmatic templates)
│   └── launcher.py            # launch_hypervisor desktop app subprocess management
├── watcher.py                  # File watcher (watchdog) for live rebuild on .md changes
├── config/                     # Portable configuration (tracked in git)
│   ├── tags.json              # Canonical tag registry (MCP server)
│   └── projects.json          # Valid project names (MCP server)
├── state/                      # Content-specific state (gitignored)
│   ├── work-item-counter.json # Sequential work item ID counter
│   └── health-history.json    # Health snapshots (MCP server)
├── preferences.json            # User preferences persisted by the desktop app (gitignored)
├── requirements-app.txt        # Extra deps for the desktop app (pywebview, watchdog)
├── site_utils/                 # Build modules package
│   ├── __init__.py             # Re-exports all public symbols
│   ├── config.py               # Paths, constants, MD engine, category metadata
│   ├── file_utils.py           # File collection, path helpers, naming, date extraction
│   ├── markdown_processing.py  # Markdown rendering + all post-processing transforms
│   ├── page_generation.py      # HTML templates, breadcrumbs, topbar, shell builder, page builder
│   ├── page_builders.py        # Homepage, pinboard, 404, utility pages, learn section (all as fragments)
│   ├── fragment.py             # Content fragment JSON schema, serialization, mermaid detection
│   ├── directory_index.py      # Dir tree helpers, home page, subdirectory index generators
│   ├── search.py               # Search index builder
│   ├── build_cache.py          # Content hash caching for incremental builds
│   ├── backlinks.py            # Reverse-link index from .md cross-references
│   ├── ideas.py                # Idea operations (delete/dismiss implemented ideas)
│   ├── external_files.py       # .external/ import and delete operations
│   └── work_items.py           # Work item operations (mark done, move files)
├── assets/                     # Static assets — source of truth for site styling & behavior
│   ├── css/                    # Modular CSS (numbered sorted, zz-* last → site/style.css)
│   │   ├── 00-variables.css    # CSS custom properties, resets, component base classes
│   │   ├── 01-layout.css       # Topbar, page, footer, breadcrumbs, scroll-to-top
│   │   ├── 02-search.css       # Search input, results dropdown, tag filtering, work item filters
│   │   ├── 03-menus.css        # Reference menu, utilities menu, width toggle, accent picker
│   │   ├── 04-content.css      # Markdown body, code blocks, tables, blockquotes
│   │   ├── 05-cards.css        # Card grid, doc lists, build stats, homepage dock
│   │   ├── 06-pinboard.css     # Pin cards, pin button, pinboard page, pin type badges
│   │   ├── 07-toc.css          # Floating table of contents sidebar
│   │   ├── 08-utilities.css    # Password generator and other utility page styles
│   │   ├── 09-effects.css      # Cursor companion, glitch effect, keyboard shortcuts
│   │   ├── 10-splash.css       # Loading splash screen styles
│   │   ├── 11-tabs.css         # Tabbed document interface styles
│   │   ├── 12-drop-import.css  # Drag-and-drop .md file import zone
│   │   ├── 13-ideas-dismiss.css # Idea dismiss button styles
│   │   ├── 14-editor.css       # Inline markdown editor styles
│   │   ├── 15-command-palette.css # Command palette (Ctrl+K) overlay
│   │   ├── 16-scratch.css      # Scratch buffer / daily journal panel
│   │   └── zz-accessibility.css # A11y panel, high contrast, reduced motion (loads last)
│   └── js/                     # Modular JS (core/ → features/ → webgl/ → screensaver/ → site/app.js)
│       ├── core/               # Foundation modules (load first, order matters)
│       │   ├── 00-core.js      # IIFE open, PyWebView bridge, preferences, toasts, shared DOM refs
│       │   ├── 01-router.js    # SPA router: fragment fetch, content swap, history, lifecycle hooks
│       │   ├── navigation.js   # Search, topbar scroll, ref menu, util menu, code copy, scroll-to-top
│       │   ├── toc.js          # Floating TOC sidebar, active heading tracking (lifecycle-aware)
│       │   └── theme.js        # Accent color picker, palette modes, brand/title hover
│       ├── features/           # Self-contained feature modules (order-independent, zz-* last)
│       │   ├── actions-drawer.js # Footer actions drawer toggle
│       │   ├── command-palette.js # Unified command palette (Ctrl+K) — docs, actions, utilities
│       │   ├── content.js      # Todo filters, section copy, table copy, zoom, width toggle (lifecycle-aware)
│       │   ├── drop-import.js  # Drag-and-drop .md import on .external page (lifecycle-aware)
│       │   ├── editor.js       # Inline markdown editor (lifecycle-aware)
│       │   ├── effects.js      # Terminal glitch, footer clock, cursor companion
│       │   ├── ideas-dismiss.js # Dismiss/delete buttons on ideas/ index (lifecycle-aware)
│       │   ├── live-reload.js  # Build-change polling / fragment re-fetch
│       │   ├── pins.js         # Pinboard: pin CRUD, card rendering, navigation (lifecycle-aware)
│       │   ├── scratch.js      # Scratch buffer / daily journal (backtick hotkey, auto-save)
│       │   ├── shortcuts.js    # Keyboard shortcuts overlay
│       │   ├── splash.js       # Initial load splash screen
│       │   ├── tabs.js         # Tabbed document interface (multi-doc browsing)
│       │   ├── writeback.js    # Task checkbox + status write-back, explorer, mark done (lifecycle-aware)
│       │   └── zz-accessibility.js  # Accessibility panel + IIFE close (must be last)
│       ├── webgl/              # WebGL2 integration layer (loads after features, before screensaver)
│       │   └── 00-hypergl.js   # HyperGL — zero-dep WebGL2 runtime for GPU shader effects
│       └── screensaver/        # Screensaver engine + modes (00-* first, zz-* last)
│           ├── 00-engine-head.js    # Engine IIFE open, shared helpers, DOM overlay, state
│           ├── particles.js    # Mode: SPH fluid particles with mouse interaction
│           ├── starfield.js    # Mode: Starfield fly-through
│           ├── worm.js         # Mode: Wandering worm trails
│           ├── dither.js       # Mode: Bayer-dithered morphing gradients (CPU)
│           ├── bounce.js       # Mode: Bouncing text (DVD-style)
│           ├── life.js         # Mode: Conway's Game of Life
│           ├── grid.js         # Mode: Infinite perspective grid
│           ├── gl-dither.js    # Mode: GPU Bayer dither (WebGL2 via HyperGL)
│           ├── gl-noise.js     # Mode: GPU FBM noise (WebGL2 via HyperGL)
│           ├── gl-particles.js # Mode: GPU fluid particles (50k, transform feedback)
│           └── zz-engine-tail.js    # Engine tail: public API, activate/dismiss, idle timer
├── docs/                       # Hypervisor's own documentation (this file lives here)
│   ├── README.md
│   ├── SETUP.md
│   ├── architecture.md
│   ├── configuration.md
│   ├── design.md
│   ├── mcp-server.md
│   └── technical-reference.md
└── site/                       # Generated output (ephemeral, not version-controlled)
```

## How the Build Works

Hypervisor has three entry points. Two generate the static site; one exposes hyperspace as AI-accessible tools.

### Entry Point 1: Static Site (`build.py`)

Run `python build.py` from the command line. Performs a one-shot full build, writes all output to `site/`, and prints a summary. The output is a **SPA (Single Page Application) shell** — one HTML file plus JSON content fragments that are loaded dynamically by the client-side router.

**Build output:**
```
site/
├── index.html              # The SPA shell (single HTML entry point)
├── content/                # Content fragments (JSON, one per document/index)
│   ├── home.json           # Homepage fragment
│   ├── 404.json            # Not-found page fragment
│   ├── _pins.json          # Pinboard fragment
│   ├── work.json           # Directory index fragment
│   ├── work/done.json      # Sub-directory index fragment
│   ├── work/done/my-item.json  # Document fragment
│   ├── _utils/password-gen.json # Utility page fragment
│   ├── learn.json          # Learn section index
│   └── learn/my-topic.json # Learn page fragment
├── search-index.json       # Search data (loaded once at startup)
├── nav-state.json          # Nav rail state (categories, recent indicators)
├── _build.json             # Build ID for live-reload detection
├── style.css               # Concatenated CSS
├── app.js                  # Concatenated JS (includes SPA router)
├── _utils/                 # Companion assets for utility pages
└── prototypes/             # Raw HTML prototypes (standalone, outside SPA)
```

### Entry Point 2: Desktop App (`hypervisor-app.py`)

Run `python hypervisor-app.py` to launch a native OS window (via PyWebView) that wraps the generated site via an internal HTTP server. The desktop app adds:

- **Live file watching** — `watcher.py` uses watchdog to monitor `.hyperspace/**/*.md` for changes. On save, it triggers `build_single_file()` for incremental rebuilds (single doc fragment + parent index fragments + homepage fragment) instead of a full rebuild.
- **Fragment-based live reload** — on file change, the Python process calls `window.__hypervisorReload()` which re-fetches the current page's JSON fragment via the SPA router, swapping content without a full page reload. Scroll position is preserved naturally.
- **SPA fallback routing** — the Bottle HTTP server serves `index.html` for any path that doesn't match a real file on disk, enabling deep-linking and back/forward navigation.
- **Checkbox write-back** — clicking a task checkbox in the rendered HTML writes the toggle back to the source `.md` file via the `HypervisorAPI.toggle_checkbox` JS bridge.
- **Metadata write-back** — status changes made in the UI are written back to the source `.md` file via `HypervisorAPI.update_metadata`.
- **Ignore-path grace** — when the app writes to a `.md` file programmatically, it tells the watcher to ignore events for that path for 2 seconds, preventing a feedback loop.
- **Preferences** — user settings (accent color, palette mode, reading width) are persisted to `preferences.json` so they survive app restarts.

Both entry points call the same functions from `site_utils/` and `build.py`:

| Function | CLI (`build.py`) | Desktop App (`hypervisor-app.py`) |
|----------|------------------|-----------------------------------|
| `full_build()` | Called once on run | Called once on startup, and on file deletions |
| `build_single_file()` | Not used | Called by watcher on `.md` edits/creates |
| `build_shell()` | Part of `full_build` | Only on full build (shell is stable between incremental rebuilds) |
| `copy_assets()` | Part of `full_build` | Also called in `build_single_file` to keep CSS/JS current |
| `compute_recent_paths()` | Part of `full_build` and `build_indexes` | Also called in `build_single_file` for homepage refresh |

### Entry Point 3: MCP Server (`mcp-server.py`)

Run via Kiro's MCP configuration (stdio transport). The MCP server does not generate the static site — it exposes hyperspace documents as structured tools for AI assistants. It maintains its own in-memory index and backlink graph, independent of the build pipeline.

The server:
- Builds a full in-memory index of all hyperspace documents at startup
- Starts a watchdog file watcher to keep the index current
- Registers 19 tools covering search, CRUD, validation, analytics, smart context, migration, and content generation
- Enforces all hyperspace conventions (tag validation, status transitions, template compliance) at the tool level

The MCP server shares `site_utils/` for file discovery and date extraction, but does not depend on `build.py` or the generated `site/` directory. Full documentation in `docs/mcp-server.md`.

## Process Coordination

Hypervisor has three entry points that can run concurrently. Two of them (the desktop app and the MCP server) watch the same directory for file changes. Without coordination, they cause race conditions — duplicate builds, file-locking errors on Windows, and stale UI state.

### The Problem: Two Watchers, One Directory

| Process | Watcher | Purpose | Debouncing | Ignore mechanism |
|---------|---------|---------|------------|-----------------|
| Desktop app (`hypervisor-app.py`) | `watcher.py` → `FileWatcher` | Triggers incremental/full site rebuilds | Yes (300ms) | Yes (content hashing + grace periods) |
| MCP server (`mcp-server.py`) | `hv_mcp/index.py` → `_HyperspaceHandler` | Keeps in-memory index current | Minimal (100ms delay) | No |

When both processes run simultaneously (Kiro's MCP server + the desktop app open), a file write triggers both watchers. If the MCP server also fires `trigger_site_build()`, you get two concurrent full builds writing to `site/` — which causes Windows file-locking errors (PermissionError) and inconsistent output.

### The Solution: Ownership Model

**Rule: The desktop app owns site builds. The MCP server owns data operations.**

| Responsibility | Desktop App | MCP Server |
|----------------|-------------|------------|
| Site generation (HTML, CSS, JS) | ✓ Exclusive | ✗ Defers |
| File watching for site rebuilds | ✓ | ✗ |
| In-memory index maintenance | ✗ | ✓ |
| `_index.md` regeneration | Via MCP import | ✓ |
| Convention enforcement | ✗ | ✓ |
| Write-back (checkbox, status) | ✓ | ✗ |

### How It Works

1. **Lock file** — The desktop app creates `.hypervisor/.app_running` on startup (containing its PID) and deletes it on shutdown.

2. **MCP defers builds** — `trigger_site_build()` in `hv_mcp/helpers.py` checks for `.app_running`. If present, it returns immediately — the desktop app's watcher will detect the file change and rebuild on its own schedule with proper debouncing.

3. **MCP watcher is read-only** — The MCP server's watcher in `hv_mcp/index.py` only updates the in-memory index and backlink graph. It never writes files or triggers builds.

4. **Desktop calls MCP's index logic** — When the desktop app moves a work item (`mark_done`), it imports `hv_mcp.index.rebuild_index` and `hv_mcp.index_file.regenerate_index_file` directly. This keeps `_index.md` in sync without a separate MCP server process.

5. **Desktop suppresses before writing** — The desktop app calls `watcher.ignore_path()` on both source and destination paths *before* any file operation, preventing its own watcher from racing the operation.

### When Only the MCP Server Runs

If the desktop app is not open (`.app_running` doesn't exist), the MCP server handles everything autonomously:
- Write operations trigger `trigger_site_build()` → full rebuild in a background thread
- The MCP watcher keeps the index current
- No coordination needed (single process)

### When Only the Desktop App Runs

If Kiro's MCP server is not active, the desktop app handles everything via its own watcher and write-back bridge. No coordination needed.

### Shared Build Pipeline

`build.py` exports `full_build()` and `build_single_file()` as importable functions. The orchestration does four things:

1. **SPA Shell** — A single `site/index.html` containing the topbar, nav rail, TOC sidebar (empty container), main content area (empty), footer, and all scripts. Generated once per full build. Content is loaded dynamically by the client-side router.

2. **Content fragments** — Each `.md` document becomes a JSON fragment at `site/content/<path>.json`. The fragment contains: `title`, `html` (rendered article body + backlinks), `toc` (table of contents HTML), `breadcrumbs` (path parts array), `sourcePath`, `hasMermaid` (boolean), and `pageType` (doc/index/home/utility/learn/pinboard). The router fetches these on navigation and swaps the shell's content area.

3. **Directory indexes** — Auto-generated fragment for every directory that contains documents. Shows sub-category cards and a date-sorted document listing. These don't correspond to any `.md` source document. (logic in `directory_index`)

4. **Homepage** — `site/content/home.json` is a fragment with category cards, recent activity, and build statistics. (logic in `directory_index.generate_home_content`)

## Asset Pipeline

### CSS: Modular Concatenation

CSS lives in `assets/css/` as numbered modules. During build, `build.py` globs numbered files in **sorted order**, then appends `zz-*` files last. All are concatenated into a single `site/style.css`. The numeric prefixes (`00-`, `01-`, ...) control load order; `zz-` ensures accessibility overrides always come last.

**This is the active CSS pipeline.** When adding or modifying styles, always edit the appropriate module in `assets/css/`.

| Module | Scope |
|--------|-------|
| `00-variables.css` | `:root` custom properties, resets, body cursor rules, tooltip base, component base classes |
| `01-layout.css` | Topbar, `.page` layout, footer, breadcrumbs, scroll-to-top, Lucide icon sizes, condensed reading width |
| `02-search.css` | Search input, results dropdown, tag filter indicator, result snippets/tags, work item filters |
| `03-menus.css` | Reference dropdown, utilities dropdown, width toggle button, accent picker + palette preview |
| `04-content.css` | `.markdown-body` typography, code blocks, tables, blockquotes, metadata bar, section panels, backlinks, related sections |
| `05-cards.css` | Card grid, card animations, doc lists, build stats, homepage dock, empty messages |
| `06-pinboard.css` | Pin cards, pin button (footer), pinboard page, pin type badges, dock item |
| `07-toc.css` | Floating TOC sidebar, active heading tracking, responsive hide |
| `08-utilities.css` | Shared utility page container, 404 not-found page |
| `utilities/password-gen.css` | Password generator layout, output display, history panel |
| `utilities/quiz.css` | AWS CCP practice quiz — layout, cards, options, sidebar, study guide |
| `utilities/regex-editor.css` | Regex editor — pattern input, flags, test strings, match highlights, reference |
| `utilities/screensaver-settings.css` | Screensaver utility — mode cards, preview canvas, settings |
| `utilities/health-dashboard.css` | Health dashboard — cards, charts, status indicators, grids |
| `utilities/palette-gen.css` | Palette generator — preset grid, swatch editor, live preview |
| `09-effects.css` | Cursor companion box, section copy buttons, table cell copy, keyboard shortcuts overlay |
| `10-splash.css` | Loading splash screen overlay, scrollbar suppression during splash |
| `11-tabs.css` | Tab bar, tab items, sliding highlight, tab overflow |
| `12-drop-import.css` | Drag-and-drop file import zone for .external page |
| `13-ideas-dismiss.css` | Idea dismiss/delete button overlay on list items |
| `14-editor.css` | Inline markdown editor panel, toolbar, textarea |
| `15-command-palette.css` | Command palette modal, search input, result items, categories |
| `16-scratch.css` | Scratch buffer slide-in panel, journal entries, history view |
| `zz-accessibility.css` | A11y panel UI, high contrast mode, large text, reduced motion, font smoothing, focus indicators, system cursors |

### JS: Subdirectory Concatenation

JS lives in `assets/js/` organized into four subdirectories. During build, `build.py` concatenates them in this order: `core/` → `features/` → `webgl/` → `screensaver/`. Within each directory, files sort alphabetically with `zz-*` files loading last. All modules share a single IIFE closure — `core/00-core.js` opens it (`(function() { "use strict";`) and `features/zz-accessibility.js` closes it (`})();`). Variables declared in any module are accessible to all subsequent modules.

**Always edit the appropriate module in `assets/js/`.** Never edit the generated `site/app.js` directly.

**`core/`** — Foundation modules (load first, order matters):

| Module | Scope |
|--------|-------|
| `00-core.js` | IIFE open, PyWebView bridge, `savePreference`, preferences, toasts, Lucide init, cursor activation, shared DOM refs |
| `01-router.js` | SPA router: fragment fetch, content swap, history management, breadcrumbs, TOC, nav state, lazy Mermaid, `onNavigate` lifecycle API |
| `navigation.js` | Topbar scroll shadow, search, ref menu, util menu, code block copy, scroll-to-top, nav rail active state |
| `toc.js` | Floating TOC sidebar, active heading tracking (lifecycle-aware — reinits on navigation) |
| `theme.js` | Accent color picker, hex/rgb/hsl converters, palette modes, `applyAccent`, brand/title hover effects |

**`features/`** — Self-contained feature modules (order-independent, `zz-*` loads last):

| Module | Scope |
|--------|-------|
| `actions-drawer.js` | Footer actions drawer toggle (shell-level, persists) |
| `command-palette.js` | Unified command palette (Ctrl+K) — fuzzy search across docs, actions, utilities, tags |
| `content.js` | Todo filters, section copy (HTML→markdown), table cell copy, zoom controls, width toggle (lifecycle-aware) |
| `drop-import.js` | Drag-and-drop .md import on .external page (lifecycle-aware) |
| `editor.js` | Inline markdown editor with read/write bridge (lifecycle-aware) |
| `effects.js` | Terminal glitch effect, footer clock, cursor companion box |
| `ideas-dismiss.js` | Dismiss/delete buttons on ideas/ directory page (lifecycle-aware, requires bridge) |
| `live-reload.js` | Build-change polling, fragment re-fetch via router |
| `pins.js` | Pinboard: pin CRUD, card rendering, per-page pin button (lifecycle-aware) |
| `scratch.js` | Scratch buffer / daily journal — backtick hotkey, auto-save, history browsing (requires bridge) |
| `shortcuts.js` | Keyboard shortcuts overlay |
| `splash.js` | Initial load splash screen (once per session) |
| `tabs.js` | Tabbed document interface — multi-doc browsing with localStorage persistence |
| `writeback.js` | Task checkbox + status write-back (event delegation), explorer button, mark done (lifecycle-aware) |
| `zz-accessibility.js` | Accessibility panel + IIFE close (must be last globally) |

**`webgl/`** — WebGL2 integration layer (loads after features, before screensaver):

| Module | Scope |
|--------|-------|
| `00-hypergl.js` | HyperGL — zero-dependency WebGL2 runtime: shader compilation, program linking, uniform management, fullscreen triangle, resize handling. Used by `gl-*` screensaver modes. |

**`screensaver/`** — Screensaver engine and modes (`00-*` first, `zz-*` last):

| Module | Scope |
|--------|-------|
| `00-engine-head.js` | Screensaver IIFE open, shared helpers, DOM overlay, state variables |
| `particles.js` | Mode: SPH fluid particles with mouse interaction (CPU) |
| `starfield.js` | Mode: Starfield fly-through |
| `worm.js` | Mode: Wandering worm trails |
| `dither.js` | Mode: Bayer-dithered morphing gradients (CPU) |
| `bounce.js` | Mode: Bouncing text (DVD-style) |
| `life.js` | Mode: Conway's Game of Life |
| `grid.js` | Mode: Infinite perspective grid with mouse-tilt |
| `gl-dither.js` | Mode: GPU Bayer 8×8 ordered dither with selectable patterns (WebGL2 via HyperGL) |
| `gl-noise.js` | Mode: GPU animated FBM noise colored by accent palette (WebGL2 via HyperGL) |
| `gl-particles.js` | Mode: GPU fluid particles — 50k particles via transform feedback (WebGL2 via HyperGL) |
| `zz-engine-tail.js` | Screensaver engine tail: public API, activate/dismiss, idle timer, events |

### Adding New Styles

1. Identify which module owns the feature area (see CSS table above)
2. Add styles to that module
3. If a new module is needed, create it with the next available number prefix (e.g. `10-newfeature.css`)
4. Run `python build.py` to regenerate

### Adding New JS Behavior

1. Identify which subdirectory and module owns the feature area
2. Add code to that module — all modules share the same IIFE scope
3. For new features, create a file in `features/` (no number prefix needed)
4. For new screensaver modes, create a file in `screensaver/` (no number prefix needed)
5. For WebGL utilities shared across modes, add to `webgl/`
6. Ensure the IIFE closing `})();` stays in `features/zz-accessibility.js`
7. Run `python build.py` to regenerate

## Module Responsibilities

| Module | What it owns |
|--------|-------------|
| `config.py` | `HYPERSPACE_ROOT`, `OUTPUT_DIR`, `ASSETS_DIR`, `SKIP_DIRS`, `SKIP_FILES`, `MD` engine instance, `CATEGORY_LABELS`, `CATEGORY_DESCRIPTIONS`, `CATEGORY_ICONS` |
| `file_utils.py` | `collect_files`, `html_dir_for`, `href_for`, `nice_name`, `dir_label`, `get_title`, `extract_dates`, `sort_date`, `count_docs_under`, `get_dir_snippet`, `get_dir_tags`, `get_dir_status`, `infer_app_group` |
| `markdown_processing.py` | `render_markdown`, `post_process`, and all seven transforms (see pipeline below) |
| `page_generation.py` | `TOP_BAR`, `PAGE_TEMPLATE`, `SHELL_TEMPLATE` strings, `make_breadcrumbs`, `build_topbar`, `build_page`, `build_shell`, `build_site_nav`, `set_nav_categories` |
| `fragment.py` | `build_fragment`, `write_fragment`, `has_mermaid`, `make_breadcrumb_parts` — content fragment schema and serialization |
| `page_builders.py` | `build_homepage`, `build_404_page`, `build_utility_pages`, `build_learn_pages`, `build_pinboard_page`, `build_raw_html_pages` (all output fragments except raw HTML) |
| `directory_index.py` | `collect_dir_contents`, `collect_all_dirs`, `generate_home_content`, `generate_dir_index_content` |
| `search.py` | `build_search_index` (with snippet extraction, tag extraction, and date enrichment) |
| `build_cache.py` | `BuildCache` — content hash caching for incremental builds, template change detection |
| `backlinks.py` | `build_backlink_index`, `render_backlinks_html` — reverse-link index from .md cross-references |
| `ideas.py` | `delete_idea` — file deletion for dismissed/implemented ideas (called by desktop app bridge) |
| `external_files.py` | `import_external_file`, `has_metadata_header` — .external/ import with metadata injection, collision handling |
| `work_items.py` | `mark_done` — move work item to done/, update status+timestamp, regenerate _index.md (called by desktop app bridge) |

## Post-Processing Pipeline

After markdown-to-HTML conversion, `markdown_processing.post_process` runs seven transforms in order:

| Step | What it does |
|------|-------------|
| `rewrite_md_links` | Converts `href="...something.md"` to `href=".../index.html"` so cross-doc links work |
| `extract_metadata_block` | Pulls `- Date:`, `- Tags:`, `- Related:` etc. from after H1 into a styled key-value bar. Internally calls `linkify_md_paths` to convert `.md` paths in metadata values into clickable links |
| `wrap_h2_sections` | Wraps content between H2 headings in collapsible `<details class="doc-section" open>` panels with summary headers |
| `style_related_section` | Detects H2 sections titled "Related" or "See Also", groups items by category prefix (Model, Component, API, Backend, etc.) under sub-headers, and restructures each item into path + description layout |
| `convert_mermaid_blocks` | Detects mermaid diagram content in generic code blocks and converts to `<pre class="mermaid">` for client-side rendering |
| `label_code_blocks` | Adds language labels to fenced code blocks based on Pygments/codehilite classes |
| `style_task_lists` | Converts `[ ]` / `[x]` checkbox patterns into styled task items |

New transforms that modify link hrefs go after `rewrite_md_links`. New transforms that add wrapper elements go after `wrap_h2_sections`.

## Date Extraction & Sorting

Document listings on directory indexes and the homepage are sorted by date (newest first). `extract_dates` scans the first 30 lines of each markdown document for metadata in these formats:

- `Created: 2026-02-17` or `- Created: 2026-02-17`
- `Date: 2026-02-26`
- `Updated: 2026-02-18` or `Last updated: 2026-04-20`
- `**Last Updated:** February 13, 2026` (long-form month names)

The sort prefers `updated` over `created`. Undated docs sort last.

## Navigation Model

Hub-and-spoke, no sidebar:

```
Homepage (recently updated + category cards + build stats)
  └── Category index (subcategory cards + date-sorted document list)
       └── Doc page (rendered markdown)
```

Every page has:
- **Top bar** — brand link (home), breadcrumbs, search input, accent color picker, palette mode toggle
- **Breadcrumbs** — clickable path segments, e.g. `~ / patterns / django / soft delete`
- **Search** — client-side fuzzy filter over all docs (matches title, path, body snippet, and tags), keyboard navigable (`/` to focus, arrows to select, Enter to go, Esc to close). Results show a content snippet preview and clickable tags for filtering.
- **Tag filtering** — click any tag in search results to filter docs by that tag. Active tag filter shown as an indicator below the search bar. Click × or press Esc to clear.
- **Keyboard shortcuts** — press `?` to toggle a shortcuts overlay showing all keybindings
- **Accent picker** — color input + palette mode button (cycles `SPL → TRI → ANA → SQR → CMP`) with four-swatch preview
- **Width toggle** — switches between full-width and condensed (1280px max-width) reading mode. Persists to `localStorage`. Keyboard shortcut: `w`. In condensed mode with TOC, the page uses flex layout so the TOC sits beside the content without overlapping.
- **Recent activity** — homepage shows the 10 most recently changed docs (by updated or created date) with `new` / `updated` badges for quick access
- **Floating TOC** — doc pages with 3+ headings and sufficient height get a floating table of contents on the right side. Tracks the active heading on scroll. Hidden on narrow screens (<1200px).
- **Backlinks** — "Referenced By" section at the bottom of each doc page showing all other docs that link to it. Built as a reverse-link index during the build step.

## Path Resolution

The site runs inside PyWebView with a Bottle HTTP server. All paths are absolute (e.g., `/content/work/done/my-item.json`, `/style.css`). The SPA shell at `/index.html` is served for any URL that doesn't match a physical file, enabling deep-linking.

**Fragment path mapping:**
- `/work/done/my-item/index.html` → fetches `/content/work/done/my-item.json`
- `/work/index.html` → fetches `/content/work.json`
- `/` or `/index.html` → fetches `/content/home.json`
- `/_pins/index.html` → fetches `/content/_pins.json`
- `/learn/my-topic/index.html` → fetches `/content/learn/my-topic.json`

## Live Reload

The desktop app uses fragment-based live reload — no full page reload needed:

1. File watcher detects a `.md` change and calls `build_single_file(rel_path)`
2. `build_single_file` regenerates the changed document's fragment JSON, affected directory index fragments, the homepage fragment, and `nav-state.json`
3. Python calls `window.__hypervisorReload()` via PyWebView's `evaluate_js`
4. `__hypervisorReload()` calls `router.reload()` which re-fetches the current page's fragment with a cache-busting `?t=` parameter
5. The router applies the new fragment (content swap, TOC update, lifecycle hooks)
6. A toast notification confirms the update

**For full rebuilds** (file deletion, moves): the Python side calls `full_build()` then `__hypervisorReload()`. The shell doesn't change (it's the same HTML); only the fragment content is refreshed.

**For non-desktop usage** (browser polling): `live-reload.js` polls `/_build.json` every 2 seconds. When the build ID changes, it calls `router.reload()`.

## SPA Router Architecture

The client-side router (`assets/js/core/01-router.js`) manages all navigation:

### Navigation Flow

1. Intercepts all internal `<a>` link clicks via a `document` click listener
2. Resolves the target URL to a fragment path
3. Fetches the JSON fragment
4. Runs registered teardown hooks (cleanup old content bindings)
5. Swaps `#content-target` innerHTML with the fragment's `html`
6. Updates document title, breadcrumbs, TOC, nav rail active state, footer source path
7. Pushes browser history state
8. Renders Lucide icons in new content
9. Lazy-loads Mermaid if `hasMermaid` is true
10. Runs registered init hooks (setup new content bindings)
11. Fires a `routeChanged` custom event

### Feature Lifecycle System

Features that bind to content elements must reinitialize on every navigation. The router provides `window.__router.onNavigate(teardown, init)`:

| Feature | Lifecycle | Reason |
|---------|-----------|--------|
| TOC active tracking | teardown + init | Heading element references become stale |
| Todo filters | init only | New DOM elements each navigation |
| Section/table copy | init only | Buttons attached to new content |
| Pin button | teardown + init | Button added/removed per page |
| Drop import | teardown + init | Only activates on .external page |
| Mark Done button | teardown + init | Only on work/to-do/ pages |
| Editor | teardown + init | Tracks current file path |
| Explorer button | init only | Visibility depends on page type |

Features using **event delegation** on `document` (task writeback, status writeback) survive navigation without reinit.

Shell-level features (search, themes, zoom, width, screensaver, accessibility) run once at startup and persist across all navigations.

## Custom 404 Handling

With the SPA architecture, 404 handling is two-layered:

1. **Server-side**: The Bottle server's `asset()` route serves `index.html` for any path that doesn't match a real file (SPA fallback). The `@app.error(404)` handler also returns `index.html`.

2. **Client-side**: When the router fetches a fragment that doesn't exist (HTTP 404 from `/content/...`), it falls back to fetching `/content/404.json` — the themed 404 content fragment.

## Supported Code Block Languages

The `label_code_blocks` transform recognizes: python, javascript, jsx, typescript, tsx, bash, shell, sql, json, yaml, html, css, terraform, hcl, markdown, text, nix.