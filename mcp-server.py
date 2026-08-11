"""
Hypervisor MCP Server — Convention as Code.

Entry point that registers all tools with FastMCP and starts the server.
All logic lives in the `mcp/` package submodules.

Architecture:
    Kiro ←→ MCP Protocol (stdio) ←→ this file ←→ mcp/ package ←→ .hyperspace/
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — ensure mcp package and site_utils are importable
# ---------------------------------------------------------------------------
_THIS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_THIS_DIR))

# ---------------------------------------------------------------------------
# Structured logging (shared ecosystem logger)
# ---------------------------------------------------------------------------
_HYPERSPACE_ROOT = _THIS_DIR.parent
sys.path.insert(0, str(_HYPERSPACE_ROOT / ".hyperkit" / "python"))
from hyper_logging import setup_logger  # noqa: E402

logger = setup_logger("mcp-server")

from mcp.server.fastmcp import FastMCP

# Import submodules
from hv_mcp.index import rebuild_index, start_watcher
from hv_mcp.index_file import regenerate_index_file
from hv_mcp.search import search_hyperspace, recent_activity, get_work_items
from hv_mcp.rag import get_rag
from hv_mcp.tags import get_tags, add_tag
from hv_mcp.validation import validate_single, validate_all
from hv_mcp.claims import validate_work_item_claims
from hv_mcp.crud import create_document, update_document, move_work_item
from hv_mcp.analytics import stale_documents, health_report, tag_analytics
from hv_mcp.intelligence import session_brief, suggest_next_action, context_for_work_item
from hv_mcp.migration import migrate_document, get_schema_changelog
from hv_mcp.generation import suggest_tags, similar_documents, outline_work_item
from hv_mcp.launcher import launch_hypervisor


# ---------------------------------------------------------------------------
# MCP Server Definition
# ---------------------------------------------------------------------------

server = FastMCP(
    "hypervisor",
    instructions=(
        "Hyperspace convention-as-code server. Provides tools for creating, "
        "searching, validating, and managing hyperspace documents with guaranteed "
        "structural correctness. All document operations enforce tag validation, "
        "project validation, status transitions, and template compliance."
    ),
)


# ---------------------------------------------------------------------------
# Tool Registration — Search & Retrieval
# ---------------------------------------------------------------------------

@server.tool(name="search_hyperspace")
def search_hyperspace_tool(
    query: str = "",
    tags: list[str] | None = None,
    type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search hyperspace documents by text, tags, and/or type.

    Args:
        query: Text to search in titles, descriptions, and snippets (optional).
        tags: Filter by tags — results must contain ALL specified tags (optional).
        type: Filter by document type: work-item, idea, research, context, pattern, etc. (optional).
        limit: Maximum results to return (default 20).

    Returns:
        Structured list of matching documents with path, title, tags, dates, type, status, snippet.
    """
    return search_hyperspace(query=query, tags=tags, type=type, limit=limit)


@server.tool(name="recent_activity")
def recent_activity_tool(days: int = 7) -> list[dict]:
    """Get recently created or updated documents.

    Args:
        days: Number of days to look back (default 7).

    Returns:
        Documents sorted by most recent activity (updated or created date).
    """
    return recent_activity(days=days)


@server.tool(name="get_work_items")
def get_work_items_tool(
    status: str | None = None,
    tags: list[str] | None = None,
    project: str | None = None,
) -> list[dict]:
    """Get work items, optionally filtered by status, tags, and/or project.

    Args:
        status: Filter by status (Planned, In Progress, Complete). Optional.
        tags: Filter by tags — results must contain ALL specified tags. Optional.
        project: Filter by project name. Optional.

    Returns:
        Work item summaries with path, title, status, tags, project, dates, and work_id (e.g., 'WI-23').
    """
    return get_work_items(status=status, tags=tags, project=project)


