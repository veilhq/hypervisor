"""
Directory tree helpers and index page generators (home + subdirectory indexes).
"""

import re
from datetime import datetime, date
from pathlib import PurePosixPath

from .config import (
    HYPERSPACE_ROOT, CATEGORY_DESCRIPTIONS, CATEGORY_ICONS, ASSETS_DIR,
    hypervisor_logo_svg, eco_app_icon_svg,
)
from .file_utils import (
    dir_label, nice_name, get_title, extract_dates, sort_date, display_date,
    href_for, count_docs_under, get_dir_snippet,
    get_dir_status, get_dir_type, get_dir_tags, infer_app_group,
    compute_badges, format_badge_html, read_md, _extract_assignee_from_text,
    _extract_horizon_from_text,
)
from chips import render_chip


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

COMPACT_THRESHOLD = 10  # Switch to grouped shelves above this many subdirs


def _initials(name: str) -> str:
    """Extract up to 2 initials from a full name, or pass through short values."""
    name = name.strip()
    if len(name) <= 3:
        return name.upper()
    parts = name.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper() if parts else "?"


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

    # --- 0. Orchestrator launcher (greeting + app icon row) ---
    html.append('<div class="dashboard-wrap">')
    html.append('<div class="home-anchor">')
    html.append('<span class="home-anchor-greeting" data-home-greeting></span>')
    # App icon row — each icon in a bordered box
    html.append('<div class="launcher-row">')
    launcher_apps = [
        ("hypervisor", "Hypervisor", None),
        ("hyperagent", "Hyperagent", "launch_hyperagent"),
        ("hypereye", "HyperEye", "launch_hypereye"),
        ("hyperfield", "HyperField", "launch_dither_widget"),
        ("hyperline", "Hyperline", "launch_hyperline"),
        ("hypercycle", "Hypercycle", "launch_hypercycle"),
        ("launchdev", "LaunchDev", "launch_dev"),
    ]
    # 0-based index drives the CSS stagger, so the row scales to any number of
    # tiles. Incrementing only for rendered tiles keeps the sequence gapless
    # when an icon is missing and its tile is skipped.
    tile_index = 0
    for app_id, label, action in launcher_apps:
        icon = eco_app_icon_svg(app_id, "launcher-icon")
        if not icon:
            continue
        is_active = app_id == "hypervisor"
        cls = "launcher-box active" if is_active else "launcher-box"
        style = f'style="--launcher-i: {tile_index}"'
        if is_active:
            html.append(
                f'<div class="{cls}" {style} data-tooltip="{label}" aria-label="{label} (active)">'
                f'{icon}</div>'
            )
        else:
            html.append(
                f'<button class="{cls}" {style} data-launch="{action}" data-tooltip="{label}" aria-label="Launch {label}">'
                f'{icon}</button>'
            )
        tile_index += 1
    html.append('</div>')  # .launcher-row
    html.append('</div>')  # .home-anchor

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
        md_text = read_md(HYPERSPACE_ROOT / rel)
        from .file_utils import _extract_status_from_text
        status = _extract_status_from_text(md_text)
        if status and ("progress" in status.lower() or "discussion" in status.lower()):
            title = get_title(md_text, nice_name(parts[2]))
            dates = extract_dates(md_text)
            date_str, _ = sort_date(dates)
            done, total = _parse_task_progress(md_text)
            work_id = _extract_work_id_from_text(md_text)
            assignee = _extract_assignee_from_text(md_text)
            # Extract short description (line after H1, before metadata)
            desc = ""
            lines = md_text.splitlines()
            for ln in lines[1:]:
                stripped = ln.strip()
                if stripped == "" or stripped == "---":
                    continue
                if stripped.startswith("- ") or stripped.startswith("#"):
                    break
                if re.match(r'^-?\s*\*{0,2}[A-Za-z][A-Za-z_ ]*\*{0,2}\s*:', stripped):
                    break
                desc = stripped[:120] + ("…" if len(stripped) > 120 else "")
                break
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
                "desc": desc,
                "status": status,
                "date": date_str,
                "rel": rel,
                "done": done,
                "total": total,
                "work_id": work_id,
                "days": days_active,
                "assignee": assignee,
            })
    active_items.sort(key=lambda x: x["date"], reverse=True)

    # --- 2b. Research (recent from research/) ---
    research_items = []
    for rel in files:
        rel_posix = str(rel).replace("\\", "/")
        if not rel_posix.startswith("research/"):
            continue
        parts = PurePosixPath(rel_posix).parts
        if parts[-1].startswith("_"):
            continue
        md_text = read_md(HYPERSPACE_ROOT / rel)
        title = get_title(md_text, nice_name(rel.name))
        dates = extract_dates(md_text)
        date_str, _ = sort_date(dates)
        # Extract snippet
        desc = ""
        past_meta = False
        for ln in md_text.splitlines()[1:]:
            stripped = ln.strip()
            if not past_meta:
                if re.match(r'^-?\s*\*{0,2}[A-Za-z][A-Za-z_ ]*\*{0,2}\s*:', stripped):
                    continue
                if stripped == "" or stripped == "---":
                    continue
                past_meta = True
            if stripped.startswith("#") or stripped.startswith("```") or stripped.startswith("<"):
                continue
            if stripped == "":
                continue
            desc = stripped[:100] + ("…" if len(stripped) > 100 else "")
            break
        # Extract tags
        doc_tags = []
        for ln in md_text.splitlines()[:30]:
            m = re.match(r'^-?\s*Tags\s*:\s*(.+)', ln.strip(), re.IGNORECASE)
            if m:
                doc_tags = [t.strip().strip('`') for t in m.group(1).split(",") if t.strip()]
                break
        research_items.append({
            "rel": rel,
            "title": title,
            "desc": desc,
            "date": date_str,
            "tags": doc_tags[:3],
        })
    research_items.sort(key=lambda x: x["date"], reverse=True)
    research_items = research_items[:10]

    # --- 3. Recent Activity (up to 10 items) ---
    from .file_utils import _extract_status_from_text as _status
    recent = []
    for rel in files:
        rel_posix = str(rel).replace("\\", "/")
        if rel_posix in recent_paths:
            md_text = read_md(HYPERSPACE_ROOT / rel)
            title = get_title(md_text, nice_name(rel.name))
            dates = extract_dates(md_text)
            date_str, date_label = sort_date(dates)
            status = _status(md_text)
            # Classify event type from metadata
            if (status and status.lower() == "complete"
                    and rel_posix.startswith("work/done/")):
                event = "completed"
            elif (status and "progress" in status.lower()
                  and date_label == "updated"
                  and rel_posix.startswith("work/to-do/")):
                event = "started"
            elif rel_posix.startswith(".external/"):
                event = "uploaded"
            elif date_label == "created":
                event = "created"
            else:
                event = "updated"
            recent.append((rel, title, date_str, event))
    recent.sort(key=lambda x: x[2], reverse=True)
    recent = recent[:10]

    # Group recent items by day label
    from collections import OrderedDict
    recent_by_day = OrderedDict()
    for rel, title, date_str, event in recent:
        day = _pulse_day_header(date_str)
        recent_by_day.setdefault(day, []).append((rel, title, date_str, event))

    # --- 4. Single-column dashboard flow ---

    # Active Work section — card grid
    html.append('<div class="home-section home-section-work">')
    summary_parts = [f'{len(active_items)} in progress']
    if build_time:
        summary_parts.append(f'built {build_time}')
    pulse_summary = ' &middot; '.join(summary_parts)
    html.append(
        f'<h2 class="home-section-header"><i data-lucide="rocket" class="section-icon"></i> Active'
        f' <span class="pulse-summary">{pulse_summary}</span></h2>'
    )

    if active_items:
        html.append('<div class="work-card-grid">')
        for it in active_items:
            done, total = it["done"], it["total"]
            if total > 0:
                pct = int(round(done * 100 / total))
                progress_html = (
                    '<span class="work-card-progress">'
                    f'<span class="progress-track pulse-bar">'
                    f'<span class="progress-fill pulse-fill" style="width:{pct}%"></span>'
                    f'</span>'
                    f'<span class="work-card-progress-label">{done}/{total}</span>'
                    f'</span>'
                )
            else:
                progress_html = (
                    '<span class="work-card-progress">'
                    '<span class="progress-track progress-track-empty pulse-bar pulse-bar-empty"></span>'
                    '<span class="work-card-progress-label">&mdash;/&mdash;</span>'
                    '</span>'
                )
            days_str = f'{it["days"]}d'
            chip = (
                render_chip("filled", it["work_id"], extra_class="work-card-chip")
                if it["work_id"]
                else render_chip("outlined-muted", "&mdash;", extra_class="work-card-chip")
            )
            assignee_label = (
                f'<span class="work-card-assignee">{_initials(it["assignee"])}</span>'
                if it.get("assignee")
                else ""
            )
            desc_html = (
                f'<span class="work-card-desc">{it["desc"]}</span>'
                if it.get("desc")
                else ""
            )
            html.append(
                f'<a class="work-card" href="{href_for(it["rel"])}">'
                f'<span class="work-card-meta">{chip}{assignee_label}<span class="work-card-days">{days_str}</span></span>'
                f'<span class="work-card-title">{it["title"]}</span>'
                f'{desc_html}'
                f'{progress_html}'
                f'</a>'
            )
        html.append('</div>')
    else:
        html.append('<div class="pulse-empty">no items in progress</div>')
    html.append('</div>')  # /.home-section-work

    # Recent Activity section — action descriptions with relative time
    html.append('<div class="home-section home-section-recent">')
    html.append(
        '<h2 class="home-section-header"><i data-lucide="arrow-down-circle" class="section-icon"></i> Activity</h2>'
    )
    if recent:
        _EVENT_STYLE = {
            "created":   ("plus",       "activity-icon-new",  "Created"),
            "uploaded":  ("upload",     "activity-icon-new",  "Uploaded"),
            "started":   ("play",       "activity-icon-start", "Started"),
            "updated":   ("pen-line",   "activity-icon-upd",  "Updated"),
            "completed": ("check",      "activity-icon-done", "Completed"),
        }
        for rel, title, date_str, event in recent:
            icon_name, icon_cls, action = _EVENT_STYLE.get(event, _EVENT_STYLE["updated"])
            # Relative time
            rel_time = ""
            if date_str and not date_str.startswith("0000"):
                try:
                    dt = datetime.strptime(date_str[:16], "%Y-%m-%dT%H:%M")
                    delta = datetime.now() - dt
                    hours = int(delta.total_seconds() // 3600)
                    if hours < 1:
                        rel_time = "just now"
                    elif hours < 24:
                        rel_time = f"{hours}h ago"
                    elif hours < 48:
                        rel_time = "yesterday"
                    else:
                        rel_time = f"{hours // 24}d ago"
                except ValueError:
                    rel_time = ""
            html.append(
                f'<a class="pulse-row pulse-row-recent" href="{href_for(rel)}">'
                f'<span class="activity-indicator {icon_cls}"><i data-lucide="{icon_name}" class="activity-indicator-icon"></i></span>'
                f'<span class="pulse-title">{action} <strong>{title}</strong></span>'
                f'<span class="pulse-right">{rel_time}</span>'
                f'</a>'
            )
    else:
        html.append('<div class="pulse-empty">no recent activity</div>')
    html.append('</div>')  # /.home-section-recent

    # Research section — card grid
    if research_items:
        html.append('<div class="home-section home-section-research">')
        html.append(
            '<h2 class="home-section-header"><i data-lucide="flask-conical" class="section-icon"></i> Recent Research</h2>'
        )
        html.append('<div class="idea-card-grid">')
        for item in research_items:
            tags_html = ""
            if item["tags"]:
                tags_html = '<span class="idea-card-tags">' + ''.join(
                    f'<span class="idea-card-tag">{t}</span>' for t in item["tags"]
                ) + '</span>'
            desc_html = f'<span class="idea-card-desc">{item["desc"]}</span>' if item["desc"] else ''
            date_display = display_date(item["date"]) if item["date"] != "0000-00-00" else ""
            html.append(
                f'<a class="idea-card" href="{href_for(item["rel"])}">'
                f'<span class="idea-card-title">{item["title"]}</span>'
                f'{desc_html}'
                f'<span class="idea-card-footer">{tags_html}<span class="idea-card-date">{date_display}</span></span>'
                f'</a>'
            )
        html.append('</div>')
        html.append('</div>')  # /.home-section-research

    # Pinned section (rendered client-side by pins.js)
    html.append('<div class="home-section home-section-pins" data-pins-home-mount>')
    html.append(
        '<h2 class="home-section-header"><i data-lucide="pin" class="section-icon"></i> Pinned'
        ' <span class="pins-home-count" data-pins-home-count></span></h2>'
    )
    html.append(
        '<div class="pins-home-list" data-pins-home-list>'
        '<div class="pins-home-loading">loading pins&hellip;</div>'
        '</div>'
    )
    html.append('</div>')  # /.home-section-pins
    html.append('</div>')  # /.dashboard-wrap

    # --- 5. Root-level documents (full width, bottom) ---
    if top_docs:
        html.append('<div class="home-section root-docs-section">')
        html.append('<h2 class="home-section-header"><i data-lucide="files" class="section-icon"></i> Root Documents</h2>')
        html.append('<ul class="doc-list">')

        enriched = []
        for rel in top_docs:
            md_text = read_md(HYPERSPACE_ROOT / rel)
            title = get_title(md_text, nice_name(rel.name))
            dates = extract_dates(md_text)
            date_str, date_label = sort_date(dates)
            enriched.append((rel, title, date_str, date_label))
        enriched.sort(key=lambda x: x[2], reverse=True)

        for rel, title, date_str, date_label in enriched:
            rel_posix = str(rel).replace("\\", "/")
            date_content = display_date(date_str) if date_label else ""
            badge = '<span class="label-badge label-badge-muted">root</span>'
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
            md_text = read_md(candidate_path)
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
            md_text = read_md(md_path)
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
    html.append('<div class="content-section documents-section">')
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
            md_text = read_md(HYPERSPACE_ROOT / rel)
            doc_title = get_title(md_text, name)
            dates = extract_dates(md_text)
            date_str, date_label = sort_date(dates)
            # Extract tags
            doc_tags = []
            for ln in md_text.splitlines()[:30]:
                m = re.match(r'^-?\s*Tags\s*:\s*(.+)', ln.strip(), re.IGNORECASE)
                if m:
                    doc_tags = [t.strip().strip('`') for t in m.group(1).split(",") if t.strip()]
                    break
            # Extract snippet (first body line after metadata)
            doc_snippet = ""
            past_meta = False
            for ln in md_text.splitlines()[1:]:
                stripped = ln.strip()
                if not past_meta:
                    if re.match(r'^-?\s*\*{0,2}[A-Za-z][A-Za-z_ ]*\*{0,2}\s*:', stripped):
                        continue
                    if stripped == "" or stripped == "---":
                        continue
                    past_meta = True
                if stripped.startswith("#") or stripped.startswith("```") or stripped.startswith("<") or stripped == "---":
                    continue
                if stripped == "":
                    continue
                doc_snippet = stripped[:100] + ("…" if len(stripped) > 100 else "")
                break
            enriched_child.append((rel, doc_title, date_str, date_label, doc_tags, doc_snippet))
        dated_c = [(r, t, d, l, tags, sn) for r, t, d, l, tags, sn in enriched_child if d != "0000-00-00"]
        undated_c = [(r, t, d, l, tags, sn) for r, t, d, l, tags, sn in enriched_child if d == "0000-00-00"]
        dated_c.sort(key=lambda x: x[2], reverse=True)
        undated_c.sort(key=lambda x: x[1].lower())
        enriched_child = dated_c + undated_c
        for rel, doc_title, date_str, date_label, doc_tags, doc_snippet in enriched_child:
            rel_posix = str(rel).replace("\\", "/")
            fname_stem = PurePosixPath(rel_posix).stem
            date_content = display_date(date_str) if date_label else ""
            li_cls = ' class="doc-recent"' if rel_posix in recent_paths else ''
            # Tags as small chips
            tags_html = ""
            if doc_tags:
                tags_html = '<span class="doc-row-tags">' + ''.join(
                    f'<span class="doc-row-tag">{t}</span>' for t in doc_tags[:4]
                ) + '</span>'
            # Snippet
            snippet_html = f'<span class="doc-row-snippet">{doc_snippet}</span>' if doc_snippet else ''
            html.append(
                f'<li{li_cls}>'
                f'<a href="{sd}/{fname_stem}/index.html"><i data-lucide="file-text" class="doc-icon"></i> {doc_title}</a>'
                f'<span class="doc-date">{date_content}</span>'
                f'{snippet_html}{tags_html}'
                f'</li>'
            )
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

    html.append('<div class="content-section documents-section">')
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
                f'<span class="label-badge {type_cls}">{type_label}</span>'
                f'<span class="label-badge {status_cls}">{status_label}</span>'
                f'</li>'
            )

        html.append('</ul>')
        html.append('</div>')

    html.append('</div>')



