# The MCP Server

How Hypervisor exposes hyperspace operations to AI assistants through Model Context Protocol.

---

## What the MCP Server Does

The MCP server gives AI assistants (like Kiro) structured access to hyperspace. Instead of reading/writing raw markdown files, the AI calls typed tools that enforce conventions automatically — tag validation, status transitions, template compliance, and structural correctness.

```
Kiro ←→ MCP Protocol (stdio) ←→ mcp-server.py ←→ hv_mcp/ package ←→ .hyperspace/
```

The key insight: **convention enforcement happens at the tool level**, not in the AI's instructions. The AI can't create a document with an invalid tag or an impossible status transition because the tool rejects it before writing anything to disk.

## Entry Point: `mcp-server.py`

The server file is thin — it registers tools with FastMCP and delegates all logic to the `hv_mcp/` package:

```python
from mcp.server.fastmcp import FastMCP

server = FastMCP(
    "hypervisor",
    instructions="Hyperspace convention-as-code server..."
)

@server.tool(name="create_document")
def create_document_tool(...) -> dict:
    return create_document(...)  # Delegates to hv_mcp/crud.py
```

Each tool is a thin wrapper that maps MCP parameters to a function in one of the `hv_mcp/` submodules. The server communicates over stdio using the MCP protocol.

## Package Structure: `hv_mcp/`

```
hv_mcp/
├── __init__.py
├── config.py           ← Paths, registries (config/tags.json, config/projects.json), constants
├── index.py            ← In-memory document index + file watcher
├── index_file.py       ← Regenerates _index.md after write operations
├── search.py           ← search_hyperspace, recent_activity, get_work_items
├── tags.py             ← get_tags, add_tag (tag registry CRUD)
├── validation.py       ← validate_single, validate_all (convention checks)
├── crud.py             ← create_document, update_document, move_work_item
├── templates.py        ← Document template generators (markdown assembly)
├── template_drift.py   ← Drift detection (programmatic vs markdown templates)
├── analytics.py        ← stale_documents, health_report, tag_analytics
├── intelligence.py     ← session_brief, suggest_next_action, context_for_work_item
├── migration.py        ← migrate_document, get_schema_changelog
├── generation.py       ← suggest_tags, similar_documents, outline_work_item
├── helpers.py          ← Slug generation, validation helpers, backlink rewriting
├── dates.py            ← Date parsing and age calculations
└── backlinks.py        ← Reverse-link graph (who links to whom)
```

## The In-Memory Index

The server maintains a live index of all hyperspace documents in memory. On startup, `rebuild_index()` walks `.hyperspace/` and extracts metadata (title, tags, dates, status, project, type) from every `.md` file.

```python
_index: list[dict] = []   # All documents, one dict per file
_index_lock = threading.Lock()  # Thread-safe access
```

A watchdog file watcher keeps the index fresh — when a `.md` file is created, modified, or deleted, the index updates incrementally without a full rescan.

This index powers search, recent activity, session briefs, and all analytics tools. It's the reason MCP operations are fast — they read from memory, not disk.

## Tool Categories

### Search & Retrieval

| Tool | Purpose |
|------|---------|
| `search_hyperspace` | Text + tag + type search across all documents |
| `recent_activity` | Documents updated within N days |
| `get_work_items` | Work items filtered by status, tags, project |

These read from the in-memory index — no disk I/O needed.

### Document CRUD

| Tool | Purpose |
|------|---------|
| `create_document` | Create new documents with full convention enforcement |
| `update_document` | Modify metadata fields (status, tags, project) |
| `move_work_item` | Move work item from to-do → done, rewrite backlinks |

Every write operation:
1. Validates inputs (tags against registry, project against registry, status transitions)
2. Generates content using a template function from `templates.py`
3. Writes the file to disk
4. Refreshes the in-memory index
5. Regenerates `_index.md`
6. Triggers a site rebuild (background thread)

### Tag Management

| Tool | Purpose |
|------|---------|
| `get_tags` | Return the full tag registry with usage counts |
| `add_tag` | Add a new tag (validates naming, checks duplicates) |