@server.tool(name="semantic_search")
def semantic_search_tool(
    query: str,
    top_k: int = 5,
    tags: list[str] | None = None,
    doc_type: str | None = None,
    project: str | None = None,
    source_type: str | None = None,
) -> list[dict] | dict:
    """Search hyperspace documents by meaning — finds conceptually related
    content even when exact keywords don't match. Use this when looking for
    'how does X work', 'what was decided about Y', or 'anything related to Z'.
    Use search_hyperspace instead for exact tag/title filtering.

    Hybrid retrieval: dense embedding similarity (sqlite-vec) fused with keyword
    search (FTS5) via Reciprocal Rank Fusion, then MMR-reranked for diversity.

    Args:
        query: Natural language question or topic to search for.
        top_k: Maximum results to return (default 5).
        tags: Filter by tags — results must contain ALL specified tags (optional).
        doc_type: Filter by document type: work-item, idea, research, context, etc. (optional).
        project: Filter by project name (optional).
        source_type: Filter by source type: 'doc' (authored docs) or 'kb' (agent knowledge bank) (optional).

    Returns:
        List of matching chunks with: content, path, title, section, similarity
        score, doc_type, tags, updated date. Results are ordered by fused
        relevance with diversity enforced.
    """
    rag = get_rag()
    return rag.search(
        query=query,
        top_k=top_k,
        tags=tags,
        doc_type=doc_type,
        project=project,
        source_type=source_type,
    )


# ---------------------------------------------------------------------------
# Tool Registration — Tags
# ---------------------------------------------------------------------------

@server.tool(name="get_tags")
def get_tags_tool() -> dict:
    """Get the canonical tag registry with usage counts.

    Returns:
        Dictionary with 'tags' list (name, category, description, count) and 'total_documents'.
    """
    return get_tags()


@server.tool(name="add_tag")
def add_tag_tool(
    name: str,
    category: str,
    description: str | None = None,
) -> dict:
    """Add a new tag to the canonical registry.

    Args:
        name: Tag name (must be lowercase, kebab-case, no duplicates).
        category: One of: application, technology, domain.
        description: Optional description of what this tag refers to.

    Returns:
        Confirmation with the tag details, or error if validation fails.
    """
    return add_tag(name=name, category=category, description=description)


# ---------------------------------------------------------------------------
# Tool Registration — Validation
# ---------------------------------------------------------------------------

@server.tool(name="validate_document")
def validate_document_tool(path: str = "") -> dict:
    """Validate a hyperspace document (or all documents) against conventions.

    Args:
        path: Relative path to a document, or "all" to validate everything.
              Empty string also triggers batch validation.

    Returns:
        Violations with rule names, messages, and line numbers. For batch mode,
        returns a summary with totals and top issues.
    """
    if path == "" or path == "all":
        return validate_all()
    return validate_single(path)


@server.tool(name="validate_work_item_claims")
def validate_work_item_claims_tool(slug: str, apply_updates: bool = False) -> dict:
    """Sweep a work item's claims against the actual codebase and surface gaps.

    Checks file/line references in Implementation Notes, Tasks, and Acceptance
    Criteria against the real repos (resolved from paths like
    'cyber-portal/api/apps/views.py' relative to the workspace root). Detects
    missing files, stale line references, and lines that likely drifted from
    edits. Also flags unchecked tasks whose described behavior already appears
    to exist in the codebase, as an open question for human review.

    This is heuristic pattern-matching against source, not proof — it never
    auto-completes a task or removes an acceptance criterion. Findings are
    always advisory. Defaults to dry-run (apply_updates=False); pass True to
    write findings into the document's Implementation Notes section.

    Args:
        slug: The filename (without .md) of the work item in work/to-do/ or
              work/done/, OR a work item ID (e.g., 'WI-23').
        apply_updates: If True, write findings into Implementation Notes and
                       bump Updated. Defaults to False (review before writing).

    Returns:
        When clean: {"clean": True, "message": ..., "claims_checked": N}.
        When gaps found: findings grouped by category (file_missing, gaps,
        line_moved, possibly_done_tasks), a summary count, and either a
        diff_preview (dry-run) or confirmation of the applied write.
    """
    return validate_work_item_claims(slug=slug, apply_updates=apply_updates)


