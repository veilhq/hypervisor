#!/usr/bin/env python3
"""
Hypervisor — Static site generator for .hyperspace markdown documents.

Hub-and-spoke navigation: site nav rail → category indexes → doc pages. The homepage is a status dashboard (Workspace Pulse + Pinned).
No sidebar. Persistent search bar in top bar on every page.

Usage:
    pip install markdown pygments
    python build.py
"""

import json
import shutil
import sys
import time
from datetime import datetime
from pathlib import PurePosixPath

from site_utils.config import HYPERSPACE_ROOT, OUTPUT_DIR, ASSETS_DIR, SKIP_DIRS
from site_utils.file_utils import collect_files, html_dir_for, nice_name, get_title, extract_dates, sort_date, count_docs_under
from site_utils.build_cache import BuildCache

# Structured logging (shared ecosystem logger)
sys.path.insert(0, str(OUTPUT_DIR.parent.parent.resolve()))
from hyper_logging import setup_logger  # noqa: E402

logger = setup_logger("hypervisor")

# Utilities directory (HTML snippets for interactive tools)
_HYPERVISOR_DIR = OUTPUT_DIR.parent
UTILITIES_DIR = _HYPERVISOR_DIR / "utilities"
CSS_DIR = ASSETS_DIR / "css"
JS_DIR = ASSETS_DIR / "js"
from site_utils.markdown_processing import render_markdown
from site_utils.search import build_search_index
from site_utils.backlinks import build_backlink_index, render_backlinks_html
from site_utils.directory_index import collect_all_dirs, generate_dir_index_content
from site_utils.page_generation import set_nav_categories, build_shell
from site_utils.fragment import build_fragment, write_fragment


# ---------------------------------------------------------------------------
# Build functions — importable by both build.py and hypervisor-app.py
# ---------------------------------------------------------------------------

def prepare_output():
    """Clean and recreate the output directory."""
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)


def copy_assets():
    """Concatenate CSS and JS modules, copy static assets to the output directory."""
    # Concatenate CSS modules into site/style.css
    # Order: numbered files first (sorted), then zz-* files last
    if CSS_DIR.exists():
        css_parts = []
        # Main CSS files (numbered, sorted)
        for css_file in sorted(CSS_DIR.glob("*.css")):
            if css_file.name.startswith("zz-"):
                continue
            css_parts.append(css_file.read_text(encoding="utf-8"))
        # Utility sub-styles (if utilities/ subdir exists)
        util_css_dir = CSS_DIR / "utilities"
        if util_css_dir.exists():
            for css_file in sorted(util_css_dir.glob("*.css")):
                css_parts.append(css_file.read_text(encoding="utf-8"))
        # zz-* files last (accessibility overrides)
        for css_file in sorted(CSS_DIR.glob("zz-*.css")):
            css_parts.append(css_file.read_text(encoding="utf-8"))
        (OUTPUT_DIR / "style.css").write_text("\n".join(css_parts), encoding="utf-8")
    else:
        src = ASSETS_DIR / "style.css"
        if src.exists():
            shutil.copy2(src, OUTPUT_DIR / "style.css")

    # Concatenate JS modules into site/app.js
    # Order: core/ → features/ → webgl/ → screensaver/
    if JS_DIR.exists():
        js_parts = []
        # Core modules (sorted — 00-core.js must be first)
        core_dir = JS_DIR / "core"
        if core_dir.exists():
            for js_file in sorted(core_dir.glob("*.js")):
                js_parts.append(js_file.read_text(encoding="utf-8"))
        # Feature modules (sorted, zz-* last)
        features_dir = JS_DIR / "features"
        if features_dir.exists():
            for js_file in sorted(features_dir.glob("*.js")):
                if js_file.name.startswith("zz-"):
                    continue
                js_parts.append(js_file.read_text(encoding="utf-8"))
        # WebGL modules (sorted — HyperGL layer, loads before screensaver)
        webgl_dir = JS_DIR / "webgl"
        if webgl_dir.exists():
            for js_file in sorted(webgl_dir.glob("*.js")):
                if js_file.name.startswith("zz-"):
                    continue
                js_parts.append(js_file.read_text(encoding="utf-8"))
        # Screensaver modules (sorted — 00-engine-head first, zz-engine-tail last)
        ss_dir = JS_DIR / "screensaver"
        if ss_dir.exists():
            for js_file in sorted(ss_dir.glob("*.js")):
                if js_file.name.startswith("zz-"):
                    continue
                js_parts.append(js_file.read_text(encoding="utf-8"))
            # Screensaver tail
            for js_file in sorted(ss_dir.glob("zz-*.js")):
                js_parts.append(js_file.read_text(encoding="utf-8"))
        # Feature zz-* files last (accessibility closes the IIFE)
        if features_dir.exists():
            for js_file in sorted(features_dir.glob("zz-*.js")):
                js_parts.append(js_file.read_text(encoding="utf-8"))
        if js_parts:
            (OUTPUT_DIR / "app.js").write_text("\n".join(js_parts), encoding="utf-8")