The tag registry lives in `config/tags.json`. The `add_tag` tool enforces:
- Lowercase kebab-case naming
- Category must be `application`, `technology`, or `domain`
- Fuzzy duplicate detection (rejects tags too similar to existing ones)

### Validation & Health

| Tool | Purpose |
|------|---------|
| `validate_document` | Check one or all docs against conventions |
| `health_report` | Full validation + trend comparison + template drift check |
| `migrate_document` | Auto-fix metadata format issues (non-destructive) |
| `get_schema_changelog` | Show when conventions changed |

The health report records snapshots to `state/health-history.json` and compares against previous runs to show whether the knowledge base is improving or declining.

### Analytics

| Tool | Purpose |
|------|---------|
| `stale_documents` | Documents not updated within N days |
| `tag_analytics` | Co-occurrence, underused tags, merge candidates |

### Intelligence

| Tool | Purpose |
|------|---------|
| `session_brief` | Curated context for starting a productive session |
| `suggest_next_action` | Prioritized recommendations based on work state |
| `context_for_work_item` | Full context package (work item + linked docs + backlinks) |

### Generation

| Tool | Purpose |
|------|---------|
| `suggest_tags` | Analyze content and recommend tags from registry |
| `similar_documents` | Detect duplicates before creating new docs |
| `outline_work_item` | Generate structured work item from freeform text |

## Template System

Document creation flows through `templates.py`, which has one function per document type:

```python
apply_work_item_template(title, description, tags, project, ...)
apply_idea_template(title, description, tags, doc_type, concept, ...)
apply_document_template(title, description, tags, content, ...)
apply_adr_template(title, tags, number, context, decision, ...)
apply_bugfix_template(title, tags, severity, affected, problem, ...)
```

Each function assembles a markdown string with the correct metadata fields, section headings, and section order for its document type.

### Dual-Source Guarantee

Templates exist in two places that must stay in sync:

| Source | Purpose |
|--------|---------|
| `.hyperspace/templates/*.md` | Human-readable reference (AI reads before manual creation) |
| `hv_mcp/templates.py` | Programmatic output (MCP tool uses for `create_document`) |

The **markdown template is the source of truth**. The Python code must match its section order, metadata fields, and section names. The `template_drift.py` module enforces this — it generates a sample from each Python template, extracts structural elements, and compares them against the markdown reference.

The health report includes drift detection results automatically.

## Validation Engine

`validation.py` checks documents against these rules:

| Rule | What It Checks |
|------|---------------|
| `structure-missing-title` | Document has an H1 heading |
| `metadata-missing-created` | `Created:` field exists |
| `metadata-missing-updated` | `Updated:` field exists |
| `metadata-date-format` | Dates include time (`YYYY-MM-DDTHH:MM`) |
| `metadata-key-format` | Uses `Created:` not `Date:` |
| `metadata-format-bold` | Uses `- Key:` not `**Key:**` |
| `tag-unknown` | Tags exist in the canonical registry |
| `tag-count-low` | At least 2 tags |
| `tag-count-high` | No more than 4 tags |
| `project-unknown` | Project exists in registry |

Validation skips directories that don't contain user documents (`templates`, `.external`, `.hypervisor`) and specific files (`_index.md`, `_readme.md`).

## Data Flow: Create Document

Here's the full flow when the AI calls `create_document(type="work-item", ...)`:

```
1. crud.py validates type is valid
2. crud.py calls validate_tags() → checks each tag against config/tags.json
3. crud.py calls validate_project() → checks against config/projects.json
4. crud.py calls apply_work_item_template() → assembles markdown string
5. crud.py generates slug from title, checks for collisions
6. crud.py writes the .md file to work/to-do/{slug}.md
7. crud.py calls refresh_single() → updates in-memory index
8. crud.py calls regenerate_index_file() → rewrites _index.md
9. crud.py calls trigger_site_build() → rebuilds HTML site (background thread)
10. crud.py returns {path, title, slug} confirmation
```

