# HV-TECHREF

A comprehensive walkthrough of how Hypervisor works, from source to rendered site. This document covers every module, every pipeline stage, and every client-side system — written so you can understand the construction decisions and learn from the patterns.

- Created: 2026-04-24T00:00
- Updated: 2026-07-14T09:43
- Tags: hypervisor, architecture, python, javascript

---

## High-Level Architecture

Hypervisor is a zero-dependency static site generator that produces a Single Page Application (SPA). The entire stack is:

- Python (`build.py` + `site_utils/` package) — reads markdown, produces JSON content fragments + one HTML shell
- Modular CSS in `assets/css/` (concatenated in sorted order during build into a single `site/style.css`)
- Modular JS in `assets/js/` (concatenated in sorted order during build into a single `site/app.js`, includes the SPA router)
- One CDN script — Lucide icons (Mermaid is lazy-loaded only when needed)

There is no bundler, no framework, no build tool chain. The output is a directory served by PyWebView's internal Bottle HTTP server — one HTML shell loads JSON content fragments dynamically via the client-side router.

### Directory Layout

```
.hypervisor/
  build.py                    # Entry point — orchestrator, CLI, incremental rebuild
  assets/
    css/                      # Modular CSS (numbered sorted, zz-* last → site/style.css)
      00-variables.css        # CSS custom properties, resets, component base classes
      01-layout.css           # Topbar, page, footer, breadcrumbs, condensed width
      02-search.css           # Search input, results dropdown, tag filtering, work item filters
      03-menus.css            # Reference menu, utilities menu, width toggle, accent picker
      04-content.css          # Markdown body, code blocks, tables, related sections
      05-cards.css            # Card grid, doc lists, build stats, homepage dock
      06-pinboard.css         # Pin cards, pin button, pinboard page, pin type badges
      07-toc.css              # Floating table of contents sidebar
      08-utilities.css        # Shared utility page container, 404 page
      utilities/              # Per-utility-page styles (loaded after numbered modules)
        password-gen.css
        quiz.css
        regex-editor.css
        screensaver-settings.css
        health-dashboard.css
        palette-gen.css
      09-effects.css          # Cursor companion, glitch effect, keyboard shortcuts
      10-splash.css           # Loading splash screen
      11-tabs.css             # Tabbed document interface
      12-drop-import.css      # Drag-and-drop file import zone
      13-ideas-dismiss.css    # Idea dismiss button
      14-editor.css           # Inline markdown editor
      15-command-palette.css  # Command palette (Ctrl+K) overlay
      16-scratch.css          # Scratch buffer / daily journal panel
      zz-accessibility.css    # A11y panel, high contrast, reduced motion (loads last)
    js/                       # Modular JS (core/ → features/ → webgl/ → screensaver/ → site/app.js)
      core/                   # Foundation modules (load first, order matters)
        00-core.js            # IIFE open, PyWebView bridge, preferences, toasts, shared DOM refs
        01-router.js          # SPA router: fragment fetch, content swap, history, lifecycle
        navigation.js         # Search, topbar scroll, ref menu, util menu, code copy, scroll-to-top
        toc.js                # Floating TOC sidebar, active heading tracking
        theme.js              # Accent color picker, palette modes, brand/title hover
      features/               # Self-contained features (order-independent, zz-* last)
        actions-drawer.js     # Footer actions drawer toggle
        command-palette.js    # Unified command palette (Ctrl+K)
        content.js            # Todo filters, section copy, table copy, zoom, width toggle
        drop-import.js        # Drag-and-drop .md import on .external page
        editor.js             # Inline markdown editor
        effects.js            # Terminal glitch, footer clock, cursor companion
        ideas-dismiss.js      # Dismiss/delete buttons on ideas/ page
        live-reload.js        # Build-change polling / fragment re-fetch
        pins.js               # Pinboard: pin CRUD, card rendering, navigation
        scratch.js            # Scratch buffer / daily journal (backtick hotkey)
        shortcuts.js          # Keyboard shortcuts overlay
        splash.js             # Initial load splash screen
        tabs.js               # Tabbed document interface
        writeback.js          # Task checkbox + status write-back (desktop app)
        zz-accessibility.js   # Accessibility panel + IIFE close (must be last)
      webgl/                  # WebGL2 integration layer (loads before screensaver)
        00-hypergl.js         # HyperGL — zero-dep WebGL2 runtime for GPU effects
      screensaver/            # Screensaver engine + modes (00-* first, zz-* last)
        00-engine-head.js     # Engine IIFE open, shared helpers, DOM overlay, state
        particles.js          # Mode: SPH fluid particles (CPU)
        starfield.js          # Mode: Starfield fly-through
        worm.js               # Mode: Wandering worm trails
        dither.js             # Mode: Bayer-dithered gradients (CPU)
        bounce.js             # Mode: Bouncing text (DVD-style)
        life.js               # Mode: Conway's Game of Life
        grid.js               # Mode: Infinite perspective grid
        gl-dither.js          # Mode: GPU Bayer dither (WebGL2 via HyperGL)
        gl-noise.js           # Mode: GPU FBM noise (WebGL2 via HyperGL)
        gl-particles.js       # Mode: GPU fluid particles (WebGL2 via HyperGL)
        zz-engine-tail.js     # Engine tail: public API, activate/dismiss, idle timer
  site_utils/                 # Python package — build pipeline modules
    __init__.py
    config.py                 # Paths, constants, markdown engine, category metadata
    file_utils.py             # File collection, path math, naming, dates, status, app-group inference
    markdown_processing.py    # Markdown-to-HTML + post-processing transforms
    page_generation.py        # HTML template, breadcrumbs, top bar, page assembly
    page_builders.py          # Homepage, pinboard, 404, utility pages, learn section
    fragment.py               # Content fragment JSON schema, serialization
    directory_index.py        # Homepage and directory index page generators
    search.py                 # Search index builder (JSON blob)
    build_cache.py            # Content hash caching for incremental builds
    backlinks.py              # Reverse-link index (who links to whom)
    ideas.py                  # Idea delete/dismiss operations
    external_files.py         # .external/ import and delete operations
    work_items.py             # Work item mark-done operations
  utilities/                  # Raw HTML snippets for interactive tools
    password-generator.html
  docs/                       # Documentation about hypervisor itself
  site/                       # Generated output (ephemeral — never edit directly)
```