def build_doc_pages(files, backlink_index, build_id, cache=None):
    """Render each markdown file into a content fragment JSON.

    If a BuildCache is provided, unchanged docs are skipped.
    Returns the number of fragments that were actually rendered (cache misses).
    """
    rendered = 0
    for rel in files:
        md_path = HYPERSPACE_ROOT / rel
        md_text = md_path.read_text(encoding="utf-8")

        # Check cache — skip rendering if content unchanged and output exists
        if cache and cache.is_unchanged(rel, md_text):
            continue

        title = get_title(md_text, nice_name(rel.name))
        content_html, toc_html = render_markdown(md_text, source_path=str(rel).replace("\\", "/"))
        hdir = html_dir_for(rel)

        rel_posix = str(rel).replace("\\", "/")
        doc_backlinks = backlink_index.get(rel_posix, [])
        backlinks_html = render_backlinks_html(doc_backlinks)

        fragment = build_fragment(
            content_html, title, rel_posix,
            toc_html=toc_html, backlinks_html=backlinks_html,
            page_type="doc", source_path=rel_posix,
        )

        # Write fragment to site/content/{hdir}.json
        fragment_path = OUTPUT_DIR / "content" / (str(PurePosixPath(hdir)) + ".json")
        write_fragment(fragment, fragment_path)

        # Update cache with new hash
        if cache:
            cache.update(rel, md_text)

        rendered += 1

    return rendered


def compute_recent_paths(files):
    """Return the set of recently updated file paths (top 10 by datetime)."""
    recent_paths = set()
    candidates = []
    for rel in files:
        md_text = (HYPERSPACE_ROOT / rel).read_text(encoding="utf-8")
        dates = extract_dates(md_text)
        date_str, _ = sort_date(dates)
        if date_str != "0000-00-00T00:00":
            candidates.append((rel, date_str))
    candidates.sort(key=lambda x: x[1], reverse=True)
    for rel, _ in candidates[:10]:
        recent_paths.add(str(rel).replace("\\", "/"))
    return recent_paths


def build_indexes(files, build_id, recent_paths=None):
    """Generate directory index fragments for every directory containing docs.

    Always regenerates indexes (they depend on the current file list, not just
    their own content) and prunes orphaned output directories whose source
    files no longer exist.
    """
    if recent_paths is None:
        recent_paths = compute_recent_paths(files)

    all_dirs = collect_all_dirs(files)
    for d in sorted(all_dirs):
        content_html, page_title = generate_dir_index_content(files, d, recent_paths=recent_paths)

        fragment = build_fragment(
            content_html, page_title, d,
            page_type="index", source_path=d,
        )

        fragment_path = OUTPUT_DIR / "content" / (d + ".json")
        write_fragment(fragment, fragment_path)

    # Prune orphaned doc output files (source .md was deleted)
    _prune_orphaned_outputs(files)

    return all_dirs


