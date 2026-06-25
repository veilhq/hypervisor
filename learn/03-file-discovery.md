# File Discovery

How Hypervisor finds, names, and organizes your markdown files.

---

## The Scanner: `collect_files()`

This is the starting point of every build. It walks the entire `.hyperspace/` directory tree and returns a sorted list of every `.md` file it finds.

```python
def collect_files(root: Path):
    files = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(p in SKIP_DIRS for p in rel.parts):
            continue
        if path.name in SKIP_FILES:
            continue
        files.append(rel)
    return files
```

### How it works

1. **`root.rglob("*.md")`** — recursively finds every file ending in `.md` under the root directory. `rglob` is like `glob` but searches all subdirectories.

2. **`path.relative_to(root)`** — converts the absolute path to a relative one. If root is `/home/user/.hyperspace/` and path is `/home/user/.hyperspace/context/cms.md`, the result is `context/cms.md`.

3. **Skip filters** — certain directories (`__pycache__`, `site`, `learn`) and files (`.gitkeep`) are excluded.

4. **`sorted()`** — ensures consistent ordering across builds regardless of filesystem order.

### Why relative paths?

Everything downstream works with relative paths. The relative path determines:
- The output URL (`context/cms.md` → `site/context/cms/index.html`)
- The breadcrumb trail (`~ / context / cms`)
- Which directory index the file appears in

## Path Helpers

### `html_dir_for(rel)` — Where does this file's HTML go?

```python
def html_dir_for(rel):
    # context/cms-architecture.md → context/cms-architecture
    return rel.parent / rel.stem
```

Strips the `.md` extension and uses the stem as a directory name. The actual HTML file is always `index.html` inside that directory.

### `root_prefix(hdir)` — How many `../` to reach the site root?

```python
def root_prefix(hdir):
    depth = len(hdir.parts)
    return "../" * (depth) if depth else "./"
```

A page at `context/cms-architecture/index.html` is 2 levels deep, so it needs `../../` to reference `style.css` at the root. This is critical for `file://` protocol where absolute paths don't work.

### `nice_name(filename)` — Human-readable name from a filename

```python
def nice_name(name):
    stem = Path(name).stem
    return stem.replace("-", " ").replace("_", " ").title()
```

Converts `cms-architecture.md` → `"Cms Architecture"`. Used as a fallback title when the document doesn't have an H1 heading.

### `get_title(md_text, fallback)` — Extract the document title

```python
def get_title(md_text, fallback):
    for line in md_text.split("\n"):
        if line.startswith("# "):
            return line[2:].strip()
    return fallback
```

Looks for the first `# Heading` in the markdown. If none found, falls back to `nice_name()`.

## Date Extraction

Documents are sorted by date in directory listings. `extract_dates()` scans the first 30 lines looking for metadata patterns:

```python
# These patterns are recognized:
# Created: 2026-02-17
# - Created: 2026-02-17T14:30
# Updated: 2026-02-18
# Date: 2026-02-26
```

The function returns a dict with `created` and `updated` keys. `sort_date()` then picks the best date for sorting (prefers `updated` over `created`).

### Why only 30 lines?

Metadata always appears at the top of a document (right after the H1 heading). Scanning the entire file would be wasteful — especially for large documents with dates mentioned in the body text that aren't metadata.

## Directory Structure → Site Structure

The mapping is direct:

| Filesystem | Generated Site | URL |
|---|---|---|
| `context/cms.md` | `site/context/cms/index.html` | `context/cms/index.html` |
| `work/to-do/cms-bulk-upload.md` | `site/work/to-do/cms-bulk-upload/index.html` | `work/to-do/cms-bulk-upload/index.html` |
| `patterns/django/soft-delete.md` | `site/patterns/django/soft-delete/index.html` | `patterns/django/soft-delete/index.html` |

Every directory that contains at least one document also gets an auto-generated index page at `<dir>/index.html`.

## The `pathlib` Library

All path manipulation uses Python's built-in `pathlib`. Key concepts:

- **`Path`** — an object representing a filesystem path (not just a string)
- **`.parent`** — the directory containing this path
- **`.stem`** — filename without extension (`cms-architecture.md` → `cms-architecture`)
- **`.name`** — full filename with extension
- **`.parts`** — tuple of path components (`('context', 'cms-architecture')`)
- **`.relative_to(base)`** — strip a prefix to get a relative path
- **`.rglob(pattern)`** — recursive glob search

### Why `pathlib` instead of string manipulation?

```python
# String manipulation (fragile):
path = "context/cms-architecture.md"
dir_name = path.rsplit("/", 1)[0]  # breaks on Windows backslashes

# pathlib (cross-platform):
path = Path("context/cms-architecture.md")
dir_name = path.parent  # works on any OS
```

`pathlib` handles OS differences (forward vs backslash), provides clean APIs for common operations, and prevents bugs from manual string splitting.

## Reference Links

- [pathlib documentation](https://docs.python.org/3/library/pathlib.html) — the full API reference
- [pathlib tutorial (Real Python)](https://realpython.com/python-pathlib/) — beginner-friendly walkthrough
- [glob patterns](https://docs.python.org/3/library/pathlib.html#pathlib.Path.glob) — how `*.md` and `**/*.md` work

## Next

→ [Markdown Rendering](../04-markdown-rendering/index.html) — how `.md` content becomes HTML