# ---------------------------------------------------------------------------
# Tool Registration — CRUD
# ---------------------------------------------------------------------------

@server.tool(name="create_document")
def create_document_tool(
    type: str,
    title: str,
    tags: list[str],
    description: str = "",
    project: str | None = None,
    doc_type: str = "Professional",
    directory: str | None = None,
    overview: str | None = None,
    design: str | None = None,
    acceptance_criteria: dict | None = None,
    tasks: list[str] | None = None,
    open_questions: list[str] | None = None,
    concept: str | None = None,
    key_questions: list[str] | None = None,
    content: str | None = None,
    related: list[str] | None = None,
    solution_plan: str | None = None,
    number: int | None = None,
    context_text: str | None = None,
    decision: str | None = None,
    rationale: str | None = None,
    consequences: str | None = None,
    severity: str | None = None,
    affected: str | None = None,
    problem: str | None = None,
    root_cause: str | None = None,
    fix: str | None = None,
    testing: str | None = None,
    recommendations: str | None = None,
) -> dict:
    """Create a new hyperspace document with full convention enforcement.

    Args:
        type: Document type — work-item, idea, document, adr, bugfix.
        title: Document title.
        tags: List of tags (validated against canonical registry).
        description: One-liner description (shown under H1 and in index).
        project: Project name (required for work-items, validated against registry).
        doc_type: Personal or Professional (default Professional).
        directory: Target subdirectory (required for type='document', e.g. 'research/rbac', 'context').
        overview: User story / overview text (required for work-items).
        design: Technical design content (optional, work-items).
        acceptance_criteria: Dict of {section_name: [criteria_list]} (optional, work-items).
        tasks: List of task descriptions (optional, work-items).
        open_questions: List of unresolved implementation questions — scoping ambiguities,
            decisions that need to be made before coding starts (optional, work-items).
            Rendered under Implementation Notes so they're visible before work begins.
        concept: Freeform concept text (required for ideas).
        key_questions: List of open questions to explore (optional, ideas).
        solution_plan: High-level approach or implementation sketch (optional, ideas).
        content: Main content body (required for type='document').
        related: List of markdown links to related docs (optional).
        number: ADR number (required for type='adr').
        context_text: ADR context section (required for type='adr').
        decision: ADR decision statement (required for type='adr').
        rationale: ADR rationale (required for type='adr').
        consequences: ADR consequences (optional).
        severity: Bug severity — Low, Medium, High, Critical (required for bugfix).
        affected: Affected component/path (required for bugfix).
        problem: Problem description — what's broken or missing (optional for ideas, required for bugfix).
        root_cause: Root cause analysis (required for bugfix).
        fix: Fix description (required for bugfix).
        testing: Testing steps (optional, bugfix).
        recommendations: Additional recommendations (optional, bugfix).

    Returns:
        Created file path and confirmation, or error details.
    """
    return create_document(
        type=type, title=title, tags=tags, description=description,
        project=project, doc_type=doc_type, directory=directory,
        overview=overview, design=design, acceptance_criteria=acceptance_criteria,
        tasks=tasks, open_questions=open_questions, concept=concept, key_questions=key_questions,
        content=content, related=related, solution_plan=solution_plan,
        number=number, context_text=context_text, decision=decision,
        rationale=rationale, consequences=consequences,
        severity=severity, affected=affected, problem=problem,
        root_cause=root_cause, fix=fix, testing=testing,
        recommendations=recommendations,
    )


@server.tool(name="update_document")
def update_document_tool(
    path: str,
    status: str | None = None,
    tags: list[str] | None = None,
    project: str | None = None,
    doc_type: str | None = None,
) -> dict:
    """Update metadata fields on an existing document.

    Only the fields passed will be changed. Always bumps 'Updated' timestamp.
    Validates status transitions, tags, and project names.

    Args:
        path: Relative path to the document (e.g., 'work/to-do/my-item.md').
        status: New status value (validates transition from current).
        tags: New tag list (replaces existing, validated against registry).
        project: New project name (validated against registry).
        doc_type: New Type value (Personal or Professional).

    Returns:
        Confirmation with updated fields, or error.
    """
    return update_document(path=path, status=status, tags=tags, project=project, doc_type=doc_type)


