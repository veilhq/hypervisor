"""
Directory tree helpers and index page generators (home + subdirectory indexes).
"""

import re
from datetime import datetime, date
from pathlib import PurePosixPath

from .config import (
    HYPERSPACE_ROOT, CATEGORY_DESCRIPTIONS, CATEGORY_ICONS, ASSETS_DIR,
    hypervisor_logo_svg,
)
from .file_utils import (
    dir_label, nice_name, get_title, extract_dates, sort_date, display_date,
    href_for, count_docs_under, get_dir_snippet,
    get_dir_status, get_dir_type, get_dir_tags, infer_app_group,
    compute_badges, format_badge_html,
)
from .chips import render_chip


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

COMPACT_THRESHOLD = 10  # Switch to grouped shelves above this many subdirs


def _doc_type_badge(rel_path):
    """Return an HTML badge indicating the document type based on filename.

    Legacy function — with the flat-file work item format, document-type badges
    are no longer needed. Returns empty string for all files.
    """
    return ''


def collect_dir_contents(files, dir_prefix):
    """
    For a given directory prefix (e.g. "patterns" or "ideas/to-do/cms"),
    return (subdirs, doc_entries) where:
      subdirs = sorted list of immediate child directory names
      doc_entries = list of (rel_path, nice_name) for immediate .md documents
    """
    subdirs = set()
    doc_entries = []
    prefix = PurePosixPath(dir_prefix) if dir_prefix else PurePosixPath(".")

    for rel in files:
        p = PurePosixPath(str(rel).replace("\\", "/"))
        # Must be inside this directory
        try:
            remainder = p.relative_to(prefix) if dir_prefix else p
        except ValueError:
            continue

        parts = remainder.parts
        if len(parts) == 1:
            # Direct child document
            doc_entries.append((rel, nice_name(parts[0])))
        elif len(parts) > 1:
            # In a subdirectory — record the immediate child dir
            subdirs.add(parts[0])

    return sorted(subdirs), doc_entries


def collect_all_dirs(files):
    """Return set of all directory prefixes that contain files (directly or nested)."""
    dirs = set()
    for rel in files:
        p = PurePosixPath(str(rel).replace("\\", "/"))
        # Add every ancestor directory
        for i in range(1, len(p.parts)):
            dirs.add(str(PurePosixPath(*p.parts[:i])))
    return dirs



def _parse_task_progress(md_text):
    """Return (done, total) count of task-list checkboxes in the document.

    Counts markdown checkboxes: `- [ ]` (open) and `- [x]` / `- [X]` (done).
    Only counts lines that look like task-list items (dash + checkbox), so
    inline `[x]` inside prose is ignored.
    """
    done = 0
    total = 0
    for line in md_text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("- [", "* [")):
            if len(stripped) < 5:
                continue
            marker = stripped[3]
            if marker in (" ", "x", "X"):
                total += 1
                if marker in ("x", "X"):
                    done += 1
    return done, total