def _prune_orphaned_outputs(files):
    """Remove fragment JSON files whose source .md files no longer exist.

    Walks the content output directory and removes any fragment file that doesn't
    correspond to a current source file or directory index.
    """
    import os

    content_dir = OUTPUT_DIR / "content"
    if not content_dir.exists():
        return

    # Build set of expected fragment paths from current source files
    expected_fragments = set()
    for rel in files:
        hdir = html_dir_for(rel)
        expected_fragments.add(str(PurePosixPath(hdir)) + ".json")

    # Also include directory indexes
    all_dirs = set(collect_all_dirs(files))
    for d in all_dirs:
        expected_fragments.add(d + ".json")

    # Also include raw HTML prototype fragments
    for html_file in sorted(HYPERSPACE_ROOT.rglob("*.html")):
        rel = html_file.relative_to(HYPERSPACE_ROOT)
        if any(p in SKIP_DIRS for p in rel.parts):
            continue
        if ".hypervisor" in rel.parts:
            continue
        expected_fragments.add(str(PurePosixPath(rel.parent / html_file.stem)) + ".json")

    # Special fragments (never pruned)
    skip_prefixes = ("_utils", "learn", "_pins", "_about", "home")

    # Walk content directory and find orphaned fragment files
    for root_dir, dirs, dir_files in os.walk(str(content_dir)):
        for fname in dir_files:
            if not fname.endswith(".json"):
                continue
            fpath = os.path.join(root_dir, fname)
            try:
                from pathlib import Path
                rel_path = Path(fpath).relative_to(content_dir)
                rel_str = str(PurePosixPath(rel_path)).replace("\\", "/")
            except (ValueError, OSError):
                continue

            # Skip special fragments
            if any(rel_str.startswith(p) for p in skip_prefixes):
                continue

            # If this fragment doesn't correspond to any current source, remove it
            if rel_str not in expected_fragments:
                try:
                    os.remove(fpath)
                except OSError:
                    pass


from site_utils.page_builders import (
    build_homepage, build_404_page, build_utility_pages,
    build_learn_pages, build_pinboard_page, build_about_page, build_raw_html_pages
)


