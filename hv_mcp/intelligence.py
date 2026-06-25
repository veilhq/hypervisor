"""
Phase 2 Smart Context tools: session_brief, suggest_next_action, context_for_work_item.

These tools traverse the in-memory index and backlink graph to deliver
full context in single calls — replacing multiple file reads with one structured response.
"""

from datetime import datetime, timedelta
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT

from .backlinks import get_backlinks_for, get_outlinks_for
from .dates import parse_date, days_since, best_activity_date
from .index import get_index_lock


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Minimum shared tags to consider documents "related"
RELATED_TAG_THRESHOLD = 2

# Days thresholds for staleness heuristics
STALE_IN_PROGRESS_DAYS = 7
RECENT_COMPLETION_DAYS = 14
RECENT_DECISION_DAYS = 14


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_index_snapshot() -> list[dict]:
    """Thread-safe snapshot of the in-memory index."""
    from .index import _index
    with get_index_lock():
        return list(_index)


def _read_file_content(rel_path: str) -> str | None:
    """Read a hyperspace file's content by relative path."""
    full = HYPERSPACE_ROOT / rel_path.replace("/", "\\")
    if not full.exists():
        return None
    try:
        return full.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _count_tasks(content: str) -> tuple[int, int]:
    """Count total and completed tasks (checkboxes) in markdown content.

    Returns:
        (total_tasks, completed_tasks)
    """
    total = 0
    completed = 0
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- [x]") or stripped.startswith("- [X]"):
            total += 1
            completed += 1
        elif stripped.startswith("- [ ]"):
            total += 1
    return total, completed


def _humanize_age(date_str: str | None) -> str:
    """Convert a date string to a human-friendly relative age."""
    age = days_since(date_str)
    if age is None:
        return "unknown"
    if age == 0:
        return "today"
    if age == 1:
        return "yesterday"
    if age < 7:
        return f"{age} days ago"
    if age < 30:
        weeks = age // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    months = age // 30
    return f"{months} month{'s' if months > 1 else ''} ago"


def _entry_summary(entry: dict, extras: dict | None = None) -> dict:
    """Build a compact summary dict from an index entry."""
    summary = {
        "title": entry.get("title", ""),
        "path": entry.get("path", ""),
        "status": entry.get("status"),
        "tags": entry.get("tags", []),
        "project": entry.get("project"),
    }
    if extras:
        summary.update(extras)
    return summary


# ---------------------------------------------------------------------------
# session_brief
# ---------------------------------------------------------------------------