@server.tool(name="move_work_item")
def move_work_item_tool(slug: str) -> dict:
    """Move a work item from to-do to done (mark as complete).

    Atomically: sets status to Complete, moves file to done/, rewrites backlinks,
    and regenerates _index.md.

    Args:
        slug: The filename (without .md) of the work item in work/to-do/,
              OR a work item ID (e.g., 'WI-23').

    Returns:
        Confirmation with new path and any updated backlinks.
    """
    return move_work_item(slug=slug)


# ---------------------------------------------------------------------------
# Tool Registration — Phase 2: Analytics & Health
# ---------------------------------------------------------------------------

@server.tool(name="stale_documents")
def stale_documents_tool(days: int = 30) -> dict:
    """Get documents not updated within the given window, grouped by type.

    Args:
        days: Number of days without updates to consider "stale" (default 30).

    Returns:
        Documents grouped by type with title, path, last activity date, and days stale.
    """
    return stale_documents(days=days)


@server.tool(name="health_report")
def health_report_tool() -> dict:
    """Run validation and return current health with trend comparison.

    Runs a full validation pass, records a health snapshot, then compares
    against the previous snapshot to determine trend direction.

    Returns:
        Current stats, previous snapshot, trend, docs added, and top remaining issues.
    """
    return health_report()


@server.tool(name="tag_analytics")
def tag_analytics_tool() -> dict:
    """Analyze tag usage patterns: co-occurrence, underused tags, merge candidates.

    Returns:
        Summary stats, top co-occurring tag pairs, underused tags, merge candidates,
        and orphaned tags (used in docs but not in registry).
    """
    return tag_analytics()


# ---------------------------------------------------------------------------
# Tool Registration — Phase 2: Smart Context
# ---------------------------------------------------------------------------

@server.tool(name="session_brief")
def session_brief_tool(project: str | None = None) -> dict:
    """Get a curated session context summary for starting a productive session.

    Returns active work items (with task progress), recent non-work activity,
    stale items that may need attention, and recent completions.

    Args:
        project: Filter to a specific project (optional). If None, returns cross-project view.

    Returns:
        Structured summary with active_work, recent_activity, stale_items,
        recent_completions, planned_items, and summary counts.
    """
    return session_brief(project=project)


@server.tool(name="suggest_next_action")
def suggest_next_action_tool() -> dict:
    """Analyze work landscape and suggest prioritized next actions.

    Identifies:
    - Work items with all tasks done (ready to complete)
    - Items In Progress but untouched 7+ days (possibly blocked)
    - Items with partial progress but stale (ready to resume)
    - Ideas with sufficient research (ready to promote)
    - Planned items with related research (ready to start)

    Returns:
        Prioritized list of suggestions with action type, reasoning, and paths.
    """
    return suggest_next_action()


@server.tool(name="context_for_work_item")
def context_for_work_item_tool(slug: str) -> dict:
    """Get a work item plus all linked and related documents in one call.

    Traverses the backlink graph and tag relationships to deliver full context
    as a structured package — replacing 5-8 individual file reads.

    Args:
        slug: The filename (without .md) of the work item, OR a work item ID (e.g., 'WI-23').
              Searches both to-do/ and done/.

    Returns:
        Work item content, outlinked docs, backlinks, related-by-tags docs, and stats.
    """
    return context_for_work_item(slug=slug)


# ---------------------------------------------------------------------------
# Tool Registration — Phase 2: Template Evolution & Migration
# ---------------------------------------------------------------------------