def _meta_description(dir_prefix):
    """Return the description paragraph from a directory's _meta.md, or ''.

    The _meta.md structure is: H1, a summary line, dash-prefixed metadata, a
    `---` separator, then the body. The card description is the first real
    content line after that `---` separator — keying off the rule is more
    robust than trying to detect the end of the metadata block heuristically.
    Falls back to the first non-empty body line if no `---` is present.
    """
    meta_path = HYPERSPACE_ROOT / dir_prefix / "_meta.md"
    if not meta_path.exists():
        return ""
    md_text = read_md(meta_path)
    lines = md_text.splitlines()

    # Find the first horizontal-rule separator; the description follows it.
    start = 0
    for i, ln in enumerate(lines):
        if ln.strip() == "---":
            start = i + 1
            break

    for ln in lines[start:]:
        stripped = ln.strip()
        if not stripped:
            continue
        if stripped.startswith(("#", "```", "<", "-", "*", "|")) or stripped == "---":
            continue
        return stripped
    return ""


def _render_subdirs_dashboard(html, files, dir_prefix, subdirs, dir_has_recent_fn):
    """Render subdirectories as rich dashboard cards (title, description, count,
    and a short preview of recent docs). Used for the Project Context landing so
    external users can dig into each subject area from the page body, not just
    the nav rail.
    """
    html.append(f'<div class="card-grid dir-dashboard" aria-label="{dir_label(PurePosixPath(dir_prefix).name)} sections">')
    for sd in subdirs:
        sd_path = f"{dir_prefix}/{sd}"
        # Prefer the subdir's _meta.md H1 for the card title, else the label.
        sd_title = dir_label(sd)
        meta_path = HYPERSPACE_ROOT / sd_path / "_meta.md"
        if meta_path.exists():
            extracted = get_title(read_md(meta_path), "")
            if extracted:
                sd_title = extracted
        sd_desc = (
            _meta_description(sd_path)
            or CATEGORY_DESCRIPTIONS.get(sd, "")
            or f"Documents in {sd_title}."
        )
        count = count_docs_under(files, sd_path)
        sd_icon = CATEGORY_ICONS.get(sd, "folder")
        recent_cls = " card-recent" if dir_has_recent_fn(sd_path) else ""

        # Preview: up to 3 most-recent docs directly under this subdir.
        _, child_docs = collect_dir_contents(files, sd_path)
        previews = []
        for rel, name in child_docs:
            if PurePosixPath(str(rel).replace("\\", "/")).name == "_meta.md":
                continue
            md_text = read_md(HYPERSPACE_ROOT / rel)
            doc_title = get_title(md_text, name)
            dates = extract_dates(md_text)
            date_str, _ = sort_date(dates)
            previews.append((doc_title, date_str))
        previews.sort(key=lambda x: x[1], reverse=True)
        previews = previews[:3]

        html.append(f'<a href="/{dir_prefix}/{sd}/index.html" class="card dir-dashboard-card{recent_cls}">')
        html.append('<div class="dir-card-head">')
        html.append(f'<i data-lucide="{sd_icon}" class="dir-card-icon"></i>')
        html.append(f'<span class="card-name">{sd_title}</span>')
        html.append('</div>')
        if sd_desc:
            html.append(f'<span class="card-desc">{sd_desc}</span>')
        if previews:
            html.append('<ul class="dir-card-preview">')
            for doc_title, _ in previews:
                html.append(
                    f'<li><i data-lucide="file-text" class="dir-card-preview-icon"></i>'
                    f'<span>{doc_title}</span></li>'
                )
            html.append('</ul>')
        html.append(f'<span class="card-count">{count} doc{"s" if count != 1 else ""}</span>')
        html.append('</a>')
    html.append('</div>')


