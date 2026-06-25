"""
Hypervisor MCP Server — modular package (hv_mcp).

Submodules:
    config      — paths, constants, registries
    index       — in-memory index, rebuild, refresh, watcher
    backlinks   — backlink graph (eager build, incremental updates)
    dates       — date parsing utilities
    health      — health history snapshot storage
    helpers     — slug generation, validation helpers, backlink rewriting
    templates   — document template generators
    validation  — validate_document (single + batch)
    crud        — create_document, update_document, move_work_item
    search      — search_hyperspace, recent_activity, get_work_items
    tags        — get_tags, add_tag
    analytics   — stale_documents, health_report, tag_analytics
    intelligence — session_brief, suggest_next_action, context_for_work_item
    migration   — migrate_document, get_schema_changelog
    generation  — suggest_tags, similar_documents, outline_work_item
"""
