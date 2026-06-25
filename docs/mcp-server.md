# HV-MCP-SERVER

Convention-as-code MCP server that exposes hyperspace document management as structured tools for AI assistants.

- Created: 2026-06-09T12:50
- Updated: 2026-06-09T15:32

## Overview

The Hypervisor MCP server (`mcp-server.py`) exposes the hyperspace knowledge base as a set of tools accessible to Kiro (or any MCP-compatible AI client). It enforces all hyperspace conventions — tag validation, project validation, status transitions, template compliance, canonical metadata format — at the tool level, guaranteeing structural correctness without requiring the AI to interpret steering prose.

The server runs alongside Kiro via the standard MCP stdio transport. It is configured in the workspace's `.kiro/settings/mcp.json`.

## Architecture

```
Kiro ←→ MCP Protocol (stdio) ←→ mcp-server.py ←→ hv_mcp/ package ←→ .hyperspace/
```

### Entry Point

`mcp-server.py` (~120 lines) is the thin registration layer. It:
1. Imports all tool implementations from the `hv_mcp/` package
2. Registers them as `@server.tool` functions with FastMCP
3. Builds the in-memory index and starts the file watcher at startup
4. Runs the MCP stdio transport

### Package Structure

```
.hypervisor/
├── mcp-server.py              # Entry point: FastMCP init, tool registration, startup
├── hv_mcp/                    # All server logic
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
│   └── generation.py          # suggest_tags, similar_documents, outline_work_item
├── config/                    # Portable configuration (tracked in git)
│   ├── tags.json              # Canonical tag registry
│   └── projects.json          # Valid project names
├── state/                     # Content-specific state (gitignored)
│   ├── work-item-counter.json # Sequential work item ID counter
│   └── health-history.json    # Persisted health snapshots
```

### Shared Infrastructure

All tools share these core systems:

| System | Module | Purpose |
|--------|--------|---------|
| In-memory index | `index.py` | Full document metadata in RAM, thread-safe, incrementally updated |
| Backlink graph | `backlinks.py` | Eagerly-built reverse-link map (who links to whom) |
| File watcher | `index.py` | Watchdog observer keeps index and backlinks current on disk changes |
| Tag registry | `config.py` → `config/tags.json` | Canonical tag names, categories, descriptions |
| Project registry | `config.py` → `projects.json` | Valid project names for validation |
| Health history | `health.py` → `health-history.json` | Timestamped validation snapshots for trend tracking |

## Tool Reference

The server exposes 19 tools organized into 6 functional groups.

### Search & Retrieval

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `search_hyperspace` | `query`, `tags[]`, `type`, `limit` | Full-text + tag + type filtered search across all documents |
| `recent_activity` | `days` (default 7) | Documents created or updated within N days, sorted newest first |
| `get_work_items` | `status`, `tags[]`, `project` | Work items filtered by status/tags/project |

### Tags

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `get_tags` | — | Full tag registry with per-tag usage counts |
| `add_tag` | `name`, `category`, `description` | Register a new tag (validates kebab-case, no dupes) |

### Validation

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `validate_document` | `path` (or "all") | Check one doc or entire corpus against conventions |

**Validation rules enforced:**
- H1 title present
- `Created:` and `Updated:` metadata present with datetime format
- Tags validated against canonical registry (with fuzzy suggestions for typos)
- Project validated against project registry
- No bold metadata format (`**Key:**`)
- No `Date:` key (must be `Created:`)
- Tag count within 2–4 range

### CRUD

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `create_document` | `type`, `title`, `tags[]`, + type-specific fields | Create a new document with full template and convention enforcement |
| `update_document` | `path`, `status`, `tags[]`, `project`, `doc_type` | Update metadata fields with transition validation |
| `move_work_item` | `slug` | Move a work item from to-do/ to done/ (sets Complete, rewrites backlinks) |

**Supported document types:** `work-item`, `idea`, `document`, `adr`, `bugfix`

Each type has required and optional fields:
- **work-item**: `title`, `tags`, `project` (required); `overview`, `design`, `acceptance_criteria`, `tasks` (optional)
- **idea**: `title`, `tags`, `concept` (required)
- **document**: `title`, `tags`, `directory`, `content` (required)
- **adr**: `title`, `tags`, `number`, `context_text`, `decision`, `rationale` (required)
- **bugfix**: `title`, `tags`, `severity`, `affected`, `problem`, `root_cause`, `fix` (required)

### Analytics & Health

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `stale_documents` | `days` (default 30) | Documents not updated within threshold, grouped by type |
| `health_report` | — | Run validation, record snapshot, compare to previous, show trend |
| `tag_analytics` | — | Co-occurrence patterns, underused tags, merge candidates, orphans |

### Smart Context

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `session_brief` | `project` (optional) | One-call session start: active work (with task progress), recent activity, stale items, completions, planned queue |
| `suggest_next_action` | — | Prioritized action suggestions: completable, blocked, resumable, promotable, ready-to-start |
| `context_for_work_item` | `slug` | Full work item + outlinks + backlinks + related-by-tags as structured package |

### Template Evolution & Migration

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `migrate_document` | `path` (or "all"), `dry_run` | Fix metadata drift: Date→Created, bold→dash, missing fields, reorder |
| `get_schema_changelog` | — | Schema version history and current conventions |

### Content Generation