def _render_subdirs_dock(html, files, dir_prefix, subdirs, dir_has_recent_fn):
    """Render subdirectories as a dock-style strip (2-10 subdirs, non-top-level)."""
    # Determine if this is a top-level category (children shown in site nav)
    is_top_level = "/" not in dir_prefix and "\\" not in dir_prefix
    if is_top_level:
        # Project Context gets a rich dashboard in the page body so external
        # users can dig into each subject area, not just the nav rail. Other
        # top-level categories rely on the nav rail (children listed there).
        if dir_prefix == "context":
            _render_subdirs_dashboard(html, files, dir_prefix, subdirs, dir_has_recent_fn)
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

    html.append('<div class="content-section documents-section">')

    enriched = []
    statuses_set = set()
    app_groups_seen = {}
    horizons_seen = {}
    _APP_GROUP_ORDER = ["portal", "portal-cms", "hyperspace", "infrastructure", "other"]
    _HORIZON_ORDER = ["Sprint", "Sprint+1", "Sprint+2", "Sprint+3", "Backlog"]

    is_todo = dir_prefix.startswith("work/to-do")

    for rel, name in doc_entries:
        md_text = read_md(HYPERSPACE_ROOT / rel)
        doc_title = get_title(md_text, name)
        dates = extract_dates(md_text)
        date_str, date_label = sort_date(dates)
        status = _extract_status_from_text(md_text) or ""
        item_type = _extract_type_from_text(md_text) or "professional"
        tags = _extract_tags_from_text(md_text)
        app_label, app_key = infer_app_group(tags)
        horizon = _extract_horizon_from_text(md_text) or "Backlog"
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
            desc = stripped[:120] + ("…" if len(stripped) > 120 else "")
            break

        if status:
            statuses_set.add(status)
        if app_key not in app_groups_seen:
            app_groups_seen[app_key] = app_label
        if horizon not in horizons_seen:
            horizons_seen[horizon] = horizon
        badges_html = format_badge_html(compute_badges(md_text, dates.get("updated")))
        enriched.append((rel, doc_title, date_str, date_label, status, item_type, app_key, app_label, desc, work_id, badges_html, horizon))

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

    # Sort within each group by work item ID (descending — newest first)
    def _wi_sort_key(e):
        wid = e[9]  # work_id field
        if wid and wid.startswith("WI-"):
            try:
                return -int(wid[3:])
            except ValueError:
                pass
        return 0

    enriched.sort(key=_wi_sort_key)

    # Group by Horizon for work/to-do, flat for everything else
    if is_todo and not is_ideas:
        for hz in _HORIZON_ORDER:
            group_items = [e for e in enriched if e[11] == hz]
            if not group_items:
                continue
            hz_slug = hz.lower().replace("+", "plus")
            html.append(f'<div class="app-shelf horizon-shelf" data-horizon-group="{hz_slug}">')
            html.append(f'<div class="app-shelf-header">')
            html.append(f'<span class="app-shelf-label">{hz}</span>')
            html.append(f'<span class="app-shelf-count">{len(group_items)}</span>')
            html.append(f'</div>')
            html.append('<ul class="doc-list todo-list">')
            for rel, doc_title, date_str, date_label, status, item_type, app_key, _al, desc, work_id, badges_html, _hz in group_items:
                _render_work_item_row(html, rel, doc_title, status, item_type, app_key, desc, work_id, badges_html, recent_paths, is_ideas)
            html.append('</ul>')
            html.append('</div>')
    else:
        html.append('<ul class="doc-list todo-list">')
        for rel, doc_title, date_str, date_label, status, item_type, app_key, _al, desc, work_id, badges_html, _hz in enriched:
            _render_work_item_row(html, rel, doc_title, status, item_type, app_key, desc, work_id, badges_html, recent_paths, is_ideas)
        html.append('</ul>')

    html.append('</div>')