def session_brief(project: str | None = None) -> dict:
    """Return a curated session context summary.

    Provides active work, recent decisions/research, stale items, and
    recent completions — everything needed to start a productive session.

    Args:
        project: Filter to a specific project (optional). If None, returns cross-project view.

    Returns:
        Structured summary with active_work, recent_activity, stale_items, recent_completions.
    """
    entries = _get_index_snapshot()

    # Apply project filter if specified
    if project:
        entries = [e for e in entries if e.get("project") == project]

    now = datetime.now()

    # --- Active work (In Progress work items) ---
    active_work = []
    for entry in entries:
        if entry.get("type") != "work-item":
            continue
        if entry.get("status") != "In Progress":
            continue

        # Read content to count tasks
        content = _read_file_content(entry["path"])
        total_tasks, completed_tasks = (0, 0)
        if content:
            total_tasks, completed_tasks = _count_tasks(content)

        active_work.append({
            "title": entry.get("title", ""),
            "path": entry.get("path", ""),
            "project": entry.get("project"),
            "tags": entry.get("tags", []),
            "last_touched": _humanize_age(best_activity_date(entry)),
            "tasks_total": total_tasks,
            "tasks_completed": completed_tasks,
            "tasks_remaining": total_tasks - completed_tasks,
        })

    # Sort by most recently touched
    active_work.sort(
        key=lambda x: parse_date(
            best_activity_date(
                next((e for e in entries if e.get("path") == x["path"]), {})
            )
        ) or datetime.min,
        reverse=True,
    )

    # --- Recent activity (non-work-item docs updated in last 14 days) ---
    recent_cutoff = (now - timedelta(days=RECENT_DECISION_DAYS)).strftime("%Y-%m-%dT%H:%M")
    recent_items = []
    for entry in entries:
        if entry.get("type") == "work-item":
            continue
        activity = best_activity_date(entry)
        if activity and activity >= recent_cutoff:
            recent_items.append({
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "type": entry.get("type", "document"),
                "date": activity,
                "age": _humanize_age(activity),
            })
    recent_items.sort(key=lambda x: x.get("date", ""), reverse=True)
    recent_items = recent_items[:10]  # Cap at 10

    # --- Stale items (In Progress but untouched for 7+ days) ---
    stale_items = []
    for entry in entries:
        if entry.get("type") != "work-item":
            continue
        if entry.get("status") != "In Progress":
            continue
        activity = best_activity_date(entry)
        age = days_since(activity)
        if age is not None and age >= STALE_IN_PROGRESS_DAYS:
            stale_items.append({
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "days_untouched": age,
                "project": entry.get("project"),
            })
    stale_items.sort(key=lambda x: x["days_untouched"], reverse=True)

    # --- Recent completions (work items in done/ completed in last 14 days) ---
    recent_completions = []
    for entry in entries:
        if entry.get("type") != "work-item":
            continue
        if entry.get("status") != "Complete":
            continue
        activity = best_activity_date(entry)
        if activity and activity >= recent_cutoff:
            recent_completions.append({
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "completed": activity,
            })
    recent_completions.sort(key=lambda x: x.get("completed", ""), reverse=True)

    # --- Planned items (queued for future work) ---
    planned = []
    for entry in entries:
        if entry.get("type") != "work-item":
            continue
        if entry.get("status") != "Planned":
            continue
        planned.append({
            "title": entry.get("title", ""),
            "path": entry.get("path", ""),
            "project": entry.get("project"),
            "tags": entry.get("tags", []),
        })

    return {
        "project_filter": project,
        "active_work": active_work,
        "recent_activity": recent_items,
        "stale_items": stale_items,
        "recent_completions": recent_completions,
        "planned_items": planned[:10],  # Cap
        "summary": {
            "active_count": len(active_work),
            "stale_count": len(stale_items),
            "planned_count": len(planned),
            "recently_completed": len(recent_completions),
        },
    }


# ---------------------------------------------------------------------------
# suggest_next_action
# ---------------------------------------------------------------------------