### Data Flow

```
.hyperspace/*.md files
        |
        v
  collect_files()          — Walk filesystem, filter by SKIP_DIRS/SKIP_FILES
        |
        v
  build_search_index()     — Extract title, snippet, tags, dates per document
  build_backlink_index()   — Scan for .md links, build reverse map
        |
        v
  For each .md document:
    render_markdown()      — Convert to HTML + post-process transforms
    build_page()           — Inject into PAGE_TEMPLATE with topbar, TOC, backlinks
    Write to site/{path}/index.html
        |
        v
  For each directory:
    generate_dir_index_content()  — Build card grid + document list
    build_page()                  — Wrap in template
    Write to site/{dir}/index.html
        |
        v
  generate_home_content()  — Build homepage with category cards, stats, recent docs
  Write to site/index.html
        |
        v
  Concatenate assets/css/*.css → site/style.css
  Copy assets/app.js → site/app.js
  Open in browser via webbrowser.open()
```

---

## The Build Pipeline (build.py)

`build.py` is the entry point. It calls `main()` which runs a linear pipeline:

### Phase 0: Setup

```python
build_id = str(int(time.time() * 1000))
files = collect_files(HYPERSPACE_ROOT)
search_index = build_search_index(files)
backlink_index = build_backlink_index(files)
```

- `build_id` is a millisecond epoch timestamp stamped into every page for stale-tab detection (more on this later).
- `collect_files()` walks `.hyperspace/` recursively, returns a sorted list of relative `.md` paths, excluding anything in `SKIP_DIRS` or `SKIP_FILES`.
- The search index and backlink index are computed once, upfront, before any pages are generated.

### Phase 1: Document Pages

For each markdown file, the pipeline:

1. Reads the raw `.md` text
2. Extracts the title (first `# heading`, or falls back to a cleaned-up filename)
3. Calls `render_markdown()` which returns `(content_html, toc_html)`
4. Looks up backlinks for this document from the pre-built index
5. Calls `build_page()` to assemble the final HTML
6. Writes to `site/{path-without-extension}/index.html`

The output path convention is important: `context/foo.md` becomes `site/context/foo/index.html`. This means every document gets its own directory, and links can use clean paths like `context/foo/index.html` without worrying about file extensions.