def _render_work_item_row(html, rel, doc_title, status, item_type, app_key, desc, work_id, badges_html, recent_paths, is_ideas):
    """Render a single work item row (shared between grouped and flat views)."""
    rel_posix = str(rel).replace("\\", "/")
    fname_stem = PurePosixPath(rel_posix).stem
    type_cls = "type-badge-personal" if item_type.lower() == "personal" else "type-badge-professional"
    type_label = item_type.lower()[:4]
    status_cls = "status-" + (status or "planned").lower().replace(" ", "-")
    status_label = status or "—"
    li_cls = " doc-recent" if rel_posix in recent_paths else ""
    status_badge = f'<span class="label-badge {status_cls}">{status_label}</span>' if not is_ideas else ''
    id_prefix = f'<span class="work-id-inline">{work_id} —</span> ' if work_id else ''
    html.append(
        f'<li class="{li_cls.strip()}" data-name="{doc_title.lower()}" data-type="{item_type.lower()}" data-status="{(status or "").lower()}" data-app="{app_key}">'
        f'<div class="todo-title"><a href="{fname_stem}/index.html"><i data-lucide="{"lightbulb" if is_ideas else "circle-dot"}" class="doc-icon"></i>{id_prefix}{doc_title}</a>'
        f'<span class="todo-desc">{desc}</span></div>'
        f'<div class="todo-badges">{badges_html}'
        f'<span class="label-badge {type_cls}">{type_label}</span>'
        f'{status_badge}</div>'
        f'</li>'
    )