| Tool | Parameters | Purpose |
|------|-----------|---------|
| `suggest_tags` | `content` | Confidence-ranked tag suggestions based on keyword analysis |
| `similar_documents` | `title`, `content` (optional) | Duplicate detection with proceed/review/duplicate recommendation |
| `outline_work_item` | `description` | Generate structured work item outline from freeform text |

## Configuration

### Kiro MCP Config

The server is configured in the workspace `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "hypervisor": {
      "command": "python",
      "args": [".hyperspace/.hypervisor/mcp-server.py"],
      "disabled": false,
      "autoApprove": [
        "search_hyperspace",
        "recent_activity",
        "get_work_items",
        "get_tags",
        "add_tag",
        "validate_document",
        "create_document",
        "update_document",
        "move_work_item",
        "stale_documents",
        "health_report",
        "tag_analytics",
        "session_brief",
        "suggest_next_action",
        "context_for_work_item",
        "migrate_document",
        "get_schema_changelog",
        "suggest_tags",
        "similar_documents",
        "outline_work_item"
      ]
    }
  }
}
```

### Dependencies

The MCP server requires:
- `mcp` — FastMCP server library (MCP protocol implementation)
- `rapidfuzz` — C-accelerated fuzzy string matching (for `similar_documents`)
- `watchdog` — File system monitoring (for incremental index updates)
- Standard library: `pathlib`, `json`, `re`, `threading`, `datetime`

These are in addition to the base hypervisor dependencies (`markdown`, `pygments`).

### Registries

**tags.json** — Canonical tag registry. Structure:
```json
{
  "tag-name": {
    "category": "application | technology | domain",
    "description": "What this tag refers to"
  }
}
```

**projects.json** — Valid project names:
```json
{
  "projects": ["General System Development", "Curriculum Management", "CYBER Range", "CYBERPortal Platform"]
}
```

## How the Index Works

At startup, the server:
1. Walks all `.md` files in `.hyperspace/` (excluding `.hypervisor/`, `templates/`, `.external/`)
2. Parses each file's metadata (title, description, dates, tags, status, project, type)
3. Builds a flat list of index entries in memory
4. Builds the backlink graph (maps each path → set of paths that link to it)
5. Starts a watchdog observer that incrementally updates both on file changes

The index is thread-safe (locked reads/writes) and stays current without manual rebuilds. Tools query the index directly — no disk I/O for search, filtering, or graph traversal.

## Key Design Decisions

### Convention Enforcement at the Tool Layer

The AI never needs to remember hyperspace conventions. Every `create_document` call validates tags, projects, and required fields before writing. Every `update_document` validates status transitions. The server rejects invalid operations with structured error messages.

### Non-Destructive Migration

`migrate_document` only touches metadata structure (field names, format, order). It never modifies content sections, headings, or body text. Dry-run mode previews all changes before applying.

### Process Coordination: Desktop App vs MCP Server

**The desktop app owns site builds. The MCP server owns data operations.**

When both processes run simultaneously, they share `.hyperspace/`. The coordination protocol:

1. The desktop app writes `.hypervisor/.app_running` on startup, deletes on shutdown
2. `trigger_site_build()` checks for this file — if present, it returns immediately (the desktop watcher handles the rebuild with proper debouncing)
3. The MCP watcher only updates the in-memory index — it never writes to `site/`
4. `update_document` rejects `status="Complete"` for work items — callers must use `move_work_item()` to prevent half-states (status changed but file not moved)

This eliminates the class of bugs where two concurrent builds fight over output files on Windows.

### One-Call Context Delivery

`session_brief` and `context_for_work_item` are designed to replace chains of file reads. One tool call delivers everything the AI needs to understand the current state or a specific work item — reducing context consumption and speeding up session starts.

### Similarity Without Embeddings

`similar_documents` uses a three-signal composite score (title fuzzy match + tag Jaccard + content token Jaccard) instead of vector embeddings. This keeps the server dependency-light and fast enough for synchronous tool calls (~50ms for 165 docs).

## Extending the Server

### Adding a New Tool

1. Create or extend a module in `hv_mcp/` with the implementation function
2. Import it in `mcp-server.py`
3. Add a `@server.tool(name="tool_name")` wrapper function with full docstring
4. Add the tool name to `autoApprove` in the MCP config
5. Restart the MCP server (or reconnect from Kiro's MCP panel)

### Adding a New Document Type

1. Create a markdown template in `.hyperspace/templates/` (e.g., `my-type-template.md`) — this is the human-readable format reference
2. Add a programmatic template generator in `hv_mcp/templates.py` that produces the same structure
3. Add the type to the `create_document` routing logic in `hv_mcp/crud.py`
4. Add the target directory mapping in `hv_mcp/config.py` (`TYPE_DIRECTORIES`)
5. Update `_infer_doc_type` in `hv_mcp/index.py` for the new type

Both the markdown template and the Python generator must stay in sync — the template is the source of truth for format, and the generator reproduces it programmatically.

### Adding a Validation Rule

1. Add the check to `validate_single()` in `hv_mcp/validation.py`
2. Use a unique `rule` name (kebab-case, e.g. `metadata-missing-project`)
3. Include `message` (human-readable) and `line` (line number or None)
4. Consider whether `migrate_document` should auto-fix the new rule

## Related

- `README.md` — Hypervisor project overview and quick start
- `architecture.md` — Build pipeline and static site generation
- `configuration.md` — Dependencies and configuration constants