### Phase 2: Directory Index Pages

`collect_all_dirs()` returns every directory prefix that contains documents (directly or nested). For each one, the pipeline generates an index page — unless a document page already exists at that path (collision avoidance).

Directory indexes show:
- Subdirectory cards (same grid layout as the homepage)
- A document list with date metadata, sorted newest-first for dated docs, alphabetical for undated

### Phase 3: Homepage

The homepage is special-cased. It gets:
- Build statistics (document count, page count, timestamp)
- Category cards for every top-level directory (except `reference`, which is accessible via the header menu instead)
- Root-level documents (if any exist directly in `.hyperspace/`)
- A "Recently Updated" section showing the 10 most recently dated documents

### Phase 4: Utility Pages

Utility pages are raw HTML snippets in the `utilities/` directory. They get wrapped in the same `PAGE_TEMPLATE` as everything else, so they inherit the topbar, search, accent picker, and all styling. The password generator is the current example.

### Phase 5: Browser Launch

```python
webbrowser.open((OUTPUT_DIR / "index.html").as_uri())
```

Opens the generated site in the default browser. Combined with the stale-tab system (covered in the JS section), this replaces the previous tab automatically.

---

## Configuration (site_utils/config.py)

This module centralizes all constants and shared state.

### Path Resolution

```python
_HYPERVISOR_DIR = Path(__file__).resolve().parent.parent  # .hypervisor/
HYPERSPACE_ROOT = _HYPERVISOR_DIR.parent                  # .hyperspace/
OUTPUT_DIR = _HYPERVISOR_DIR / "site"
ASSETS_DIR = _HYPERVISOR_DIR / "assets"
```

Paths are resolved relative to `config.py`'s own location, so the build works regardless of where you invoke it from.

### Skip Filters

```python
SKIP_DIRS = {"__pycache__", "site"}
SKIP_FILES = {".gitkeep"}
```

`collect_files()` checks every path component against `SKIP_DIRS`. If any segment matches, the path is excluded. This is a set membership check, not a glob — simple and fast.

### Markdown Engine

A single `markdown.Markdown` instance is configured once and reused (with `.reset()` between documents):

- `fenced_code` — triple-backtick code blocks
- `codehilite` — syntax highlighting via Pygments
- `tables` — pipe-delimited tables
- `toc` — generates a table of contents (used for the sidebar TOC)
- `meta` — YAML-style metadata in frontmatter
- `sane_lists` — prevents list items from being merged unexpectedly

### Category Metadata

Three parallel dictionaries drive the homepage and directory index rendering:

```python
CATEGORY_LABELS   = {"context": "Context", ...}       # Display names
CATEGORY_DESCRIPTIONS = {"context": "Project overviews...", ...}  # Card descriptions
CATEGORY_ICONS    = {"context": "book-open", ...}      # Lucide icon names
```

Categories are auto-discovered from the filesystem. These dictionaries are optional enrichment — if a directory isn't listed, it falls back to title-cased directory name and a generic folder icon.

---

## File Utilities (site_utils/file_utils.py)

### collect_files(root)

Walks the tree with `root.rglob("*.md")`, filters against `SKIP_DIRS` and `SKIP_FILES`, returns a sorted list of `Path` objects (relative to root). Sorting ensures deterministic output order.

### Path Math

Several functions handle the mapping between source paths and output paths:

- `html_dir_for(rel_path)` — strips `.md` extension, normalizes to POSIX separators. `context/foo.md` becomes `context/foo`.
- `href_for(rel_path)` — appends `/index.html` to the above. Used for generating links.
- `root_prefix(html_dir)` — computes the relative path back to site root. A page at depth 2 gets `../../`. This is critical for `file://` compatibility — all asset and link paths must be relative.

### Naming

- `nice_name(fname)` — converts filenames to display names. `_index.md` becomes "Index", `api-authentication-pattern.md` becomes "Api Authentication Pattern".
- `dir_label(name)` — looks up `CATEGORY_LABELS`, falls back to title-casing.
- `get_title(md_text, fallback)` — extracts the first `# heading` from markdown text via regex.

### Date Extraction

`extract_dates(md_text)` scans the first 30 lines of a document for date metadata in multiple formats:

- `Created: 2026-02-17` or `Created: 2026-02-17T14:30` (ISO date or datetime)
- `Updated: 2026-02-18T09:15` or `Last updated: 2026-04-20` (ISO)
- `**Last Updated:** February 13, 2026` (long format with month name)

All dates are normalized to `YYYY-MM-DDTHH:MM` format (plain dates get `T00:00`). Returns `{"created": "YYYY-MM-DDTHH:MM", "updated": "YYYY-MM-DDTHH:MM"}`. The `sort_date()` function prefers `updated` over `created` for sorting, and returns `"0000-00-00T00:00"` for undated docs so they sort last. The `display_date()` helper formats datetimes for HTML display as `YYYY-MM-DD HH:MM`.

---

## Markdown Processing (site_utils/markdown_processing.py)

### render_markdown(md_text)

Resets the shared `MD` instance, converts markdown to HTML, extracts the TOC, then runs `post_process()`.

### Post-Processing Pipeline

The `post_process()` function applies a chain of HTML transforms in a specific order:

```python
def post_process(html):
    html = rewrite_md_links(html)       # 1. Fix hrefs
    html = extract_metadata_block(html)  # 2. Style metadata
    html = wrap_h2_sections(html)        # 3. Section panels
    html = style_related_section(html)   # 4. Related/See Also styling
    html = convert_mermaid_blocks(html)  # 5. Mermaid diagram detection
    html = label_code_blocks(html)       # 6. Language labels
    html = style_task_lists(html)        # 7. Checkbox styling
    return html
```

Order matters. Link rewriting must happen first because later transforms parse the HTML structure. Section wrapping must happen before code block labeling because it changes the DOM tree.

### Transform Details

**rewrite_md_links** — Regex replaces `href="...something.md"` with `href="...something/index.html"`. This is what makes inter-document links work in the generated site.

**extract_metadata_block** — Detects metadata patterns after the first `<h1>` (either as a `<ul>` with `Key: Value` items, or as consecutive `<p>` tags) and wraps them in a styled `<div class="doc-meta">` block. Also converts `.md` file paths inside metadata values into clickable links.

**wrap_h2_sections** — Splits the HTML at every `<h2>` tag and wraps each section in a collapsible `<details class="doc-section" open>` element. The H2 text becomes the `<summary>` and the section content goes in a `<div class="doc-section-content">`. Sections are open by default and use native browser collapse/expand behavior.

**style_related_section** — Detects H2 sections titled "Related", "Related Docs", "References", or "See Also" and restructures them. Groups list items by category prefix (Model, Component, API, Backend, etc.) under sub-headers, and splits each categorized item at the em-dash into a path line and a description line for better readability. Plain links are grouped under a "Links" header. Sections with only one category type skip the sub-headers.

**convert_mermaid_blocks** — Since Pygments' `codehilite` strips the language identifier from code blocks, this transform detects mermaid diagrams by their content patterns (keywords like `erDiagram`, `flowchart`, `sequenceDiagram`, etc.) in blocks that have no syntax-highlighted spans. Converts them to `<pre class="mermaid">` for client-side rendering.

**label_code_blocks** — Wraps code blocks in `<div class="code-block">` and adds a `<span class="code-lang">` label based on the language class. Supports a map of known languages.

**style_task_lists** — Converts `[ ]` and `[x]` patterns in list items into styled checkbox elements using Unicode characters.

---

## Search Index (site_utils/search.py)

### build_search_index(files)

Iterates every document and builds a JSON-serializable list of entries:

```json
{
  "title": "Wave 3 Regression...",
  "path": ".external/django-wave3-org-users-payload-regression.md",
  "href": ".external/django-wave3-org-users-payload-regression/index.html",
  "snippet": "After merging the wave 3 API restructure...",
  "tags": ["artillery", "performance"],
  "date": "2026-04-24"
}
```

This JSON blob is embedded inline in every page as `window.SEARCH_INDEX = [...]`. No XHR, no fetch — the data is right there in the HTML. This is a deliberate choice for `file://` compatibility.

### Snippet Extraction

`_extract_snippet()` skips the title, metadata lines, headings, code fences, and HTML, then joins the first ~200 characters of body text. Strips markdown formatting (bold, italic, inline code, links) for clean display.

### Tag Extraction

`_extract_tags()` scans the first 30 lines for `Tags:`, `Technologies:`, or `Related:` metadata and splits on commas.

---

## Backlinks (site_utils/backlinks.py)

