"""Page builders — homepage, pinboard, utility pages, learn section.

All builders now output content fragments (JSON) for the SPA shell architecture.
"""

import shutil
from datetime import datetime

from .config import HYPERSPACE_ROOT, OUTPUT_DIR, SKIP_DIRS
from .file_utils import get_title, nice_name
from .markdown_processing import render_markdown
from .directory_index import generate_home_content
from .fragment import build_fragment, write_fragment

_HYPERVISOR_DIR = OUTPUT_DIR.parent
UTILITIES_DIR = _HYPERVISOR_DIR / "utilities"
LEARN_DIR = _HYPERVISOR_DIR / "learn"


def build_homepage(files, all_dirs, build_id, recent_paths=None, util_count=0):
    """Generate the site homepage as a content fragment."""
    page_count = len(files) + len(all_dirs) + 1 + util_count
    build_stats = {
        "files": len(files),
        "pages": page_count,
        "indexes": len(all_dirs),
        "output": str(OUTPUT_DIR),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    home_content = generate_home_content(files, build_stats, recent_paths=recent_paths)

    fragment = build_fragment(
        home_content, "Hypervisor", "",
        page_type="home", source_path="",
    )
    fragment_path = OUTPUT_DIR / "content" / "home.json"
    write_fragment(fragment, fragment_path)


def build_404_page(build_id):
    """Generate a 404 Not Found content fragment."""
    content_html = """\
<div class="not-found">
  <p class="not-found-msg">
    :you aren't supposed to be here
  </p>
</div>"""
    fragment = build_fragment(
        content_html, "404 Not Found", "404",
        page_type="utility", source_path="404",
    )
    fragment_path = OUTPUT_DIR / "content" / "404.json"
    write_fragment(fragment, fragment_path)


def _inject_health_data(html_content: str) -> str:
    """Replace __HEALTH_DATA__ placeholder with live analytics JSON."""
    import json
    try:
        from hv_mcp.index import rebuild_index
        from hv_mcp.analytics import health_report, stale_documents, tag_analytics

        # Ensure index is current (may already be built by the main build)
        rebuild_index()

        data = {
            "health": health_report(),
            "stale": stale_documents(days=30),
            "tags": tag_analytics(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        return html_content.replace("__HEALTH_DATA__", json.dumps(data, ensure_ascii=False))
    except Exception:
        # Fallback: inject empty data so the page doesn't break
        fallback = json.dumps({
            "health": {"current": {"total": 0, "valid": 0, "violations": 0}, "previous": None, "trend": "unknown", "docs_added_since_last": 0, "top_remaining_issues": [], "by_directory": {}},
            "stale": {"threshold_days": 30, "total_stale": 0},
            "tags": {"summary": {"total_tags_in_registry": 0, "tags_actively_used": 0, "total_documents": 0, "avg_tags_per_doc": 0}, "co_occurrence": [], "underused": [], "merge_candidates": [], "orphaned_tags": []},
            "timestamp": "build error",
        })
        return html_content.replace("__HEALTH_DATA__", fallback)


def build_utility_pages(build_id):
    """Generate utility page content fragments from HTML snippets in the utilities directory."""
    util_count = 0
    if not UTILITIES_DIR.exists():
        return util_count

    for util_file in sorted(UTILITIES_DIR.glob("*.html")):
        util_content = util_file.read_text(encoding="utf-8")

        # Data injection: if the page contains __HEALTH_DATA__, run the builder
        if "__HEALTH_DATA__" in util_content:
            util_content = _inject_health_data(util_content)

        util_name = util_file.stem.replace("-", " ").replace("_", " ").title()
        util_rel = f"_utils/{util_file.stem}"

        fragment = build_fragment(
            util_content, util_name, util_rel,
            page_type="utility", source_path=f"utility: {util_file.stem}",
        )
        fragment_path = OUTPUT_DIR / "content" / f"_utils/{util_file.stem}.json"
        write_fragment(fragment, fragment_path)

        # Copy companion asset directories alongside the fragment
        companion_dir = UTILITIES_DIR / util_file.stem
        if companion_dir.is_dir():
            out_companion = OUTPUT_DIR / "_utils" / util_file.stem
            out_companion.mkdir(parents=True, exist_ok=True)
            for item in companion_dir.rglob("*"):
                if item.is_file():
                    rel_to_companion = item.relative_to(companion_dir)
                    dest = out_companion / rel_to_companion
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(item, dest)

        util_count += 1

    return util_count


# ---------------------------------------------------------------------------
# Learn section — self-contained technical walkthrough of Hypervisor internals
# ---------------------------------------------------------------------------


def build_learn_pages(build_id):
    """Generate the /learn/ section as content fragments.

    Returns the number of learn pages generated.
    """
    learn_count = 0
    if not LEARN_DIR.exists():
        return learn_count

    learn_files = sorted(LEARN_DIR.glob("*.md"))
    if not learn_files:
        return learn_count

    # Build individual learn page fragments
    learn_entries = []  # (slug, title, description, order) for the index
    for md_file in learn_files:
        md_text = md_file.read_text(encoding="utf-8")
        title = get_title(md_text, nice_name(md_file.name))
        content_html, toc_html = render_markdown(md_text, source_path=f"learn/{md_file.name}")

        slug = md_file.stem
        rel_path_str = f"learn/{slug}"

        fragment = build_fragment(
            content_html, title, rel_path_str,
            toc_html=toc_html, page_type="learn",
            source_path=f"learn/{md_file.name}",
        )
        fragment_path = OUTPUT_DIR / "content" / f"learn/{slug}.json"
        write_fragment(fragment, fragment_path)

        # Extract description (first non-heading, non-metadata paragraph)
        desc = ""
        for line in md_text.split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                desc = stripped[:120]
                break

        learn_entries.append((slug, title, desc))
        learn_count += 1

    # Build learn index fragment
    _build_learn_index(learn_entries, build_id)
    learn_count += 1  # Count the index page

    return learn_count


def _build_learn_index(entries, build_id):
    """Generate the learn section index as a content fragment."""
    cards_html = '<div class="learn-index">\n'
    cards_html += '<div class="dir-header">\n'
    cards_html += '<div class="dir-header-top">\n'
    cards_html += '<i data-lucide="graduation-cap" class="dir-header-icon"></i>\n'
    cards_html += '<h1 class="dir-header-title">Learn Hypervisor</h1>\n'
    cards_html += '</div>\n'
    cards_html += '<div class="dir-header-desc">A guided walkthrough of how Hypervisor works — architecture, build pipeline, styling, interactivity, and design decisions.</div>\n'
    cards_html += '</div>\n'
    cards_html += '<div class="card-grid">\n'

    for i, (slug, title, desc) in enumerate(entries):
        card_num = f"{i + 1:02d}"
        cards_html += (
            f'<a href="/learn/{slug}/index.html" class="card">'
            f'<span class="card-num">{card_num}</span>'
            f'<span class="card-title">{title}</span>'
            f'<span class="card-desc">{desc}</span>'
            f'</a>\n'
        )

    cards_html += '</div>\n</div>\n'

    fragment = build_fragment(
        cards_html, "Learn Hypervisor", "learn",
        page_type="learn", source_path="learn",
    )
    fragment_path = OUTPUT_DIR / "content" / "learn.json"
    write_fragment(fragment, fragment_path)


def build_pinboard_page(build_id):
    """Generate the pinboard as a content fragment.

    The pinboard is client-side rendered — pins are stored in localStorage
    and the JS module populates the content dynamically.
    """
    content_html = """\
<div class="pinboard-page">
  <div class="dir-header">
    <div class="dir-header-top">
      <i data-lucide="pin" class="dir-header-icon"></i>
      <h1 class="dir-header-title">Pinboard</h1>
    </div>
    <div class="dir-header-desc">Documents you've pinned for quick access. Pins are stored locally in your browser.</div>
  </div>
  <div class="pinboard-content"></div>
</div>"""

    fragment = build_fragment(
        content_html, "Pinboard", "_pins",
        page_type="pinboard", source_path="_pins",
    )
    fragment_path = OUTPUT_DIR / "content" / "_pins.json"
    write_fragment(fragment, fragment_path)


def build_raw_html_pages():
    """Copy standalone .html files from hyperspace into site output as-is (no template wrapping).

    These are raw HTML prototypes, POCs, or interactive demos that should render
    exactly as written without Hypervisor's page chrome.
    """
    count = 0
    for html_file in sorted(HYPERSPACE_ROOT.rglob("*.html")):
        rel = html_file.relative_to(HYPERSPACE_ROOT)
        # Skip files inside directories we normally skip
        if any(p in SKIP_DIRS for p in rel.parts):
            continue
        # Skip anything inside .hypervisor (utilities have their own pipeline)
        if ".hypervisor" in rel.parts:
            continue
        out_dir = OUTPUT_DIR / rel.parent / html_file.stem
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(html_file, out_dir / "index.html")
        count += 1
    return count
