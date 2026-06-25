"""
In-memory index: build, refresh, remove, file watcher.
"""

import os
import re
import threading
from datetime import datetime
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT, SKIP_DIRS
from site_utils.file_utils import (
    collect_files, extract_dates, get_title,
    _extract_tags_from_text, _extract_status_from_text, _extract_type_from_text,
)
from site_utils.search import _extract_snippet

from .config import INDEX_FILE
from .backlinks import rebuild_backlinks, refresh_backlinks_for, remove_backlinks_for


# ---------------------------------------------------------------------------
# In-Memory Index
# ---------------------------------------------------------------------------

_index: list[dict] = []
_index_lock = threading.Lock()


def get_index_lock() -> threading.Lock:
    """Return the index lock for external callers that need atomic reads."""
    return _index_lock


# ---------------------------------------------------------------------------
# Index entry building
# ---------------------------------------------------------------------------

def _extract_description(md_text: str) -> str:
    """Extract the one-liner description between H1 and metadata."""
    lines = md_text.splitlines()
    found_title = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("# ") and not found_title:
            found_title = True
            continue
        if found_title:
            if stripped == "":
                continue
            if re.match(r'^-\s+[A-Za-z]', stripped) or stripped == "---":
                return ""
            return stripped
    return ""


def _extract_project(md_text: str) -> str | None:
    """Extract Project metadata from markdown text header."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r'Project\s*:\s*(.+)', stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_work_id(md_text: str) -> str | None:
    """Extract ID metadata (e.g., WI-23) from markdown text header."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r'ID\s*:\s*(WI-\d+)', stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _infer_doc_type(rel_path: str) -> str:
    """Infer document type from its relative path."""
    parts = rel_path.replace("\\", "/").split("/")
    if parts[0] == "work":
        return "work-item"
    elif parts[0] == "ideas":
        return "idea"
    elif parts[0] == "research" and len(parts) > 1 and parts[1] == "bugfixes":
        return "bugfix"
    elif parts[0] == "research":
        return "research"
    elif parts[0] == "context":
        return "context"
    elif parts[0] == "patterns":
        return "pattern"
    elif parts[0] == "analysis":
        return "analysis"
    elif parts[0] == "reference":
        return "reference"
    elif parts[0] == "templates":
        return "template"
    elif parts[0] == ".external":
        return "external"
    return "document"


def _build_index_entry(rel_path: Path) -> dict | None:
    """Build an index entry from a markdown file."""
    full_path = HYPERSPACE_ROOT / rel_path
    if not full_path.exists():
        return None
    try:
        md_text = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    rel_str = str(rel_path).replace("\\", "/")
    title = get_title(md_text, rel_path.stem.replace("-", " ").title())
    description = _extract_description(md_text)
    snippet = _extract_snippet(md_text, max_len=200)
    tags = _extract_tags_from_text(md_text)
    dates = extract_dates(md_text)
    status = _extract_status_from_text(md_text)
    project = _extract_project(md_text)
    work_id = _extract_work_id(md_text)
    doc_type_meta = _extract_type_from_text(md_text)
    doc_type = _infer_doc_type(rel_str)

    parts = rel_str.split("/")
    directory = "/".join(parts[:-1]) if len(parts) > 1 else ""

    return {
        "path": rel_str,
        "title": title,
        "description": description,
        "snippet": snippet,
        "type": doc_type,
        "tags": tags,
        "created": dates.get("created"),
        "updated": dates.get("updated"),
        "status": status,
        "project": project,
        "work_id": work_id,
        "doc_type": doc_type_meta,
        "directory": directory,
    }


def rebuild_index():
    """Full rebuild of the in-memory index and backlink graph from disk."""
    global _index
    files = collect_files(HYPERSPACE_ROOT)
    entries = []
    for rel in files:
        entry = _build_index_entry(rel)
        if entry:
            entries.append(entry)
    with _index_lock:
        _index = entries
    # Build backlink graph after index (uses same file set)
    rebuild_backlinks()


def refresh_single(rel_path: str):
    """Refresh a single entry in the index (after create/update)."""
    global _index
    entry = _build_index_entry(Path(rel_path))
    with _index_lock:
        _index = [e for e in _index if e["path"] != rel_path]
        if entry:
            _index.append(entry)
    # Update backlink graph for this file
    refresh_backlinks_for(rel_path)


def remove_from_index(rel_path: str):
    """Remove a path from the in-memory index."""
    global _index
    with _index_lock:
        _index = [e for e in _index if e["path"] != rel_path]
    # Remove from backlink graph
    remove_backlinks_for(rel_path)


# ---------------------------------------------------------------------------
# File Watcher (watchdog)
# ---------------------------------------------------------------------------

_watcher_started = False


def start_watcher():
    """Start a watchdog observer on the hyperspace root."""
    global _watcher_started
    if _watcher_started:
        return
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler

        class _HyperspaceHandler(FileSystemEventHandler):
            def _rel(self, path):
                try:
                    return str(Path(path).relative_to(HYPERSPACE_ROOT)).replace("\\", "/")
                except ValueError:
                    return None

            def _should_skip(self, rel):
                if not rel or not rel.endswith(".md"):
                    return True
                parts = rel.split("/")
                return any(p in SKIP_DIRS for p in parts)

            def _safe_refresh(self, rel):
                """Refresh with a small delay to avoid reading partially-written files."""
                import time
                time.sleep(0.1)  # Let writes flush on Windows
                refresh_single(rel)

            def on_created(self, event):
                if event.is_directory:
                    return
                rel = self._rel(event.src_path)
                if not self._should_skip(rel):
                    self._safe_refresh(rel)

            def on_modified(self, event):
                if event.is_directory:
                    return
                rel = self._rel(event.src_path)
                if not self._should_skip(rel):
                    self._safe_refresh(rel)

            def on_deleted(self, event):
                if event.is_directory:
                    return
                rel = self._rel(event.src_path)
                if not self._should_skip(rel):
                    remove_from_index(rel)

            def on_moved(self, event):
                if event.is_directory:
                    return
                old_rel = self._rel(event.src_path)
                new_rel = self._rel(event.dest_path)
                if old_rel and not self._should_skip(old_rel):
                    remove_from_index(old_rel)
                if new_rel and not self._should_skip(new_rel):
                    self._safe_refresh(new_rel)

        observer = Observer()
        observer.schedule(_HyperspaceHandler(), str(HYPERSPACE_ROOT), recursive=True)
        observer.daemon = True
        observer.start()
        _watcher_started = True
    except ImportError:
        pass
