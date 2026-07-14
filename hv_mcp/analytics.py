"""
Phase 2 Analytics & Health tools: stale_documents, health_report, tag_analytics.
"""

from datetime import datetime

from .dates import parse_date, days_since, best_activity_date
from .health import record_health_snapshot, get_latest_snapshot, get_previous_snapshot
from .index import get_index_lock
from .template_drift import check_template_drift
from .validation import validate_all


def stale_documents(days: int = 30) -> dict:
    """Get documents not updated within the given window, grouped by type.

    Args:
        days: Number of days without updates to consider "stale" (default 30).

    Returns:
        Documents grouped by type with title, path, last activity date, and days stale.
    """
    from .index import _index

    with get_index_lock():
        entries = list(_index)

    now = datetime.now()
    stale: dict[str, list[dict]] = {}

    for entry in entries:
        activity = best_activity_date(entry)
        dt = parse_date(activity)
        if dt is None:
            # No parseable date — skip (can't determine staleness)
            continue

        age = (now - dt).days
        if age >= days:
            doc_type = entry.get("type", "document")
            # Clean plural group key
            if doc_type.endswith("s"):
                group_key = f"stale_{doc_type}"
            elif doc_type.endswith("x"):
                group_key = f"stale_{doc_type}es"
            else:
                group_key = f"stale_{doc_type}s"
            stale.setdefault(group_key, []).append({
                "title": entry.get("title", ""),
                "path": entry.get("path", ""),
                "last_updated": activity,
                "days_stale": age,
                "status": entry.get("status"),
                "tags": entry.get("tags", []),
            })

    # Sort each group by staleness (most stale first)
    for key in stale:
        stale[key].sort(key=lambda x: x["days_stale"], reverse=True)

    total_stale = sum(len(v) for v in stale.values())
    return {
        "threshold_days": days,
        "total_stale": total_stale,
        **stale,
    }


def health_report() -> dict:
    """Run validation and return current health with trend comparison.

    Runs validate_all(), records a snapshot, then compares against
    the previous snapshot to determine trend direction.

    Returns:
        Current stats, previous snapshot, trend direction, and top remaining issues.
    """
    # Get previous snapshot BEFORE recording new one
    previous = get_latest_snapshot()

    # Run fresh validation
    current_result = validate_all()

    # Record this run as a new snapshot
    record_health_snapshot(current_result)

    # Determine trend
    trend = "unknown"
    if previous:
        prev_violation_rate = previous["violations"] / max(previous["total_documents"], 1)
        curr_violation_rate = current_result["violations"] / max(current_result["total_documents"], 1)

        if curr_violation_rate < prev_violation_rate:
            trend = "improving"
        elif curr_violation_rate > prev_violation_rate:
            trend = "declining"
        else:
            trend = "stable"

    # Compute docs added since last snapshot
    docs_added = 0
    if previous:
        docs_added = current_result["total_documents"] - previous["total_documents"]

    # Check template drift (markdown vs programmatic)
    drift_result = check_template_drift()

    return {
        "current": {
            "total": current_result["total_documents"],
            "valid": current_result["valid"],
            "violations": current_result["violations"],
            "skipped": current_result.get("skipped", 0),
        },
        "previous": {
            "total": previous["total_documents"],
            "valid": previous["valid"],
            "violations": previous["violations"],
            "timestamp": previous["timestamp"],
        } if previous else None,
        "trend": trend,
        "docs_added_since_last": docs_added,
        "top_remaining_issues": current_result.get("top_issues", [])[:5],
        "by_directory": current_result.get("by_directory", {}),
        "template_drift": drift_result,
        "violations_by_file": current_result.get("violations_by_file", {}),
    }


def tag_analytics() -> dict:
    """Analyze tag usage patterns: co-occurrence, underused tags, merge candidates.

    Returns:
        Co-occurrence pairs, underused tags, growth indicators, and merge suggestions.
    """
    from .config import load_tags
    from .index import _index

    registry = load_tags()

    with get_index_lock():
        entries = list(_index)

    # Exclude template files — their placeholder tags aren't real usage
    entries = [e for e in entries if e.get("type") != "template"]

    # --- Usage counts ---
    tag_counts: dict[str, int] = {}
    for entry in entries:
        for tag in entry.get("tags", []):
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # --- Co-occurrence matrix ---
    co_occurrence: dict[tuple[str, str], int] = {}
    for entry in entries:
        tags = sorted(entry.get("tags", []))
        for i, t1 in enumerate(tags):
            for t2 in tags[i + 1:]:
                pair = (t1, t2)
                co_occurrence[pair] = co_occurrence.get(pair, 0) + 1

    # Top co-occurring pairs (sorted by frequency)
    top_pairs = sorted(co_occurrence.items(), key=lambda x: x[1], reverse=True)[:15]
    co_occurrence_list = [
        {"tags": list(pair), "count": count, "percentage": round(count / max(len(entries), 1) * 100, 1)}
        for pair, count in top_pairs
    ]

    # --- Underused tags (in registry but used 0-2 times) ---
    underused = []
    for tag_name in registry:
        count = tag_counts.get(tag_name, 0)
        if count <= 2:
            underused.append({"tag": tag_name, "count": count})
    underused.sort(key=lambda x: x["count"])

    # --- Merge candidates (tags that co-occur in 70%+ of their uses) ---
    merge_candidates = []
    for (t1, t2), co_count in co_occurrence.items():
        t1_count = tag_counts.get(t1, 0)
        t2_count = tag_counts.get(t2, 0)
        if t1_count >= 3 and t2_count >= 3:
            # Percentage of t1's docs that also have t2, and vice versa
            t1_overlap = co_count / t1_count
            t2_overlap = co_count / t2_count
            if t1_overlap >= 0.7 or t2_overlap >= 0.7:
                merge_candidates.append({
                    "tags": [t1, t2],
                    "co_occurrences": co_count,
                    "overlap": f"{t1}: {round(t1_overlap * 100)}%, {t2}: {round(t2_overlap * 100)}%",
                    "suggestion": f"Tags '{t1}' and '{t2}' co-occur frequently. Consider merging or creating a parent tag.",
                })

    # --- Orphaned tags (in docs but not in registry) ---
    registry_names = set(registry.keys())
    all_used_tags = set(tag_counts.keys())
    orphaned = sorted(all_used_tags - registry_names)

    # --- Summary stats ---
    total_tags_in_registry = len(registry)
    tags_in_use = len([t for t, c in tag_counts.items() if c > 0 and t in registry_names])

    return {
        "summary": {
            "total_tags_in_registry": total_tags_in_registry,
            "tags_actively_used": tags_in_use,
            "total_documents": len(entries),
            "avg_tags_per_doc": round(sum(len(e.get("tags", [])) for e in entries) / max(len(entries), 1), 1),
        },
        "co_occurrence": co_occurrence_list,
        "underused": underused,
        "merge_candidates": merge_candidates,
        "orphaned_tags": orphaned,
    }