### build_backlink_index(files)

Scans every document for markdown-style links to `.md` documents (`[text](path.md)`), resolves relative paths against the source document's directory, and builds a reverse map:

```python
{
  "context/portal-architecture.md": [
    ("research/api-architecture/rest-restructure.md", "REST Restructure"),
    ("ideas/to-do/portal/devops/some-idea.md", "Some Idea"),
  ]
}
```

### Link Resolution

`_resolve_link()` handles relative paths including `../` traversal. It normalizes the path by walking the parts array — `..` pops the last element, `.` is skipped, everything else is appended. This is pure path math with no filesystem access.

### Rendering

`render_backlinks_html()` produces a "Referenced By" section at the bottom of each document page, styled with Lucide icons and the source file path displayed alongside the title.

---

## Directory Indexes (site_utils/directory_index.py)

### collect_dir_contents(files, dir_prefix)

For a given directory, separates immediate child documents from subdirectories. Returns `(subdirs, doc_entries)`. This is the core of the hub-and-spoke navigation — each level only shows its direct children.

### collect_all_dirs(files)

Returns every directory prefix that contains documents (at any depth). Used to determine which directory index pages need to be generated.

### generate_home_content(files, build_stats)

Builds the homepage HTML:

1. Build stats block — scanned count, generated count, breakdown, output path, timestamp
2. Category card grid — one card per top-level directory (except `reference`), each showing icon, label, description, and doc count
3. Root documents section — any `.md` documents directly in `.hyperspace/`
4. Recently Updated — top 10 documents sorted by date (prefers `updated` over `created`)

### generate_dir_index_content(files, dir_prefix)

Builds a subdirectory index:

1. Subdirectory cards (same grid layout)
2. Documents section — document list with dates, sorted: dated docs newest-first, then undated alphabetically

---

## Page Generation (site_utils/page_generation.py)

### PAGE_TEMPLATE

A single HTML template string with `{{PLACEHOLDER}}` tokens:

- `{{TITLE}}` — page title (in `<title>` and nowhere else)
- `{{BUILD_ID}}` — millisecond epoch timestamp for stale-tab detection
- `{{TOPBAR}}` — the full header bar HTML
- `{{TOC_SIDEBAR}}` — table of contents (empty string if not enough headings)
- `{{CONTENT}}` — the rendered markdown or index HTML
- `{{REL_PATH}}` — source file path shown in the footer
- `{{SEARCH_INDEX}}` — the full JSON search index, inline
- `{{ROOT}}` — relative path back to site root (e.g., `../../`)

The template includes:
- Lucide icons CDN (`unpkg.com/lucide@0.468.0`)
- Mermaid CDN (`cdn.jsdelivr.net/npm/mermaid@11`) with dark theme configuration
- Inline `<script>` that sets `window.SEARCH_INDEX`
- Reference to `app.js` (relative via `{{ROOT}}`)

### TOP_BAR

The header bar template includes:
- Brand link (icon + "HYPERVISOR" text)
- Breadcrumb navigation
- Search input with results dropdown
- Utilities menu (wrench icon)
- Reference menu (text-search icon)
- Accent color picker with palette preview and mode toggle

### make_breadcrumbs(rel_path_str, root)

Builds breadcrumb HTML from a path string. Each segment except the last is a link to its directory index. The first crumb is always `~` linking to the homepage.

### build_page(...)

The main assembly function. Takes content HTML, title, path, root prefix, search JSON, optional TOC, optional backlinks, and build ID. Assembles breadcrumbs, topbar, TOC sidebar (only shown if 3+ headings), appends backlinks to content, and performs all template replacements.

The TOC sidebar is conditionally included — it only renders if the markdown's table of contents has at least 3 list items, preventing clutter on short pages.

---

## Client-Side Systems (assets/js/)

All client-side behavior lives in `assets/js/` organized into four subdirectories (`core/`, `features/`, `webgl/`, `screensaver/`) that are concatenated into a single `site/app.js` during build. Everything runs inside a single IIFE (`(function() { ... })()`) to avoid polluting the global scope. The IIFE opens in `core/00-core.js` and closes in `features/zz-accessibility.js`. Each subsystem is either inline or wrapped in its own nested IIFE within the shared closure.

### Lucide Icon Initialization