def suggest_next_action() -> dict:
    """Analyze the work landscape and return prioritized action suggestions.

    Heuristics:
    - Work items with all tasks checked but still In Progress → "ready to complete"
    - Items In Progress for 7+ days with no tasks checked → "may be blocked"
    - Ideas with 3+ related research docs → "ready to promote"
    - Planned items with related research already done → "ready to start"

    Returns:
        Prioritized list of suggested actions with reasoning.
    """
    entries = _get_index_snapshot()
    suggestions: list[dict] = []

    work_items = [e for e in entries if e.get("type") == "work-item"]
    ideas = [e for e in entries if e.get("type") == "idea"]

    # --- Ready to complete: all tasks done but status still In Progress ---
    for entry in work_items:
        if entry.get("status") != "In Progress":
            continue
        content = _read_file_content(entry["path"])
        if not content:
            continue
        total, completed = _count_tasks(content)
        if total > 0 and completed == total:
            suggestions.append({
                "priority": 1,
                "action": "complete",
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "reason": f"All {total} tasks are checked. Ready to move to done/.",
                "command": f"move_work_item(slug='{Path(entry['path']).stem}')",
            })

    # --- May be blocked: In Progress 7+ days with no progress ---
    for entry in work_items:
        if entry.get("status") != "In Progress":
            continue
        activity = best_activity_date(entry)
        age = days_since(activity)
        if age is None or age < STALE_IN_PROGRESS_DAYS:
            continue
        content = _read_file_content(entry["path"])
        if not content:
            continue
        total, completed = _count_tasks(content)
        if total > 0 and completed == 0:
            suggestions.append({
                "priority": 2,
                "action": "review_blocked",
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "reason": f"In Progress for {age} days with 0/{total} tasks completed. May be blocked or forgotten.",
            })

    # --- Stale In Progress: untouched but has some progress ---
    for entry in work_items:
        if entry.get("status") != "In Progress":
            continue
        activity = best_activity_date(entry)
        age = days_since(activity)
        if age is None or age < STALE_IN_PROGRESS_DAYS:
            continue
        content = _read_file_content(entry["path"])
        if not content:
            continue
        total, completed = _count_tasks(content)
        # Already caught by "may be blocked" if completed == 0
        # Already caught by "ready to complete" if completed == total
        if total > 0 and 0 < completed < total:
            suggestions.append({
                "priority": 3,
                "action": "resume",
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "reason": f"In Progress for {age} days with {completed}/{total} tasks done. Consider resuming.",
            })

    # --- Ideas ready to promote: idea has 3+ related research docs by tags ---
    for idea in ideas:
        idea_tags = set(idea.get("tags", []))
        if len(idea_tags) < 1:
            continue
        related_research = [
            e for e in entries
            if e.get("type") == "research"
            and len(idea_tags & set(e.get("tags", []))) >= RELATED_TAG_THRESHOLD
        ]
        if len(related_research) >= 3:
            suggestions.append({
                "priority": 4,
                "action": "promote_idea",
                "title": idea.get("title", ""),
                "path": idea.get("path", ""),
                "reason": f"Has {len(related_research)} related research docs. Consider promoting to a work item.",
                "related_research": [r.get("title", "") for r in related_research[:5]],
            })

    # --- Planned items with related research (ready to start) ---
    for entry in work_items:
        if entry.get("status") != "Planned":
            continue
        entry_tags = set(entry.get("tags", []))
        if len(entry_tags) < 1:
            continue
        related_research = [
            e for e in entries
            if e.get("type") == "research"
            and len(entry_tags & set(e.get("tags", []))) >= RELATED_TAG_THRESHOLD
        ]
        if len(related_research) >= 2:
            suggestions.append({
                "priority": 5,
                "action": "start_work",
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "reason": f"Planned item with {len(related_research)} related research docs already done. Ready to begin.",
            })

    # Sort by priority (lower = more urgent)
    suggestions.sort(key=lambda x: x["priority"])

    return {
        "suggestions": suggestions,
        "total": len(suggestions),
        "summary": {
            "ready_to_complete": len([s for s in suggestions if s["action"] == "complete"]),
            "possibly_blocked": len([s for s in suggestions if s["action"] == "review_blocked"]),
            "ready_to_resume": len([s for s in suggestions if s["action"] == "resume"]),
            "promotable_ideas": len([s for s in suggestions if s["action"] == "promote_idea"]),
            "ready_to_start": len([s for s in suggestions if s["action"] == "start_work"]),
        },
    }


# ---------------------------------------------------------------------------
# context_for_work_item
# ---------------------------------------------------------------------------

