# The Build Script

A walkthrough of `build.py` — the orchestrator that ties all the modules together.

---

## What `build.py` Does

`build.py` is the entry point. It doesn't do much heavy lifting itself — it coordinates the modules in `site_utils/` in the right order. Think of it as a recipe that calls specialized functions.

## Imports

```python
from site_utils.config import HYPERSPACE_ROOT, OUTPUT_DIR, ASSETS_DIR
from site_utils.file_utils import collect_files, html_dir_for, root_prefix, nice_name, get_title
from site_utils.markdown_processing import render_markdown
from site_utils.search import build_search_index
from site_utils.backlinks import build_backlink_index, render_backlinks_html
from site_utils.directory_index import collect_all_dirs, generate_home_content, generate_dir_index_content
from site_utils.page_generation import build_page, build_topbar, make_breadcrumbs, PAGE_TEMPLATE
```

Each import pulls in a specific capability:
- `config` — where things are on disk
- `file_utils` — finding and naming files
- `markdown_processing` — converting markdown to HTML
- `search` — building the search index
- `backlinks` — tracking cross-references
- `directory_index` — auto-generating category pages
- `page_generation` — assembling final HTML pages

## The `full_build()` Function

This is the main function. Here's what it does, step by step:

### Step 1: Generate a build ID

```python
build_id = str(int(time.time() * 1000))
```

A millisecond timestamp used to detect when the site has been rebuilt. Every page embeds this ID, and the live-reload JS polls for changes.

### Step 2: Collect files

```python
files = collect_files(HYPERSPACE_ROOT)
```

Walks `.hyperspace/` and returns every `.md` file as a relative path. This list drives everything else.

### Step 3: Build indexes

```python
search_json = json.dumps(build_search_index(files))
backlink_index = build_backlink_index(files)
```

- **Search index**: For each file, extracts title, path, tags, a text snippet, and dates. Serialized to JSON and embedded in every page.
- **Backlink index**: Scans each file for `[text](path.md)` links and builds a reverse map.

### Step 4: Prepare output

```python
prepare_output()  # Delete and recreate site/
copy_assets()     # Concatenate CSS/JS, copy to site/
```

`copy_assets()` is where the CSS and JS modules get concatenated:
- CSS: numbered files in `assets/css/` sorted, then `zz-*` files appended last → `site/style.css`
- JS: `assets/js/core/` → `assets/js/features/` → `assets/js/screensaver/` (with `zz-*` last in each group) → `site/app.js`

### Step 5: Build pages

```python
build_doc_pages(files, search_json, backlink_index, build_id)
```

For each markdown file:
1. Read the `.md` content
2. Render to HTML via `render_markdown()`
3. Wrap in the page template via `build_page()`
4. Write to `site/<path>/<stem>/index.html`

### Step 6: Build directory indexes

```python
all_dirs = build_indexes(files, search_json, build_id, recent_paths=recent_paths)
```

For every directory that contains documents, generates an index page with subcategory cards and a document listing.

### Step 7: Build homepage

```python
build_homepage(files, all_dirs, search_json, build_id, recent_paths=recent_paths)
```

The hub page: hero band, KPI strip, Workspace Pulse (active work + recent activity), Pinned mount point, and root documents.

### Step 8: Write build marker

```python
(OUTPUT_DIR / "_build.json").write_text(json.dumps({"buildId": build_id}))
```

This file is polled by the live-reload JS to detect new builds.

## The `build_single_file()` Function

Used by the desktop app's file watcher for incremental rebuilds. Instead of regenerating everything, it:

1. Rebuilds just the changed document's page
2. Rebuilds the parent directory's index (since the doc list may have changed)
3. Rebuilds the homepage (since "recently updated" may have changed)
4. Re-copies assets (in case CSS/JS was edited)

This keeps the desktop app responsive — edits appear in under a second.

## How Pages Get Their URLs

The path transformation is simple:

```
.hyperspace/context/cms-architecture.md
    → site/context/cms-architecture/index.html
    → URL: context/cms-architecture/index.html
```

The function `html_dir_for(rel)` handles this conversion. Every document gets its own directory with an `index.html` inside. This means links can use clean paths without file extensions.

## The `root_prefix()` Function

Since the site can run from `file://` (no web server), all asset paths must be relative. A page at `site/context/cms-architecture/index.html` needs to reference `../../style.css` to reach the root.

`root_prefix(hdir)` calculates the correct number of `../` segments based on how deep the page is in the directory tree.

## Reference Links

- [Python `shutil`](https://docs.python.org/3/library/shutil.html) — used for `rmtree` (delete directory) and `copy2` (copy files)
- [Python `json`](https://docs.python.org/3/library/json.html) — serializing the search index
- [Python `time`](https://docs.python.org/3/library/time.html) — generating build IDs
- [Python `glob` patterns](https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob) — how `*.css` and `*.js` file collection works

## Next

→ [File Discovery](../03-file-discovery/index.html) — how `collect_files` and path helpers work