def _render_doc_list_standard(html, files, dir_prefix, doc_entries, recent_paths):
    """Render a standard document list (non-work, non-ideas directories)."""
    html.append('<div class="content-section documents-section">')
    html.append('<h2><i data-lucide="file-text" class="section-icon"></i> Documents</h2>')
    html.append('<ul class="doc-list">')

    # Enrich entries with date metadata for sorting
    enriched = []
    for rel, name in doc_entries:
        md_text = read_md(HYPERSPACE_ROOT / rel)
        doc_title = get_title(md_text, name)
        dates = extract_dates(md_text)
        date_str, date_label = sort_date(dates)
        # Extract tags
        doc_tags = []
        for ln in md_text.splitlines()[:30]:
            m = re.match(r'^-?\s*Tags\s*:\s*(.+)', ln.strip(), re.IGNORECASE)
            if m:
                doc_tags = [t.strip().strip('`') for t in m.group(1).split(",") if t.strip()]
                break
        # Extract snippet (first body line after metadata)
        doc_snippet = ""
        past_meta = False
        for ln in md_text.splitlines()[1:]:
            stripped = ln.strip()
            if not past_meta:
                if re.match(r'^-?\s*\*{0,2}[A-Za-z][A-Za-z_ ]*\*{0,2}\s*:', stripped):
                    continue
                if stripped == "" or stripped == "---":
                    continue
                past_meta = True
            if stripped.startswith("#") or stripped.startswith("```") or stripped.startswith("<") or stripped == "---":
                continue
            if stripped == "":
                continue
            doc_snippet = stripped[:100] + ("…" if len(stripped) > 100 else "")
            break
        enriched.append((rel, doc_title, date_str, date_label, doc_tags, doc_snippet))

    # Sort: dated docs first (newest to oldest), undated docs last (by title)
    dated = [(r, t, d, l, tags, sn) for r, t, d, l, tags, sn in enriched if d != "0000-00-00"]
    undated = [(r, t, d, l, tags, sn) for r, t, d, l, tags, sn in enriched if d == "0000-00-00"]
    dated.sort(key=lambda x: x[2], reverse=True)
    undated.sort(key=lambda x: x[1].lower())
    enriched = dated + undated

    is_external = dir_prefix == ".external"

    for rel, doc_title, date_str, date_label, doc_tags, doc_snippet in enriched:
        rel_posix = str(rel).replace("\\", "/")
        fname_stem = PurePosixPath(rel_posix).stem
        date_content = display_date(date_str) if date_label else ""
        li_cls = ' class="doc-recent"' if rel_posix in recent_paths else ''
        # Tags as small chips
        tags_html = ""
        if doc_tags:
            tags_html = '<span class="doc-row-tags">' + ''.join(
                f'<span class="doc-row-tag">{t}</span>' for t in doc_tags[:4]
            ) + '</span>'
        # Snippet
        snippet_html = f'<span class="doc-row-snippet">{doc_snippet}</span>' if doc_snippet else ''
        # Hidden doc-path for external delete buttons (consumed by drop-import.js)
        doc_path_html = f'<span class="doc-path">{PurePosixPath(rel_posix).name}</span>' if is_external else ''
        html.append(
            f'<li{li_cls}>'
            f'<a href="{fname_stem}/index.html"><i data-lucide="file-text" class="doc-icon"></i> {doc_title}</a>'
            f'<span class="doc-date">{date_content}</span>'
            f'{snippet_html}{tags_html}{doc_path_html}'
            f'</li>'
        )
    html.append('</ul>')
    html.append('</div>')


def _render_prototypes(html, dir_prefix):
    """Render links to raw HTML prototype files in the directory."""
    dir_path = HYPERSPACE_ROOT / dir_prefix
    if dir_path.is_dir():
        html_files = sorted(dir_path.glob("*.html"))
        if html_files:
            html.append('<div class="content-section documents-section">')
            html.append('<h2><i data-lucide="code" class="section-icon"></i> Prototypes</h2>')
            html.append('<ul class="doc-list">')
            for hf in html_files:
                hf_name = hf.stem.replace("-", " ").replace("_", " ").title()
                html.append(f'<li><a href="{hf.stem}/index.html"><i data-lucide="layout" class="doc-icon"></i> {hf_name}</a>'
                            f'<span class="doc-path">{hf.name}</span></li>')
            html.append('</ul>')
            html.append('</div>')