@server.tool(name="migrate_document")
def migrate_document_tool(path: str = "all", dry_run: bool = True) -> dict:
    """Migrate documents to current schema conventions.

    Applies non-destructive fixes to document metadata:
    - Renames 'Date:' → 'Created:'
    - Converts bold metadata (**Key:**) to dash-prefixed format
    - Adds missing 'Updated:' field (defaults to Created value)
    - Adds missing 'Created:' from file timestamp
    - Normalizes dates to YYYY-MM-DDTHH:MM format
    - Reorders metadata to canonical order

    Never modifies content sections — only structural metadata.

    Args:
        path: Relative path to a document, or "all" for batch mode. Default "all".
        dry_run: If True, preview changes without writing. Default True.

    Returns:
        Single mode: changes list and old/new metadata diff.
        Batch mode: summary counts, change breakdown, and per-file results.
    """
    return migrate_document(path=path, dry_run=dry_run)


@server.tool(name="get_schema_changelog")
def get_schema_changelog_tool() -> dict:
    """Get the schema changelog showing when conventions changed.

    Returns:
        Version history with dates and changes, current conventions, and canonical field order.
    """
    return get_schema_changelog()


# ---------------------------------------------------------------------------
# Tool Registration — Phase 2: Content Generation
# ---------------------------------------------------------------------------

@server.tool(name="suggest_tags")
def suggest_tags_tool(content: str) -> dict:
    """Suggest tags from the registry based on content analysis.

    Analyzes text against tag keywords, descriptions, and synonym mappings
    to produce confidence-ranked suggestions from the canonical registry.

    Args:
        content: Text to analyze — can be a title, description, or body content.

    Returns:
        Ranked tag suggestions with confidence scores (0-1) and matching reasons.
    """
    return suggest_tags(content=content)


@server.tool(name="similar_documents")
def similar_documents_tool(title: str, content: str | None = None) -> dict:
    """Find existing documents that overlap with a proposed new document.

    Uses three signals: title fuzzy match, tag overlap, and content token overlap.
    Returns a recommendation: proceed, review_existing, or likely_duplicate.

    Args:
        title: Proposed document title.
        content: Optional body content for deeper comparison.

    Returns:
        Similar documents with similarity scores and a clear recommendation.
    """
    return similar_documents(title=title, content=content)


@server.tool(name="outline_work_item")
def outline_work_item_tool(description: str) -> dict:
    """Generate a structured work item outline from freeform text.

    Produces suggested title, tags, project, overview (user story), acceptance
    criteria stubs, and task stubs — ready for review before create_document.

    Args:
        description: Freeform text describing what needs to be built or fixed.

    Returns:
        Complete structured outline with suggestions and similar existing docs.
    """
    return outline_work_item(description=description)


# ---------------------------------------------------------------------------
# Tool Registration — App Launcher
# ---------------------------------------------------------------------------

@server.tool(name="launch_hypervisor")
def launch_hypervisor_tool() -> dict:
    """Launch the Hypervisor desktop app (PyWebView).

    Checks if the app is already running. If not, starts it as a detached
    subprocess. The app performs a full site build on startup automatically.

    Returns:
        Status message indicating whether the app was launched or was already running.
    """
    return launch_hypervisor()


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

def _startup():
    """Initialize the in-memory search index and file watcher.

    Called once regardless of transport mode. For HTTP mode this runs before
    the uvicorn server starts accepting connections. RAG engine loading is
    deferred to a background thread so the server starts accepting connections
    immediately — the embedding model loads on first use or shortly after boot.
    """
    logger.info("initializing search index and file watcher")
    rebuild_index()
    start_watcher()
    logger.info("index and watcher ready")


def _warm_rag_background():
    """Load the RAG engine on a background thread after the server is up.

    This ensures the first semantic_search doesn't pay the full model-load
    cost, but doesn't block server startup.
    """
    import threading

    def _run():
        try:
            logger.info("background: loading RAG engine and reindexing")
            _rag_instance = get_rag()
            result = _rag_instance.reindex_changed()
            indexed = result.get("documents_indexed", 0) if isinstance(result, dict) else 0
            logger.info("background: RAG ready — %d docs reindexed", indexed)
        except Exception as exc:
            logger.error("background: RAG init failed: %s", exc)

    t = threading.Thread(target=_run, daemon=True, name="rag-warmup")
    t.start()


