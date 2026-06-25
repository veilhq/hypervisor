"""
Directory tree helpers and index page generators (home + subdirectory indexes).
"""

import re
from pathlib import PurePosixPath

from .config import (
    HYPERSPACE_ROOT, CATEGORY_DESCRIPTIONS, CATEGORY_ICONS, ASSETS_DIR,
)
from .file_utils import (
    dir_label, nice_name, get_title, extract_dates, sort_date, display_date,
    href_for, count_docs_under, get_dir_snippet,
    get_dir_status, get_dir_type, get_dir_tags, infer_app_group,
)


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

    # --- 0. Hero ASCII text ---
    hero_file = ASSETS_DIR / "hero.txt"
    if hero_file.exists():
        hero_text = hero_file.read_text(encoding="utf-8").rstrip("\n")
        html.append('<div class="hero-wrap">')
        html.append(f'<pre class="hero-ascii">{hero_text}</pre>')
        html.append('<span class="hero-tagline">interactive shell for the hyperspace persistent memory (HPM) system.</span>')
        html.append('</div>')

    # --- 1. KPI strip (compact single line) ---
    if build_stats:
        active_count = 0  # computed below
        html.append('<div class="kpi-strip">')
        html.append(f'<span class="kpi"><span class="kpi-val">{build_stats["files"]}</span><span class="kpi-label">docs</span></span>')
        html.append(f'<span class="kpi"><span class="kpi-val">{build_stats["pages"]}</span><span class="kpi-label">pages</span></span>')
        html.append(f'<span class="kpi"><span class="kpi-val">{build_stats["indexes"]}</span><span class="kpi-label">indexes</span></span>')
        html.append(f'<span class="kpi kpi-active"><span class="kpi-val" id="kpi-active">—</span><span class="kpi-label">active</span></span>')
        html.append(f'<span class="kpi kpi-time"><span class="kpi-val">{build_stats["timestamp"].split(" ")[1] if " " in build_stats["timestamp"] else build_stats["timestamp"]}</span><span class="kpi-label">built</span></span>')
        html.append('</div>')

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
            active_items.append((rel_posix, title, status, date_str, rel))
    active_items.sort(key=lambda x: x[3], reverse=True)

    # --- 3. Recent Activity (grouped by work item) ---
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

    # Group recent items by parent directory (work items share a folder)
    from collections import OrderedDict
    grouped_recent = OrderedDict()
    ungrouped_recent = []
    for rel, title, date_str, date_label in recent:
        rel_posix = str(rel).replace("\\", "/")
        # With flat-file work items, no grouping needed — treat all as ungrouped
        ungrouped_recent.append((rel, title, date_str, date_label))

    # --- 4. Two-panel layout: Active Work + Recent Activity side by side ---
    html.append('<div class="dashboard-panels">')

    # Left panel: Active Work
    html.append('<div class="hv-section active-work-section">')
    html.append(f'<h2><i data-lucide="zap" class="section-icon"></i> Active Work ({len(active_items)})</h2>')
    if active_items:
        html.append('<ul class="doc-list">')
        for work_dir, title, status, date_str, rel in active_items:
            rel_posix = str(rel).replace("\\", "/")
            status_cls = "status-" + status.lower().replace(" ", "-")
            html.append(
                f'<li><a href="{href_for(rel)}"><i data-lucide="circle-dot" class="doc-icon"></i> {title}</a>'
                f'<span class="hv-badge {status_cls}">{status}</span>'
                f'<span class="doc-date">{display_date(date_str)}</span></li>'
            )
        html.append('</ul>')
    else:
        html.append('<p class="empty-msg">No active work items.</p>')
    html.append('</div>')

    # Right panel: Recent Activity (grouped)
    html.append('<div class="hv-section recent-section">')
    html.append('<h2><i data-lucide="clock" class="section-icon"></i> Recent Activity</h2>')
    html.append('<ul class="doc-list recent-grouped">')

    # Render all recent items (flat — no grouping needed with unified work items)
    for rel, title, date_str, date_label in ungrouped_recent:
        if date_label == "created":
            badge = '<span class="hv-badge recent-badge-new">new</span>'
        else:
            badge = '<span class="hv-badge recent-badge-updated">updated</span>'
        type_badge = _doc_type_badge(rel)
        html.append(
            f'<li><a href="{href_for(rel)}"><i data-lucide="file-text" class="doc-icon"></i> {title}</a>'
            f'<span class="doc-badges">{type_badge}{badge}</span>'
            f'<span class="doc-date">{display_date(date_str)}</span></li>'
        )

    html.append('</ul>')
    html.append('</div>')

    html.append('</div>')  # close dashboard-panels

    # Update KPI active count via inline script
    if build_stats:
        html.append(f'<script>document.getElementById("kpi-active").textContent="{len(active_items)}";</script>')

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

    def _dir_has_recent(dp):
        """Check if any recent path lives under this directory prefix."""
        prefix = dp + "/"
        return any(rp.startswith(prefix) for rp in recent_paths)
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

    html = [f'<h1>{title}</h1>']

    COMPACT_THRESHOLD = 10  # Switch to list view above this many subdirs

    if subdirs:
        if len(subdirs) == 1:
            # Single subdirectory — inline its contents instead of showing a lone dock item
            sd = subdirs[0]
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

        elif len(subdirs) > COMPACT_THRESHOLD:
            # --- Grouped shelves by application ---
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
                # Check if any item in this group has recently updated docs
                shelf_has_recent = any(
                    _dir_has_recent(f"{dir_prefix}/{d[0]}") for d in group_items
                )
                shelf_cls = "app-shelf shelf-recent" if shelf_has_recent else "app-shelf"
                html.append(f'<div class="{shelf_cls}" data-app-group="{gk}">')
                html.append(f'<div class="app-shelf-header">')
                html.append(f'<span class="app-shelf-label">{gl}</span>')
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
                    li_cls = " doc-recent" if _dir_has_recent(sd_full_path) else ""
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
        else:
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
                    dock_cls = "dock-item dock-item-recent" if _dir_has_recent(sd_path) else "dock-item"
                    html.append(
                        f'<a href="{sd}/index.html" class="{dock_cls}" data-tooltip="{sd_label} ({count})">'
                        f'<i data-lucide="{sd_icon}" class="dock-icon"></i>'
                        f'<span class="dock-label">{sd_label}</span>'
                        f'<span class="dock-count">{count}</span>'
                        f'</a>'
                    )
                html.append('</nav>')

    if doc_entries:
        # Detect if this is a work directory with flat-file work items
        is_work_dir = dir_prefix.startswith("work/to-do") or dir_prefix.startswith("work/done")
        # Detect if this is the ideas directory
        is_ideas_dir = dir_prefix == "ideas"

        html.append('<div class="hv-section documents-section">')

        if (is_work_dir or is_ideas_dir) and len(doc_entries) > 5:
            # Work items / Ideas: show filter controls and app-group shelves
            from .file_utils import _extract_status_from_text, _extract_type_from_text, _extract_tags_from_text, infer_app_group

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
                enriched.append((rel, doc_title, date_str, date_label, status, item_type, app_key, app_label, desc, work_id))

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

            html.append(f'<h2><i data-lucide="{"lightbulb" if is_ideas_dir else "file-text"}" class="section-icon"></i> {"Ideas" if is_ideas_dir else "Items"} ({len(enriched)})</h2>')
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
            if not is_ideas_dir:
                html.append('  <select class="todo-filter-select" id="todo-filter-status">')
                html.append('    <option value="">all statuses</option>')
                for s in statuses:
                    html.append(f'    <option value="{s.lower()}">{s}</option>')
                html.append('  </select>')
            html.append('</div>')

            # Group by app
            for gk in ordered_groups:
                group_items = [e for e in enriched if e[6] == gk]
                gl = app_groups_seen[gk]
                shelf_has_recent = any(
                    str(e[0]).replace("\\", "/") in recent_paths for e in group_items
                )
                shelf_cls = "app-shelf shelf-recent" if shelf_has_recent else "app-shelf"
                html.append(f'<div class="{shelf_cls}" data-app-group="{gk}">')
                html.append(f'<div class="app-shelf-header">')
                html.append(f'<span class="app-shelf-label">{gl}</span>')
                html.append(f'<span class="app-shelf-count">{len(group_items)}</span>')
                html.append(f'</div>')
                html.append(f'<ul class="doc-list todo-list" data-app-group="{gk}">')

                for rel, doc_title, date_str, date_label, status, item_type, _ak, _al, desc, work_id in group_items:
                    rel_posix = str(rel).replace("\\", "/")
                    fname_stem = PurePosixPath(rel_posix).stem
                    type_cls = "type-badge-personal" if item_type.lower() == "personal" else "type-badge-professional"
                    type_label = item_type.lower()[:4]
                    status_cls = "status-" + (status or "planned").lower().replace(" ", "-")
                    status_label = status or "—"
                    li_cls = " doc-recent" if rel_posix in recent_paths else ""
                    status_badge = f'<span class="hv-badge {status_cls}">{status_label}</span>' if not is_ideas_dir else ''
                    id_prefix = f'<span class="work-id-inline">{work_id} —</span> ' if work_id else ''
                    html.append(
                        f'<li class="{li_cls.strip()}" data-name="{doc_title.lower()}" data-type="{item_type.lower()}" data-status="{(status or "").lower()}" data-app="{gk}">'
                        f'<div class="todo-title"><a href="{fname_stem}/index.html"><i data-lucide="{"lightbulb" if is_ideas_dir else "circle-dot"}" class="doc-icon"></i>{id_prefix}{doc_title}</a>'
                        f'<span class="todo-desc">{desc}</span></div>'
                        f'<span class="hv-badge {type_cls}">{type_label}</span>'
                        f'{status_badge}'
                        f'</li>'
                    )

                html.append('</ul>')
                html.append('</div>')

        else:
            # Standard document list rendering
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

    if not subdirs and not doc_entries:
        html.append('<p class="empty-msg">No documents in this directory.</p>')

    # Detect raw HTML files in this directory and add links
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

    return "\n".join(html), title