def full_build(quiet=False):
    """Run a complete site build. Returns the build_id.

    This is the main entry point for both build.py and the desktop app.
    Uses content hash caching to skip re-rendering unchanged documents.

    Outputs:
        site/index.html         — The SPA shell (single HTML entry point)
        site/content/*.json     — Content fragments for each document/index
        site/search-index.json  — Search index loaded once at startup
        site/nav-state.json     — Nav rail state (categories, recent indicators)
        site/style.css          — Concatenated CSS
        site/app.js             — Concatenated JS
        site/_build.json        — Build ID for live-reload detection
    """
    build_id = str(int(time.time() * 1000))
    if not quiet:
        print("Hypervisor: scanning .hyperspace ...")

    logger.info("full_build started: build_id=%s", build_id)

    files = collect_files(HYPERSPACE_ROOT)
    if not quiet:
        print(f"  Found {len(files)} markdown documents")

    logger.info("collected %d markdown documents", len(files))

    # Initialize build cache — detects template/asset changes automatically
    cache = BuildCache()

    search_index = build_search_index(files)
    backlink_index = build_backlink_index(files)

    # Only wipe output dir if template changed (cache invalidated) or dir missing
    if cache.invalidated() or not OUTPUT_DIR.exists():
        prepare_output()
    else:
        # Ensure output dir exists but don't wipe it
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    copy_assets()

    # Write search index as a standalone JSON file
    search_json = json.dumps(search_index)
    (OUTPUT_DIR / "search-index.json").write_text(search_json, encoding="utf-8")

    # Compute nav categories and recent paths before generating any pages
    recent_paths = compute_recent_paths(files)
    recent_dirs = {}
    for rp in recent_paths:
        p = PurePosixPath(rp)
        if len(p.parts) > 1:
            recent_dirs[p.parts[0]] = recent_dirs.get(p.parts[0], 0) + 1
        if len(p.parts) > 2:
            key = f"{p.parts[0]}/{p.parts[1]}"
            recent_dirs[key] = recent_dirs.get(key, 0) + 1
    # Build category list with children for the nav rail
    top_dirs = set()
    for rel in files:
        p = PurePosixPath(str(rel).replace("\\", "/"))
        if len(p.parts) > 1:
            top_dirs.add(p.parts[0])
    nav_categories = []
    for d in sorted(top_dirs):
        if d == "reference":
            continue
        d_count = count_docs_under(files, d)
        # Collect immediate child directories
        child_dirs = set()
        for rel in files:
            p = PurePosixPath(str(rel).replace("\\", "/"))
            if len(p.parts) > 2 and p.parts[0] == d:
                child_dirs.add(p.parts[1])
        children = []
        for cd in sorted(child_dirs):
            cd_path = f"{d}/{cd}"
            cd_count = count_docs_under(files, cd_path)
            children.append((cd, cd_count))
        nav_categories.append((d, d_count, children))
    set_nav_categories(nav_categories, recent_dirs)

    # Write nav-state.json for the router to refresh nav without full rebuild
    nav_state = {
        "categories": [
            {"name": cat[0], "count": cat[1], "children": [{"name": c[0], "count": c[1]} for c in cat[2]]}
            for cat in nav_categories
        ],
        "recentDirs": recent_dirs,
    }
    (OUTPUT_DIR / "nav-state.json").write_text(
        json.dumps(nav_state, ensure_ascii=False), encoding="utf-8"
    )

    # Generate the SPA shell (single HTML entry point)
    shell_html = build_shell(build_id)
    (OUTPUT_DIR / "index.html").write_text(shell_html, encoding="utf-8")

    # Generate 404 fragment
    build_404_page(build_id)

    # Generate content fragments for documents
    rendered = build_doc_pages(files, backlink_index, build_id, cache=cache)

    # Generate index fragments
    all_dirs = build_indexes(files, build_id, recent_paths=recent_paths)

    # Generate special page fragments
    util_count = build_utility_pages(build_id)
    learn_count = build_learn_pages(build_id)
    build_pinboard_page(build_id)
    build_about_page(build_id)
    raw_html_count = build_raw_html_pages()
    build_homepage(files, all_dirs, build_id,
                   recent_paths=recent_paths, util_count=util_count)

    # Prune stale entries from cache and save for next build
    cache.prune(files)
    cache.save()

    page_count = len(files) + len(all_dirs) + 1 + util_count + learn_count + raw_html_count
    if not quiet:
        skipped = len(files) - rendered
        if skipped > 0:
            print(f"  Generated {page_count} fragments ({rendered} rendered, {skipped} cached)")
        else:
            print(f"  Generated {page_count} fragments ({len(files)} docs + {len(all_dirs)} indexes + 1 home)")
        print(f"  Output: {OUTPUT_DIR}")

    logger.info("full_build complete: %d fragments (%d rendered, %d cached)", page_count, rendered, len(files) - rendered)

    # Write _build.json so existing browser tabs can detect the new build
    build_json_data = json.dumps({"buildId": build_id})
    (OUTPUT_DIR / "_build.json").write_text(build_json_data, encoding="utf-8")

    return build_id