def _extract_work_id_from_text(md_text):
    """Extract work item ID (e.g., WI-23) from dash-prefixed metadata."""
    for line in md_text.splitlines()[:30]:
        m = re.match(r'^-\s*ID\s*:\s*(WI-\d+)', line.strip(), re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def _pulse_day_header(date_str):
    """Return a human day label ('TODAY', 'YESTERDAY', 'N DAYS AGO') for a
    'YYYY-MM-DDTHH:MM' timestamp. Falls back to the date portion for old items.
    """
    if not date_str or date_str.startswith("0000"):
        return "OLDER"
    try:
        d = datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except ValueError:
        return "OLDER"
    delta = (date.today() - d).days
    if delta <= 0:
        return "TODAY"
    if delta == 1:
        return "YESTERDAY"
    if delta < 7:
        return f"{delta} DAYS AGO"
    if delta < 14:
        return "LAST WEEK"
    if delta < 30:
        return f"{delta} DAYS AGO"
    return "OLDER"


def _pulse_time_str(date_str):
    """Return 'HH:MM' from a 'YYYY-MM-DDTHH:MM' timestamp, or empty string."""
    if not date_str or "T" not in date_str:
        return ""
    parts = date_str.split("T", 1)
    return parts[1][:5] if len(parts) == 2 else ""


def generate_home_content(files, build_stats=None, recent_paths=None):
    """Generate the hub homepage HTML — dashboard layout."""
    if recent_paths is None:
        recent_paths = set()
    # Top-level categories
    top_dirs = set()
    top_docs = []
    for rel in files:
        p = PurePosixPath(str(rel).replace("\\", "/"))
        parts = p.parts
        if len(parts) == 1:
            top_docs.append(rel)
        else:
            top_dirs.add(parts[0])

    html = []

    # --- 0. Anchor mark (Hypervisor icon + noise field + rotating greeting) ---
    logo = hypervisor_logo_svg("home-anchor-icon")
    if logo:
        html.append(
            '<div class="home-anchor">'
            f'{logo}'
            '<span class="home-anchor-greeting" data-home-greeting></span>'
            '</div>'
        )

    # --- 1. Build metadata (folded into Pulse header below; no standalone strip) ---
    build_time = ""
    if build_stats:
        ts = build_stats.get("timestamp", "")
        # Extract "HH:MM" from "YYYY-MM-DD HH:MM:SS"
        if " " in ts:
            time_part = ts.split(" ")[1]
            build_time = time_part[:5] if len(time_part) >= 5 else time_part
        else:
            build_time = ts

    # --- 2. Active Work Items (in-progress from work/to-do) ---
    active_items = []
    for rel in files:
        rel_posix = str(rel).replace("\\", "/")
        if not rel_posix.startswith("work/to-do/"):
            continue
        parts = PurePosixPath(rel_posix).parts
        # Flat file format: work/to-do/slug.md (3 parts)
        if len(parts) != 3:
            continue
        # Skip _conventions.md
        if parts[2].startswith("_"):
            continue
        md_text = (HYPERSPACE_ROOT / rel).read_text(encoding="utf-8")
        from .file_utils import _extract_status_from_text
        status = _extract_status_from_text(md_text)
        if status and ("progress" in status.lower() or "discussion" in status.lower()):
            title = get_title(md_text, nice_name(parts[2]))
            dates = extract_dates(md_text)
            date_str, _ = sort_date(dates)
            done, total = _parse_task_progress(md_text)
            work_id = _extract_work_id_from_text(md_text)
            # Days since Created (fallback: since Updated)
            days_active = 0
            created = dates.get("created") or dates.get("updated") or ""
            if created and not created.startswith("0000"):
                try:
                    c = datetime.strptime(created[:10], "%Y-%m-%d").date()
                    days_active = max(0, (date.today() - c).days)
                except ValueError:
                    days_active = 0
            active_items.append({
                "path": rel_posix,
                "title": title,
                "status": status,
                "date": date_str,
                "rel": rel,
                "done": done,
                "total": total,
                "work_id": work_id,
                "days": days_active,
            })
    active_items.sort(key=lambda x: x["date"], reverse=True)

    # --- 3. Recent Activity (up to 10 items, day-grouped) ---
    recent = []
    for rel in files:
        rel_posix = str(rel).replace("\\", "/")
        if rel_posix in recent_paths:
            md_text = (HYPERSPACE_ROOT / rel).read_text(encoding="utf-8")
            title = get_title(md_text, nice_name(rel.name))
            dates = extract_dates(md_text)
            date_str, date_label = sort_date(dates)
            recent.append((rel, title, date_str, date_label))
    recent.sort(key=lambda x: x[2], reverse=True)
    recent = recent[:10]

    # Group recent items by day label
    from collections import OrderedDict
    recent_by_day = OrderedDict()
    for rel, title, date_str, date_label in recent:
        day = _pulse_day_header(date_str)
        recent_by_day.setdefault(day, []).append((rel, title, date_str, date_label))

    # --- 4. Two-panel dashboard: Workspace Pulse + Pinned ---
    html.append('<div class="dashboard-panels">')

    # Left panel: Workspace Pulse (in-progress + recent stream)
    html.append('<div class="hv-section pulse-section">')
    summary_parts = [
        f'{len(active_items)} active',
        f'{len(recent)} recent',
    ]
    if build_time:
        summary_parts.append(f'built {build_time}')
    pulse_summary = ' &middot; '.join(summary_parts)
    html.append(
        f'<h2><i data-lucide="activity" class="section-icon"></i> Pulse'
        f' <span class="pulse-summary">{pulse_summary}</span></h2>'
    )

    # In-progress group (no header — filled accent chips carry the signal)
    html.append('<div class="pulse-group pulse-group-active">')
    if active_items:
        for it in active_items:
            done, total = it["done"], it["total"]
            if total > 0:
                pct = int(round(done * 100 / total))
                progress_html = (
                    '<span class="pulse-progress" title="'
                    f'{done}/{total} tasks">'
                    f'<span class="hv-progress-track pulse-bar">'
                    f'<span class="hv-progress-fill pulse-fill" style="width:{pct}%"></span>'
                    f'</span>'
                    f'<span class="pulse-progress-label">{done}/{total}</span>'
                    f'</span>'
                )
            else:
                progress_html = (
                    '<span class="pulse-progress pulse-progress-empty" title="No tasks defined">'
                    '<span class="hv-progress-track hv-progress-track-empty pulse-bar pulse-bar-empty"></span>'
                    '<span class="pulse-progress-label">&mdash;/&mdash;</span>'
                    '</span>'
                )
            days_str = f'{it["days"]}d'
            chip = (
                render_chip("filled", it["work_id"], extra_class="pulse-chip pulse-chip-work")
                if it["work_id"]
                else render_chip("outlined-muted", "&mdash;", extra_class="pulse-chip pulse-chip-work pulse-chip-missing")
            )
            html.append(
                f'<a class="pulse-row pulse-row-active" href="{href_for(it["rel"])}">'
                f'{chip}'
                f'<span class="pulse-title">{it["title"]}</span>'
                f'<span class="pulse-right">{days_str}</span>'
                f'{progress_html}'
                f'</a>'
            )
    else:
        html.append('<div class="pulse-empty">no items in progress</div>')
    html.append('</div>')  # /.pulse-group-active

    # Recent stream grouped by day
    html.append('<div class="pulse-group pulse-group-recent">')
    if recent_by_day:
        for day_label, items in recent_by_day.items():
            html.append(f'<div class="pulse-day-header">{day_label}</div>')
            for rel, title, date_str, date_label in items:
                is_new = date_label == "created"
                chip_variant = "outlined-accent" if is_new else "outlined-muted"
                specific_cls = "pulse-chip pulse-chip-new" if is_new else "pulse-chip pulse-chip-updated"
                chip_label = "NEW" if is_new else "UPD"
                time_str = _pulse_time_str(date_str) or "&mdash;&mdash;:&mdash;&mdash;"
                html.append(
                    f'<a class="pulse-row pulse-row-recent" href="{href_for(rel)}">'
                    f'{render_chip(chip_variant, chip_label, extra_class=specific_cls)}'
                    f'<span class="pulse-title">{title}</span>'
                    f'<span class="pulse-right">{time_str}</span>'
                    f'</a>'
                )
    else:
        html.append('<div class="pulse-day-header">RECENT</div>')
        html.append('<div class="pulse-empty">no recent activity</div>')
    html.append('</div>')  # /.pulse-group-recent

    html.append('</div>')  # /.pulse-section

    # Right panel: Pinned (rendered client-side by pins.js)
    html.append('<div class="hv-section pins-section" data-pins-home-mount>')
    html.append(
        '<h2><i data-lucide="pin" class="section-icon"></i> Pinned'
        ' <span class="pins-home-count" data-pins-home-count></span></h2>'
    )
    html.append(
        '<div class="pins-home-list" data-pins-home-list>'
        '<div class="pins-home-loading">loading pins&hellip;</div>'
        '</div>'
    )
    html.append('</div>')  # /.pins-section

    html.append('</div>')  # /.dashboard-panels

    # --- 5. Root-level documents (full width, bottom) ---
    if top_docs:
        html.append('<div class="hv-section root-docs-section">')
        html.append('<h2><i data-lucide="files" class="section-icon"></i> Root Documents</h2>')
        html.append('<ul class="doc-list">')

        enriched = []
        for rel in top_docs:
            md_text = (HYPERSPACE_ROOT / rel).read_text(encoding="utf-8")
            title = get_title(md_text, nice_name(rel.name))
            dates = extract_dates(md_text)
            date_str, date_label = sort_date(dates)
            enriched.append((rel, title, date_str, date_label))
        enriched.sort(key=lambda x: x[2], reverse=True)

        for rel, title, date_str, date_label in enriched:
            rel_posix = str(rel).replace("\\", "/")
            date_content = display_date(date_str) if date_label else ""
            badge = '<span class="hv-badge hv-badge-muted">root</span>'
            type_badge = _doc_type_badge(rel)
            html.append(f'<li><a href="{href_for(rel)}"><i data-lucide="file-text" class="doc-icon"></i> {title}</a>'
                        f'<span class="doc-badges">{type_badge}{badge}</span>'
                        f'<span class="doc-date">{date_content}</span></li>')
        html.append('</ul>')
        html.append('</div>')

    return "\n".join(html)



def generate_dir_index_content(files, dir_prefix, recent_paths=None):
    """Generate an index page for a subdirectory."""
    if recent_paths is None:
        recent_paths = set()

    slug_label = dir_label(PurePosixPath(dir_prefix).name)
    subdirs, doc_entries = collect_dir_contents(files, dir_prefix)

    # Try to get a better title from the directory's primary doc
    title = slug_label
    for candidate in ("_meta.md",):
        candidate_path = HYPERSPACE_ROOT / dir_prefix / candidate
        if candidate_path.exists():
            md_text = candidate_path.read_text(encoding="utf-8")
            extracted = get_title(md_text, "")
            if extracted:
                title = extracted
                break

    html = []

    # --- Directory header ---
    _render_dir_header(html, files, dir_prefix, title)

    # --- Subdirectories ---
    if subdirs:
        dir_has_recent_fn = _dir_has_recent_factory(recent_paths)

        if len(subdirs) == 1:
            _render_subdirs_single(html, files, dir_prefix, subdirs[0], recent_paths)
        elif len(subdirs) > COMPACT_THRESHOLD:
            _render_subdirs_grouped(html, files, dir_prefix, subdirs, dir_has_recent_fn)
        else:
            _render_subdirs_dock(html, files, dir_prefix, subdirs, dir_has_recent_fn)

    # --- Document entries ---
    if doc_entries:
        is_work_dir = dir_prefix.startswith("work/to-do") or dir_prefix.startswith("work/done")
        is_ideas_dir = dir_prefix == "ideas"

        if (is_work_dir or is_ideas_dir) and len(doc_entries) > 5:
            _render_work_items_list(html, files, dir_prefix, doc_entries, recent_paths, is_ideas_dir)
        else:
            _render_doc_list_standard(html, files, dir_prefix, doc_entries, recent_paths)

    if not subdirs and not doc_entries:
        html.append('<p class="empty-msg">No documents in this directory.</p>')

    # --- Raw HTML prototypes ---
    _render_prototypes(html, dir_prefix)

    return "\n".join(html), title



# ---------------------------------------------------------------------------
# Private helper functions for generate_dir_index_content
# ---------------------------------------------------------------------------


def _dir_has_recent_factory(recent_paths):
    """Return a closure that checks if a directory prefix has recent activity."""
    def _dir_has_recent(dp):
        prefix = dp + "/"
        return any(rp.startswith(prefix) for rp in recent_paths)
    return _dir_has_recent


def _render_dir_header(html, files, dir_prefix, title):
    """Render the directory page header with icon, title, stats, and last activity."""
    dir_name = PurePosixPath(dir_prefix).name
    icon = CATEGORY_ICONS.get(dir_name, "folder")
    desc = CATEGORY_DESCRIPTIONS.get(dir_name, "")
    subdirs, _ = collect_dir_contents(files, dir_prefix)
    total_docs = count_docs_under(files, dir_prefix)

    # Compute last activity date across all docs in this directory
    last_activity = ""
    for rel in files:
        rel_posix = str(rel).replace("\\", "/")
        if not rel_posix.startswith(dir_prefix + "/"):
            continue
        md_path = HYPERSPACE_ROOT / rel
        if md_path.exists():
            md_text = md_path.read_text(encoding="utf-8")
            dates = extract_dates(md_text)
            date_str, _ = sort_date(dates)
            if date_str > last_activity:
                last_activity = date_str

    html.append('<div class="dir-header">')
    html.append('<div class="dir-header-top">')
    html.append(f'<i data-lucide="{icon}" class="dir-header-icon"></i>')
    html.append(f'<h1 class="dir-header-title">{title}</h1>')
    html.append('</div>')
    if desc:
        html.append(f'<div class="dir-header-desc">{desc}</div>')
    html.append('<div class="dir-header-stats">')
    html.append(f'<span class="dir-stat"><i data-lucide="file-text" class="dir-stat-icon"></i><span class="dir-stat-val">{total_docs}</span><span class="dir-stat-label">docs</span></span>')
    html.append(f'<span class="dir-stat"><i data-lucide="folder" class="dir-stat-icon"></i><span class="dir-stat-val">{len(subdirs)}</span><span class="dir-stat-label">dirs</span></span>')
    if last_activity and not last_activity.startswith("0000"):
        html.append(f'<span class="dir-stat"><i data-lucide="clock" class="dir-stat-icon"></i><span class="dir-stat-val">{display_date(last_activity)}</span><span class="dir-stat-label">last activity</span></span>')
    html.append('</div>')
    html.append('</div>')



def _render_subdirs_single(html, files, dir_prefix, sd, recent_paths):
    """Render a single subdirectory inline — expand its contents instead of showing a lone dock item."""
    _dir_has_recent = _dir_has_recent_factory(recent_paths)
    sd_path = f"{dir_prefix}/{sd}"
    sd_label = dir_label(sd)
    child_subdirs, child_docs = collect_dir_contents(files, sd_path)

    # Show a linked section header for the single child
    html.append('<div class="hv-section documents-section">')
    sd_icon = CATEGORY_ICONS.get(sd, "folder")
    html.append(f'<h2><a href="{sd}/index.html" style="color:inherit;text-decoration:none;border:none"><i data-lucide="{sd_icon}" class="section-icon"></i> {sd_label}</a></h2>')

    if child_subdirs:
        # Show grandchild dirs as a dock strip
        html.append(f'<nav class="home-dock" aria-label="{sd_label} subdirectories">')
        for gsd in child_subdirs:
            gsd_path = f"{sd_path}/{gsd}"
            gsd_label = dir_label(gsd)
            gsd_count = count_docs_under(files, gsd_path)
            gsd_icon = CATEGORY_ICONS.get(gsd, "folder")
            gsd_dock_cls = "dock-item dock-item-recent" if _dir_has_recent(gsd_path) else "dock-item"
            html.append(
                f'<a href="{sd}/{gsd}/index.html" class="{gsd_dock_cls}" data-tooltip="{gsd_label} ({gsd_count})">'
                f'<i data-lucide="{gsd_icon}" class="dock-icon"></i>'
                f'<span class="dock-label">{gsd_label}</span>'
                f'<span class="dock-count">{gsd_count}</span>'
                f'</a>'
            )
        html.append('</nav>')

    if child_docs:
        html.append('<ul class="doc-list">')
        enriched_child = []
        for rel, name in child_docs:
            md_text = (HYPERSPACE_ROOT / rel).read_text(encoding="utf-8")
            doc_title = get_title(md_text, name)
            dates = extract_dates(md_text)
            date_str, date_label = sort_date(dates)
            enriched_child.append((rel, doc_title, date_str, date_label))
        dated_c = [(r, t, d, l) for r, t, d, l in enriched_child if d != "0000-00-00"]
        undated_c = [(r, t, d, l) for r, t, d, l in enriched_child if d == "0000-00-00"]
        dated_c.sort(key=lambda x: x[2], reverse=True)
        undated_c.sort(key=lambda x: x[1].lower())
        enriched_child = dated_c + undated_c
        for rel, doc_title, date_str, date_label in enriched_child:
            rel_posix = str(rel).replace("\\", "/")
            fname_stem = PurePosixPath(rel_posix).stem
            date_content = display_date(date_str) if date_label else ""
            li_cls = ' class="doc-recent"' if rel_posix in recent_paths else ''
            type_badge = _doc_type_badge(rel)
            badge_cell = f'<span class="doc-badges">{type_badge}</span>' if type_badge else ''
            html.append(f'<li{li_cls}><a href="{sd}/{fname_stem}/index.html"><i data-lucide="file-text" class="doc-icon"></i> {doc_title}</a>'
                        f'<span class="doc-path">{rel_posix}</span>'
                        f'{badge_cell}'
                        f'<span class="doc-date">{date_content}</span></li>')
        html.append('</ul>')

    if not child_subdirs and not child_docs:
        html.append('<p class="empty-msg">No documents in this directory.</p>')

    html.append('</div>')



def _render_subdirs_grouped(html, files, dir_prefix, subdirs, dir_has_recent_fn):
    """Render subdirectories as grouped shelves by application (>10 subdirs)."""
    subdir_data = []
    for sd in subdirs:
        sd_path = f"{dir_prefix}/{sd}"
        sd_label = dir_label(sd)
        count = count_docs_under(files, sd_path)
        desc = get_dir_snippet(HYPERSPACE_ROOT, sd_path)
        status = get_dir_status(HYPERSPACE_ROOT, sd_path)
        item_type = get_dir_type(HYPERSPACE_ROOT, sd_path) or "professional"
        tags = get_dir_tags(HYPERSPACE_ROOT, sd_path)
        app_label, app_key = infer_app_group(tags)
        subdir_data.append((sd, sd_label, count, desc, status, item_type, app_key, app_label))

    # Sort within each group by name
    subdir_data.sort(key=lambda x: x[1].lower())

    # Collect unique app groups (preserve a stable order)
    _APP_GROUP_ORDER = ["portal", "portal-cms", "hyperspace", "infrastructure", "other"]
    seen_groups = {}
    for item in subdir_data:
        key, label = item[6], item[7]
        if key not in seen_groups:
            seen_groups[key] = label
    ordered_groups = [k for k in _APP_GROUP_ORDER if k in seen_groups]
    for k in seen_groups:
        if k not in ordered_groups:
            ordered_groups.append(k)

    # Collect unique statuses across all items
    statuses = sorted(set((d[4] or "").strip() for d in subdir_data if d[4]))

    html.append('<div class="hv-section documents-section">')
    html.append(f'<h2><i data-lucide="folder" class="section-icon"></i> Items ({len(subdir_data)})</h2>')
    html.append('<div class="todo-filters" id="todo-filters">')
    html.append('  <input type="text" class="todo-filter-input" id="todo-filter-name" placeholder="filter by name" spellcheck="false">')
    html.append('  <select class="todo-filter-select" id="todo-filter-app">')
    html.append('    <option value="">all apps</option>')
    for gk in ordered_groups:
        html.append(f'    <option value="{gk}">{seen_groups[gk]}</option>')
    html.append('  </select>')
    html.append('  <select class="todo-filter-select" id="todo-filter-type">')
    html.append('    <option value="">all types</option>')
    html.append('    <option value="personal">personal</option>')
    html.append('    <option value="professional">professional</option>')
    html.append('  </select>')
    html.append('  <select class="todo-filter-select" id="todo-filter-status">')
    html.append('    <option value="">all statuses</option>')
    for s in statuses:
        html.append(f'    <option value="{s.lower()}">{s}</option>')
    html.append('  </select>')
    html.append('</div>')

    # Render each app group as a shelf
    for gk in ordered_groups:
        group_items = [d for d in subdir_data if d[6] == gk]
        gl = seen_groups[gk]
        # Count how many items in this group have recent activity
        shelf_recent_count = sum(
            1 for d in group_items if dir_has_recent_fn(f"{dir_prefix}/{d[0]}")
        )
        html.append(f'<div class="app-shelf" data-app-group="{gk}">')
        html.append(f'<div class="app-shelf-header">')
        html.append(f'<span class="app-shelf-label">{gl}</span>')
        if shelf_recent_count:
            html.append(f'<span class="app-shelf-recent-count">{shelf_recent_count}</span>')
        html.append(f'<span class="app-shelf-count">{len(group_items)}</span>')
        html.append(f'</div>')
        html.append(f'<ul class="doc-list todo-list" data-app-group="{gk}">')

        for sd, sd_label, count, desc, status, item_type, _ak, _al in group_items:
            sd_icon = CATEGORY_ICONS.get(sd, "folder")
            type_cls = "type-badge-personal" if item_type.lower() == "personal" else "type-badge-professional"
            type_label = item_type.lower()[:4]
            status_cls = "status-" + (status or "proposed").lower().replace(" ", "-")
            status_label = status or "—"
            desc_text = desc if desc else ""
            sd_full_path = f"{dir_prefix}/{sd}"
            li_cls = " doc-recent" if dir_has_recent_fn(sd_full_path) else ""
            html.append(
                f'<li class="{li_cls.strip()}" data-name="{sd_label.lower()}" data-type="{item_type.lower()}" data-status="{(status or "").lower()}" data-app="{gk}">'
                f'<div class="todo-title"><a href="{sd}/index.html"><i data-lucide="{sd_icon}" class="doc-icon"></i>{sd_label}</a>'
                f'<span class="todo-desc">{desc_text}</span></div>'
                f'<span class="hv-badge {type_cls}">{type_label}</span>'
                f'<span class="hv-badge {status_cls}">{status_label}</span>'
                f'</li>'
            )

        html.append('</ul>')
        html.append('</div>')

    html.append('</div>')



def _render_subdirs_dock(html, files, dir_prefix, subdirs, dir_has_recent_fn):
    """Render subdirectories as a dock-style strip (2-10 subdirs, non-top-level)."""
    # Determine if this is a top-level category (children shown in site nav)
    is_top_level = "/" not in dir_prefix and "\\" not in dir_prefix
    if is_top_level:
        # Top-level categories: children are in the nav rail, no dock needed.
        # Just show nothing here — the nav handles navigation.
        pass
    else:
        # Dock-style strip for deeper directories not in the nav
        html.append('<nav class="home-dock" aria-label="Subdirectories">')
        for sd in subdirs:
            sd_path = f"{dir_prefix}/{sd}"
            sd_label = dir_label(sd)
            count = count_docs_under(files, sd_path)
            sd_icon = CATEGORY_ICONS.get(sd, "folder")
            dock_cls = "dock-item dock-item-recent" if dir_has_recent_fn(sd_path) else "dock-item"
            html.append(
                f'<a href="{sd}/index.html" class="{dock_cls}" data-tooltip="{sd_label} ({count})">'
                f'<i data-lucide="{sd_icon}" class="dock-icon"></i>'
                f'<span class="dock-label">{sd_label}</span>'
                f'<span class="dock-count">{count}</span>'
                f'</a>'
            )
        html.append('</nav>')



def _render_work_items_list(html, files, dir_prefix, doc_entries, recent_paths, is_ideas):
    """Render work items or ideas with filter controls and flat sorted list."""
    from .file_utils import _extract_status_from_text, _extract_type_from_text, _extract_tags_from_text, infer_app_group

    html.append('<div class="hv-section documents-section">')

    enriched = []
    statuses_set = set()
    app_groups_seen = {}
    _APP_GROUP_ORDER = ["portal", "portal-cms", "hyperspace", "infrastructure", "other"]

    for rel, name in doc_entries:
        md_text = (HYPERSPACE_ROOT / rel).read_text(encoding="utf-8")
        doc_title = get_title(md_text, name)
        dates = extract_dates(md_text)
        date_str, date_label = sort_date(dates)
        status = _extract_status_from_text(md_text) or ""
        item_type = _extract_type_from_text(md_text) or "professional"
        tags = _extract_tags_from_text(md_text)
        app_label, app_key = infer_app_group(tags)
        desc = ""
        # Extract work item ID
        work_id = ""
        for line in md_text.splitlines()[:20]:
            id_match = re.match(r'^-\s*ID\s*:\s*(WI-\d+)', line.strip(), re.IGNORECASE)
            if id_match:
                work_id = id_match.group(1)
                break
        # Extract snippet from the Overview section
        past_meta = False
        for line in md_text.splitlines():
            stripped = line.strip()
            if stripped.startswith("# ") and not past_meta:
                continue
            if not past_meta:
                if stripped.startswith("-") and ":" in stripped[:30]:
                    continue
                if stripped == "" or stripped == "---":
                    continue
                past_meta = True
            if stripped.startswith("#") or stripped.startswith("```"):
                break
            if stripped == "" or stripped == "---":
                if desc:
                    break
                continue
            desc = stripped[:120]
            break

        if status:
            statuses_set.add(status)
        if app_key not in app_groups_seen:
            app_groups_seen[app_key] = app_label
        badges_html = format_badge_html(compute_badges(md_text, dates.get("updated")))
        enriched.append((rel, doc_title, date_str, date_label, status, item_type, app_key, app_label, desc, work_id, badges_html))

    # Sort: dated docs first (newest to oldest), undated last
    dated = [e for e in enriched if e[2] != "0000-00-00T00:00"]
    undated = [e for e in enriched if e[2] == "0000-00-00T00:00"]
    dated.sort(key=lambda x: x[2], reverse=True)
    undated.sort(key=lambda x: x[1].lower())
    enriched = dated + undated

    statuses = sorted(statuses_set)
    ordered_groups = [k for k in _APP_GROUP_ORDER if k in app_groups_seen]
    for k in app_groups_seen:
        if k not in ordered_groups:
            ordered_groups.append(k)

    html.append(f'<h2><i data-lucide="{"lightbulb" if is_ideas else "file-text"}" class="section-icon"></i> {"Ideas" if is_ideas else "Items"} ({len(enriched)})</h2>')
    html.append('<div class="todo-filters" id="todo-filters">')
    html.append('  <input type="text" class="todo-filter-input" id="todo-filter-name" placeholder="filter by name" spellcheck="false">')
    html.append('  <select class="todo-filter-select" id="todo-filter-app">')
    html.append('    <option value="">all apps</option>')
    for gk in ordered_groups:
        html.append(f'    <option value="{gk}">{app_groups_seen[gk]}</option>')
    html.append('  </select>')
    html.append('  <select class="todo-filter-select" id="todo-filter-type">')
    html.append('    <option value="">all types</option>')
    html.append('    <option value="personal">personal</option>')
    html.append('    <option value="professional">professional</option>')
    html.append('  </select>')
    if not is_ideas:
        html.append('  <select class="todo-filter-select" id="todo-filter-status">')
        html.append('    <option value="">all statuses</option>')
        for s in statuses:
            html.append(f'    <option value="{s.lower()}">{s}</option>')
        html.append('  </select>')
    html.append('</div>')

    # Flat list sorted by work item ID (descending — newest first)
    def _wi_sort_key(e):
        wid = e[9]  # work_id field
        if wid and wid.startswith("WI-"):
            try:
                return -int(wid[3:])
            except ValueError:
                pass
        return 0

    enriched.sort(key=_wi_sort_key)

    html.append('<ul class="doc-list todo-list">')

    for rel, doc_title, date_str, date_label, status, item_type, app_key, _al, desc, work_id, badges_html in enriched:
        rel_posix = str(rel).replace("\\", "/")
        fname_stem = PurePosixPath(rel_posix).stem
        type_cls = "type-badge-personal" if item_type.lower() == "personal" else "type-badge-professional"
        type_label = item_type.lower()[:4]
        status_cls = "status-" + (status or "planned").lower().replace(" ", "-")
        status_label = status or "—"
        li_cls = " doc-recent" if rel_posix in recent_paths else ""
        status_badge = f'<span class="hv-badge {status_cls}">{status_label}</span>' if not is_ideas else ''
        id_prefix = f'<span class="work-id-inline">{work_id} —</span> ' if work_id else ''
        html.append(
            f'<li class="{li_cls.strip()}" data-name="{doc_title.lower()}" data-type="{item_type.lower()}" data-status="{(status or "").lower()}" data-app="{app_key}">'
            f'<div class="todo-title"><a href="{fname_stem}/index.html"><i data-lucide="{"lightbulb" if is_ideas else "circle-dot"}" class="doc-icon"></i>{id_prefix}{doc_title}</a>'
            f'<span class="todo-desc">{desc}</span></div>'
            f'<div class="todo-badges">{badges_html}'
            f'<span class="hv-badge {type_cls}">{type_label}</span>'
            f'{status_badge}</div>'
            f'</li>'
        )

    html.append('</ul>')
    html.append('</div>')



def _render_doc_list_standard(html, files, dir_prefix, doc_entries, recent_paths):
    """Render a standard document list (non-work, non-ideas directories)."""
    html.append('<div class="hv-section documents-section">')
    html.append('<h2><i data-lucide="file-text" class="section-icon"></i> Documents</h2>')
    html.append('<ul class="doc-list">')

    # Enrich entries with date metadata for sorting
    enriched = []
    for rel, name in doc_entries:
        md_text = (HYPERSPACE_ROOT / rel).read_text(encoding="utf-8")
        doc_title = get_title(md_text, name)
        dates = extract_dates(md_text)
        date_str, date_label = sort_date(dates)
        enriched.append((rel, doc_title, date_str, date_label))

    # Sort: dated docs first (newest to oldest), undated docs last (by title)
    dated = [(r, t, d, l) for r, t, d, l in enriched if d != "0000-00-00"]
    undated = [(r, t, d, l) for r, t, d, l in enriched if d == "0000-00-00"]
    dated.sort(key=lambda x: x[2], reverse=True)
    undated.sort(key=lambda x: x[1].lower())
    enriched = dated + undated

    for rel, doc_title, date_str, date_label in enriched:
        rel_posix = str(rel).replace("\\", "/")
        fname_stem = PurePosixPath(rel_posix).stem
        date_content = display_date(date_str) if date_label else ""
        li_cls = ' class="doc-recent"' if rel_posix in recent_paths else ''
        html.append(f'<li{li_cls}><a href="{fname_stem}/index.html"><i data-lucide="file-text" class="doc-icon"></i> {doc_title}</a>'
                    f'<span class="doc-path">{rel_posix}</span>'
                    f'<span class="doc-date">{date_content}</span></li>')
    html.append('</ul>')
    html.append('</div>')


def _render_prototypes(html, dir_prefix):
    """Render links to raw HTML prototype files in the directory."""
    dir_path = HYPERSPACE_ROOT / dir_prefix
    if dir_path.is_dir():
        html_files = sorted(dir_path.glob("*.html"))
        if html_files:
            html.append('<div class="hv-section documents-section">')
            html.append('<h2><i data-lucide="code" class="section-icon"></i> Prototypes</h2>')
            html.append('<ul class="doc-list">')
            for hf in html_files:
                hf_name = hf.stem.replace("-", " ").replace("_", " ").title()
                html.append(f'<li><a href="{hf.stem}/index.html"><i data-lucide="layout" class="doc-icon"></i> {hf_name}</a>'
                            f'<span class="doc-path">{hf.name}</span></li>')
            html.append('</ul>')
            html.append('</div>')
