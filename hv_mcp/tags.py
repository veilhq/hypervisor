"""
Tag registry tools: get_tags, add_tag.
"""

import re
from difflib import get_close_matches

from .config import load_tags, save_tags
from .index import get_index_lock


def get_tags() -> dict:
    """Get the canonical tag registry with usage counts."""
    registry = load_tags()

    # Import deferred to avoid circular
    from .index import _index as index_list

    with get_index_lock():
        tag_counts: dict[str, int] = {}
        for entry in index_list:
            for tag in entry.get("tags", []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        total_docs = len(index_list)

    tags_list = []
    for name, meta in sorted(registry.items()):
        tags_list.append({
            "name": name,
            "category": meta.get("category", "uncategorized") if isinstance(meta, dict) else "uncategorized",
            "description": meta.get("description") if isinstance(meta, dict) else meta,
            "count": tag_counts.get(name, 0),
        })

    return {"tags": tags_list, "total_documents": total_docs}


def add_tag(
    name: str,
    category: str,
    description: str | None = None,
) -> dict:
    """Add a new tag to the canonical registry."""
    # Validate naming
    if name != name.lower():
        return {"error": f"Tag must be lowercase. Got: '{name}'"}
    if not re.match(r'^[a-z0-9]+(-[a-z0-9]+)*$', name):
        return {"error": f"Tag must be kebab-case (lowercase alphanumeric with hyphens). Got: '{name}'"}
    if category not in ("application", "technology", "domain"):
        return {"error": f"Category must be one of: application, technology, domain. Got: '{category}'"}

    registry = load_tags()

    # Check for duplicates
    if name in registry:
        return {"error": f"Tag '{name}' already exists in the registry."}
    close = get_close_matches(name, list(registry.keys()), n=3, cutoff=0.7)
    if close:
        return {
            "error": f"Tag '{name}' is too similar to existing tags: {close}. Use an existing tag or pick a more distinct name.",
        }

    # Persist
    registry[name] = {"category": category, "description": description}
    save_tags(registry)

    return {"success": True, "tag": {"name": name, "category": category, "description": description}}