def build_single_file(changed_path):
    """Incremental rebuild: re-render one doc fragment and regenerate affected indexes.

    Args:
        changed_path: Path to the changed .md file, relative to HYPERSPACE_ROOT
                      (e.g. "work/to-do/my-item/story.md")

    Returns the build_id used for this rebuild.
    """
    from pathlib import Path, PurePosixPath

    logger.info("incremental build: %s", changed_path)

    build_id = str(int(time.time() * 1000))
    files = collect_files(HYPERSPACE_ROOT)
    search_index = build_search_index(files)
    backlink_index = build_backlink_index(files)

    # Ensure assets are current
    copy_assets()

    # Write search index as a standalone JSON file
    search_json = json.dumps(search_index)
    (OUTPUT_DIR / "search-index.json").write_text(search_json, encoding="utf-8")

    # Set up nav categories for this rebuild
    recent_paths = compute_recent_paths(files)
    recent_dirs = {}
    for rp in recent_paths:
        p = PurePosixPath(rp)
        if len(p.parts) > 1:
            recent_dirs[p.parts[0]] = recent_dirs.get(p.parts[0], 0) + 1
        if len(p.parts) > 2:
            key = f"{p.parts[0]}/{p.parts[1]}"
            recent_dirs[key] = recent_dirs.get(key, 0) + 1
    top_dirs = set()
    for rel in files:
        p = PurePosixPath(str(rel).replace("\\", "/"))
        if len(p.parts) > 1:
            top_dirs.add(p.parts[0])
    nav_categories = []
    for d in sorted(top_dirs):
        if d == "reference":
            continue
        d_count = count_docs_under(files, d)
        child_dirs = set()
        for rel in files:
            p = PurePosixPath(str(rel).replace("\\", "/"))
            if len(p.parts) > 2 and p.parts[0] == d:
                child_dirs.add(p.parts[1])
        children = []
        for cd in sorted(child_dirs):
            cd_path = f"{d}/{cd}"
            cd_count = count_docs_under(files, cd_path)
            children.append((cd, cd_count))
        nav_categories.append((d, d_count, children))
    set_nav_categories(nav_categories, recent_dirs)

    # Write updated nav-state.json
    nav_state = {
        "categories": [
            {"name": cat[0], "count": cat[1], "children": [{"name": c[0], "count": c[1]} for c in cat[2]]}
            for cat in nav_categories
        ],
        "recentDirs": recent_dirs,
    }
    (OUTPUT_DIR / "nav-state.json").write_text(
        json.dumps(nav_state, ensure_ascii=False), encoding="utf-8"
    )

    # Rebuild the changed doc fragment
    rel = PurePosixPath(changed_path)
    md_path = HYPERSPACE_ROOT / rel
    if md_path.exists():
        md_text = md_path.read_text(encoding="utf-8")
        title = get_title(md_text, nice_name(rel.name))
        content_html, toc_html = render_markdown(md_text, source_path=str(rel))
        hdir = html_dir_for(rel)

        rel_posix = str(rel).replace("\\", "/")
        doc_backlinks = backlink_index.get(rel_posix, [])
        backlinks_html = render_backlinks_html(doc_backlinks)

        fragment = build_fragment(
            content_html, title, rel_posix,
            toc_html=toc_html, backlinks_html=backlinks_html,
            page_type="doc", source_path=rel_posix,
        )

        fragment_path = OUTPUT_DIR / "content" / (str(PurePosixPath(hdir)) + ".json")
        write_fragment(fragment, fragment_path)

    # Rebuild ancestor directory index fragments
    parent = str(PurePosixPath(changed_path).parent).replace("\\", "/")
    ancestors = []
    while parent and parent != ".":
        ancestors.append(parent)
        parent = str(PurePosixPath(parent).parent).replace("\\", "/")

    for ancestor in ancestors:
        content_html, page_title = generate_dir_index_content(files, ancestor, recent_paths=recent_paths)
        fragment = build_fragment(
            content_html, page_title, ancestor,
            page_type="index", source_path=ancestor,
        )
        fragment_path = OUTPUT_DIR / "content" / (ancestor + ".json")
        write_fragment(fragment, fragment_path)

    # Rebuild pinboard fragment (search index may have changed)
    build_pinboard_page(build_id)
    build_about_page(build_id)

    # Rebuild homepage fragment (recently updated list may have changed)
    all_dirs = collect_all_dirs(files)
    util_count = len(list(UTILITIES_DIR.glob("*.html"))) if UTILITIES_DIR.exists() else 0
    build_homepage(files, all_dirs, build_id,
                   recent_paths=recent_paths, util_count=util_count)

    # Update _build.json
    build_json_data = json.dumps({"buildId": build_id})
    (OUTPUT_DIR / "_build.json").write_text(build_json_data, encoding="utf-8")

    return build_id


# ---------------------------------------------------------------------------
# CLI entry point — preserves original behavior
# ---------------------------------------------------------------------------

def main():
    build_id = full_build()
    print("  Build complete. Launch the desktop app to view.")


if __name__ == "__main__":
    main()