# ---------------------------------------------------------------------------
# Service Lock — allows Hypervisor/Hyperagent to discover a running instance
# ---------------------------------------------------------------------------

_SERVICE_LOCK = _THIS_DIR / ".mcp_service_running"


def _write_service_lock(port: int):
    """Write a lock file with PID and port so other apps can find us."""
    import os
    _SERVICE_LOCK.write_text(
        f"{os.getpid()}\n{port}\n", encoding="utf-8"
    )


def _remove_service_lock():
    """Clean up the lock file on shutdown."""
    try:
        _SERVICE_LOCK.unlink(missing_ok=True)
    except OSError:
        pass


def _is_service_running() -> tuple[bool, int | None]:
    """Check if a shared MCP service is already running.

    Returns:
        (is_running, port) — port is None if not running.
    """
    if not _SERVICE_LOCK.exists():
        return False, None
    try:
        lines = _SERVICE_LOCK.read_text(encoding="utf-8").strip().split("\n")
        pid = int(lines[0])
        port = int(lines[1])
        # Verify the process is alive (Windows)
        import ctypes
        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            kernel32.CloseHandle(handle)
            return True, port
        # Stale lock
        _SERVICE_LOCK.unlink(missing_ok=True)
        return False, None
    except (ValueError, OSError, IndexError):
        _SERVICE_LOCK.unlink(missing_ok=True)
        return False, None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

_DEFAULT_PORT = 8321


if __name__ == "__main__":
    import argparse
    import atexit

    parser = argparse.ArgumentParser(description="Hypervisor MCP Server")
    parser.add_argument(
        "--http", action="store_true",
        help="Run as a shared streamable-http service instead of stdio",
    )
    parser.add_argument(
        "--port", type=int, default=_DEFAULT_PORT,
        help=f"Port for HTTP mode (default: {_DEFAULT_PORT})",
    )
    args = parser.parse_args()

    if args.http:
        # Route uvicorn logs into our ecosystem log file
        import logging
        uvi_logger = logging.getLogger("uvicorn")
        uvi_logger.handlers = logger.handlers
        uvi_logger.setLevel(logging.INFO)
        logging.getLogger("uvicorn.access").handlers = logger.handlers
        logging.getLogger("uvicorn.access").setLevel(logging.INFO)
        logging.getLogger("uvicorn.error").handlers = logger.handlers
        logging.getLogger("uvicorn.error").setLevel(logging.INFO)

        # Check if already running
        running, existing_port = _is_service_running()
        if running:
            logger.error(
                "MCP service already running on port %d — exiting", existing_port
            )
            print(
                f"Hypervisor MCP service already running on port {existing_port}. "
                "Stop the existing instance first.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Reconfigure server for HTTP transport
        server.settings.host = "127.0.0.1"
        server.settings.port = args.port

        # Write lock EARLY so other apps (Hyperagent) see us immediately
        # and don't launch a competing instance during our init time.
        _write_service_lock(args.port)
        atexit.register(_remove_service_lock)

        # Initialize before accepting connections
        logger.info("starting in HTTP mode on port %d", args.port)
        _startup()

        # Warm the RAG engine in background — server accepts connections immediately
        _warm_rag_background()

        logger.info("accepting connections on http://127.0.0.1:%d/mcp", args.port)
        print(f"Hypervisor MCP service starting on http://127.0.0.1:{args.port}/mcp")
        server.run(transport="streamable-http")
    else:
        # Legacy stdio mode — backward compatible, RAG must be ready before
        # tool calls arrive since there's no concurrent connection model
        logger.info("starting in stdio mode")
        _startup()
        logger.info("loading RAG engine (stdio — synchronous)")
        _rag_instance = get_rag()
        _rag_instance.reindex_changed()
        logger.info("RAG ready, serving")
        server.run(transport="stdio")