```javascript
if (window.lucide) {
  lucide.createIcons({ attrs: { 'stroke-width': 1.5 } });
}
```

Called once on load. Also re-called when dropdown menus open (since their content is injected dynamically and needs icon rendering).

### Search

The search system is entirely client-side, operating on the `window.SEARCH_INDEX` array embedded in every page.

**Filtering logic:**
1. If a tag filter is active, narrow to entries matching that tag
2. If a text query exists, filter by title, path, snippet, or tags (case-insensitive substring match)
3. Cap results at 15

**Tag filtering:** Clicking a tag in search results activates a tag filter. A visual indicator appears below the search input showing the active tag with a clear button. Tags are extracted from the search index entries.

**Keyboard navigation:** Arrow keys move selection, Enter opens the selected result, `/` focuses the search input, Escape clears and blurs.

**href resolution:** `resolveHref()` prepends the site root prefix (extracted from the brand link's href) to search result links. This makes search work correctly regardless of which page you're on.

### Reference Menu

Filters the search index for entries whose path starts with `reference/`, builds a dropdown with title and snippet preview. Accessible via the text-search icon in the topbar.

### Utilities Menu

A hardcoded list of utility pages (currently just the password generator). Each entry has a name, Lucide icon, and href. The menu is built dynamically and rendered in a dropdown.

### Code Block Copy Buttons

For every `.code-block` element, a "copy" button is appended. Uses `navigator.clipboard.writeText()` with a fallback error state for `file://` protocol where the clipboard API may not be available.

### Scroll-to-Top Button

Shows after scrolling 300px, smooth-scrolls to top on click.

### Table of Contents Sidebar

The TOC sidebar is a floating nav panel that appears on pages with enough headings (3+) and sufficient content height (800px+).

**Active heading tracking:** Uses scroll position to determine which heading is currently in view. On each scroll frame, it walks the heading elements array backwards and finds the last one whose `offsetTop` is above the current scroll position (plus an 80px offset for the topbar). The corresponding TOC link gets an `toc-active` class.

### Accent Color System

The accent color picker lets users customize the site's primary color. The chosen color is persisted to `localStorage` and applied on every page load.

**Color math functions:**
- `hexToRgb()` — hex string to `{r, g, b}` object
- `rgbToHsl()` — RGB to `{h, s, l}` (hue in degrees, saturation and lightness as 0-1)
- `hslToHex()` — HSL back to hex string
- `dimColor()` — multiplies RGB channels by a factor (used for dim variants)

**Palette modes:** Five color harmony algorithms generate a 4-color palette from the accent:

| Mode | Algorithm | Angles |
|------|-----------|--------|
| Split (SPL) | Split-complementary | +150°, +210°, +180° |
| Triadic (TRI) | Triadic | +120°, +240°, +180° |
| Analogous (ANA) | Analogous | +30°, +60°, -30° |
| Square (SQR) | Tetradic | +90°, +180°, +270° |
| Complement (CMP) | Complementary | +180° (3 variants) |

Each mode produces `{accent, warm, cool, comp}` colors that are applied as CSS custom properties: `--accent`, `--warm`, `--cool`, `--comp`.

**applyAccent()** sets 10+ CSS custom properties including:
- `--accent`, `--accent-dim`, `--accent-glow`, `--accent-border`
- `--warm`, `--cool`, `--comp`
- `--cursor-default`, `--cursor-pointer`, `--cursor-text` — SVG data URI cursors colored to match the accent

The cursor customization is notable: it generates inline SVG data URIs with the accent color baked in, so even the mouse cursor matches the theme.

### Palette Preview

Four color swatches in the topbar show the current palette. Tooltips display the color name and hex value. Updated whenever the accent or palette mode changes.

### Brand and Title Icon Hover Effects

Both the homepage title icon and the header brand (icon + text) cycle through the four palette colors on hover at 50ms intervals, creating a rapid color-cycling animation. The effect stops and resets on mouse leave.

### Terminal Glitch Effect

A periodic visual effect that scrambles random text on the page for a split second, reinforcing the terminal aesthetic.

**How it works:**
1. `getGlitchTargets()` walks the DOM tree collecting text nodes (skipping scripts, styles, code blocks, and short nodes)
2. Every 8-25 seconds (random interval), picks 1-3 random text nodes
3. Runs 6 cycles at 70ms intervals, each cycle scrambling 15-40% of characters with random Unicode glyphs from a pool of box-drawing, block elements, and misc symbols
4. After the cycles complete, restores the original text

The glyph pool (`░▒▓█▄▀▐▌╔╗╚╝║═...`) is deliberately chosen from Unicode box-drawing and block element ranges to maintain the terminal feel.

### Footer Clock

A live clock in the page footer, updated every second. Displays `HH:MM:SS` in 24-hour format.

### Cursor Companion Box

A small decorative element that follows the mouse cursor. It becomes visible when hovering over clickable elements (links, buttons, cards, etc.) and plays a blink animation on click.

The clickable element detection uses a CSS selector string:
```javascript
var CLICKABLE = "a, button, [role='button'], input[type='color'], .card, .swatch, ...";
```

### Keyboard Shortcuts Overlay

Pressing `?` toggles a modal overlay showing available keyboard shortcuts. The overlay is created dynamically on page load and supports closing via the X button, clicking outside, or pressing Escape.

### Stale-Tab Auto-Close

The newest addition. Solves the problem of accumulating duplicate browser tabs on every rebuild.

**Mechanism:**
1. Each build stamps a unique `build_id` (millisecond epoch) into a `<meta name="build-id">` tag on every page
2. On page load, the JS reads this meta tag and writes the build ID to `localStorage` under the key `hypervisor-build-id`
3. The tab registers a `storage` event listener — this event fires in all *other* tabs whenever `localStorage` changes
4. When a new build opens, it overwrites the localStorage value, which triggers the `storage` event in every old tab
5. Old tabs receive the event, see the mismatched build ID, and call `window.close()`

This works because `localStorage` is shared across all `file://` pages in the same browser, and the `storage` event is delivered by the browser even to backgrounded or suspended tabs. Unlike `setInterval` polling (which browsers throttle or stop entirely for inactive tabs), the `storage` event is a system-level notification that always gets through.

---

## Utility Pages

Utility pages are standalone interactive tools that live in the `utilities/` directory as raw HTML snippets. The build pipeline wraps them in `PAGE_TEMPLATE`, giving them the full site chrome (topbar, search, accent picker).

### Password Generator

A client-side password generator with:
- Configurable length (4-128 via range slider)
- Character set toggles (uppercase, lowercase, digits, symbols, exclude ambiguous)
- Entropy calculation and strength rating (weak/fair/good/strong/excellent)
- Copy-to-clipboard
- History panel (last 15 generated passwords with timestamps)

Uses `crypto.getRandomValues()` for cryptographically secure random number generation.

---

## Design Decisions Worth Understanding

### Why file:// Compatibility?

The site runs without a web server. This means:
- All paths must be relative (the `{{ROOT}}` prefix system)
- Links must point to explicit `/index.html` files, not trailing-slash directories
- The search index must be inline JSON, not fetched via XHR
- `localStorage` is the only persistence mechanism available

### Why Modular CSS Concatenated Into One File?

No build tools means no code splitting, no tree shaking, no minification pipeline. CSS is split into numbered modules in `assets/css/` for developer ergonomics (each module owns a feature area), but the build concatenates them into a single `site/style.css`. JS follows the same pattern — numbered modules in `assets/js/` concatenated into a single `site/app.js`. For a site this size, a single file read per type is optimal.

### Why Regex-Based HTML Transforms?

The post-processing pipeline uses regex to transform HTML rather than a proper DOM parser. This is a pragmatic choice — the input is predictable (it comes from a known markdown engine with known extensions), and regex is fast and dependency-free. A DOM parser would add a dependency and complexity for no real benefit at this scale.

### Why Inline Search Index?

Every page embeds the full search index as a `<script>` tag. This duplicates data across pages but means:
- Search works instantly on any page (no async loading)
- No CORS issues with `file://` protocol
- No need for a service worker or IndexedDB

The trade-off is larger HTML pages, but for ~150 documents the index is small enough that this is negligible.

### Why localStorage for Stale-Tab Detection?

`BroadcastChannel` would be the most elegant solution but doesn't work on `file://` in all browsers. `localStorage` combined with the `storage` event is the next best thing — the event fires in all other tabs whenever a value changes, even if those tabs are backgrounded or have been idle for hours. This is more reliable than `setInterval` polling, which browsers aggressively throttle or suspend for inactive tabs.