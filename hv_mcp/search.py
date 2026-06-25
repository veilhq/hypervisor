"""
Search and retrieval tools: search_hyperspace, recent_activity, get_work_items.
"""

from datetime import datetime, timedelta

from .index import get_index_lock


def _get_index_snapshot():
    """Get a snapshot of the index (import-deferred to avoid circular)."""
    from .index import _index
    return _index


def search_hyperspace(
    query: str = "",
    tags: list[str] | None = None,
    type: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Search hyperspace documents by text, tags, and/or type."""
    with get_index_lock():
        results = list(_get_index_snapshot())

    # Filter by type
    if type:
        results = [e for e in results if e["type"] == type]

    # Filter by tags (AND logic)
    if tags:
        tag_set = set(t.lower() for t in tags)
        results = [e for e in results if tag_set.issubset(set(e.get("tags", [])))]

    # Filter by text query
    if query:
        q = query.lower()
        scored = []
        for e in results:
            title_match = q in e.get("title", "").lower()
            desc_match = q in e.get("description", "").lower()
            snippet_match = q in e.get("snippet", "").lower()
            if title_match or desc_match or snippet_match:
                score = (3 if title_match else 0) + (2 if desc_match else 0) + (1 if snippet_match else 0)
                scored.append((score, e))
        scored.sort(key=lambda x: x[0], reverse=True)
        results = [e for _, e in scored]

    return results[:limit]


def recent_activity(days: int = 7) -> list[dict]:
    """Get recently created or updated documents."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")

    with get_index_lock():
        results = []
        for e in _get_index_snapshot():
            best_date = e.get("updated") or e.get("created")
            if best_date and best_date >= cutoff:
                results.append(e)

    results.sort(key=lambda e: e.get("updated") or e.get("created") or "", reverse=True)
    return results


def get_work_items(
    status: str | None = None,
    tags: list[str] | None = None,
    project: str | None = None,
) -> list[dict]:
    """Get work items, optionally filtered by status, tags, and/or project."""
    with get_index_lock():
        results = [e for e in _get_index_snapshot() if e["type"] == "work-item"]

    if status:
        results = [e for e in results if e.get("status") == status]

    if project:
        results = [e for e in results if e.get("project") == project]

    if tags:
        tag_set = set(t.lower() for t in tags)
        results = [e for e in results if tag_set.issubset(set(e.get("tags", [])))]

    results.sort(key=lambda e: e.get("title", "").lower())
    return results