def context_for_work_item(slug: str) -> dict:
    """Get a work item plus all linked and related documents as a structured package.

    Traverses the backlink graph and tag relationships to deliver full context
    in one call — replacing 5-8 file reads.

    Args:
        slug: The filename (without .md) of the work item, OR a work item ID (e.g., 'WI-23').
              Searches both to-do/ and done/.

    Returns:
        Work item content, linked docs, backlinks, and related-by-tags documents.
    """
    entries = _get_index_snapshot()

    # Check if slug is actually a work item ID (WI-N format)
    target_path = None
    target_entry = None
    if slug.upper().startswith("WI-"):
        for entry in entries:
            if entry.get("work_id") and entry["work_id"].upper() == slug.upper():
                target_path = entry["path"]
                target_entry = entry
                break
        if not target_entry:
            # Fallback: scan work files on disk (handles empty index / startup race)
            import re
            for subdir in ("work/to-do", "work/done"):
                dir_path = HYPERSPACE_ROOT / subdir.replace("/", "\\")
                if not dir_path.is_dir():
                    continue
                for md_file in dir_path.glob("*.md"):
                    try:
                        text = md_file.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        continue
                    for line in text.splitlines()[:30]:
                        stripped = line.strip().lstrip("- ")
                        m = re.match(r'ID\s*:\s*(WI-\d+)', stripped, re.IGNORECASE)
                        if m and m.group(1).upper() == slug.upper():
                            rel = f"{subdir}/{md_file.name}"
                            target_path = rel
                            # Build a minimal entry for context assembly
                            from .index import _build_index_entry
                            target_entry = _build_index_entry(Path(rel))
                            break
                    if target_entry:
                        break
                if target_entry:
                    break
        if not target_entry:
            return {"error": f"No work item found with ID '{slug}'."}
    else:
        # Find by slug (filename without .md)
        for candidate_dir in ("work/to-do", "work/done"):
            candidate = f"{candidate_dir}/{slug}.md"
            match = next((e for e in entries if e.get("path") == candidate), None)
            if match:
                target_path = candidate
                target_entry = match
                break

        if not target_entry:
            return {"error": f"Work item '{slug}' not found in work/to-do/ or work/done/."}

    # Read full content
    content = _read_file_content(target_path)
    total_tasks, completed_tasks = (0, 0)
    if content:
        total_tasks, completed_tasks = _count_tasks(content)

    # --- Outlinks: docs this work item links TO ---
    outlinks = get_outlinks_for(target_path)
    linked_docs: list[dict] = []
    for link_path in sorted(outlinks):
        linked_entry = next((e for e in entries if e.get("path") == link_path), None)
        if linked_entry:
            linked_docs.append({
                "path": link_path,
                "title": linked_entry.get("title", ""),
                "type": linked_entry.get("type", "document"),
                "tags": linked_entry.get("tags", []),
                "snippet": linked_entry.get("snippet", ""),
            })

    # --- Backlinks: docs that link TO this work item ---
    backlinks_set = get_backlinks_for(target_path)
    backlinks: list[dict] = []
    for bl_path in sorted(backlinks_set):
        bl_entry = next((e for e in entries if e.get("path") == bl_path), None)
        if bl_entry:
            backlinks.append({
                "path": bl_path,
                "title": bl_entry.get("title", ""),
                "type": bl_entry.get("type", "document"),
                "snippet": bl_entry.get("snippet", ""),
            })

    # --- Related by tags: docs sharing 2+ tags (excluding already-linked) ---
    target_tags = set(target_entry.get("tags", []))
    already_linked = outlinks | backlinks_set | {target_path}
    related_by_tags: list[dict] = []

    if len(target_tags) >= RELATED_TAG_THRESHOLD:
        for entry in entries:
            if entry.get("path") in already_linked:
                continue
            entry_tags = set(entry.get("tags", []))
            shared = target_tags & entry_tags
            if len(shared) >= RELATED_TAG_THRESHOLD:
                related_by_tags.append({
                    "path": entry.get("path", ""),
                    "title": entry.get("title", ""),
                    "type": entry.get("type", "document"),
                    "shared_tags": sorted(shared),
                    "snippet": entry.get("snippet", ""),
                })
        # Sort by number of shared tags (most overlap first)
        related_by_tags.sort(key=lambda x: len(x["shared_tags"]), reverse=True)
        related_by_tags = related_by_tags[:10]  # Cap

    return {
        "work_item": {
            "path": target_path,
            "title": target_entry.get("title", ""),
            "description": target_entry.get("description", ""),
            "status": target_entry.get("status"),
            "project": target_entry.get("project"),
            "tags": target_entry.get("tags", []),
            "created": target_entry.get("created"),
            "updated": target_entry.get("updated"),
            "tasks_total": total_tasks,
            "tasks_completed": completed_tasks,
            "content": content,
        },
        "linked_docs": linked_docs,
        "backlinks": backlinks,
        "related_by_tags": related_by_tags,
        "stats": {
            "outlinks": len(linked_docs),
            "backlinks": len(backlinks),
            "related": len(related_by_tags),
        },
    }