If any validation step fails (bad tag, invalid project, missing required field), the tool returns an error dict and nothing is written.

## Configuration Files

Two JSON files serve as live registries:

### `tags.json`

```json
{
  "portal": {"category": "application", "description": "The main cyber-portal application"},
  "django": {"category": "technology", "description": "Django/DRF backend framework"},
  "security": {"category": "domain", "description": "Security and access control"}
}
```

### `projects.json`

```json
{
  "projects": [
    "General System Development",
    "Curriculum Management",
    "CYBER Range",
    "CYBERPortal Platform"
  ]
}
```

These are the authoritative sources for tag and project validation. The steering file documents the rules and conventions; these files hold the data.

## Status Transitions

Work items follow a directed state machine defined in `config.py`:

```
Planned → In Progress → Complete
Planned → Complete  (skip In Progress for small items)
Complete → (nothing — immutable once complete)
```

The `update_document` tool enforces these transitions. Attempting `Complete → In Progress` returns an error.

## Site Rebuild Trigger & Process Coordination

After every write operation (create, update, move), the server triggers a site rebuild — but **only when the desktop app is not running.**

### The Ownership Rule

**The desktop app owns site builds. The MCP server owns data operations.**

When both processes run simultaneously (common — Kiro's MCP server runs while the desktop app is open), they share the `.hyperspace/` directory. Without coordination, both watchers would fire on the same file change, potentially triggering concurrent builds that cause Windows file-locking errors.

### How It Works

```python
def trigger_site_build():
    # If the desktop app is running, its watcher handles rebuilds.
    app_lock = CONFIG_DIR / ".app_running"
    if app_lock.exists():
        return  # Desktop watcher will pick up the change and rebuild

    # Otherwise, MCP handles the rebuild autonomously
    threading.Thread(target=_build, daemon=True).start()
```

The desktop app creates `.hypervisor/.app_running` on startup (containing its PID) and deletes it on shutdown. The MCP server checks for this file before triggering builds.

When the desktop app IS running:
- MCP writes the file and updates the in-memory index
- MCP regenerates `_index.md`
- MCP skips the site build (returns immediately)
- The desktop app's watcher detects the file change and rebuilds with proper debouncing

When the desktop app is NOT running:
- MCP writes the file and updates the in-memory index
- MCP regenerates `_index.md`
- MCP triggers `full_build()` in a background thread

### The MCP Watcher

The MCP server's own file watcher (`hv_mcp/index.py`) is simpler than the desktop app's watcher. It only updates the in-memory index — it never writes files or triggers builds. It includes a 100ms delay before reading files to let write operations flush on Windows.

### Work Item Completion

`move_work_item` (MCP tool) and `mark_done` (desktop app bridge) both move files from `work/to-do/` to `work/done/`. They handle the same operation but from different entry points:

| Concern | MCP `move_work_item` | Desktop `mark_done` |
|---------|---------------------|---------------------|
| File write | Write to dest, delete source | Write to dest, delete source |
| Windows file locks | Retry deletion 5× with backoff | Retry deletion 5× with backoff |
| Index update | `refresh_single` + `regenerate_index_file` | `rebuild_index` + `regenerate_index_file` |
| Site rebuild | Via `trigger_site_build` (defers if app running) | Explicit `full_build()` after operation |
| Watcher suppression | Not needed (MCP watcher is read-only) | `ignore_path` called before operation |

### Preventing Half-States

`update_document` rejects `status="Complete"` for work items — callers must use `move_work_item()` which also relocates the file. This prevents a "status says Complete but file is still in to-do/" half-state.

## Reference Links

- [FastMCP documentation](https://gofastmcp.com/) — the MCP server framework
- [Model Context Protocol spec](https://modelcontextprotocol.io/) — the protocol standard
- `mcp-server.py` — the entry point (tool registration)
- `hv_mcp/` — all implementation logic
- `tags.json` — canonical tag registry
- `projects.json` — valid project names

## Next

← [Design Decisions](../09-design-decisions/index.html) — why things are built this way
