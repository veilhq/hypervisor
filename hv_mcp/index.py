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
    collect_files, extract_dates, get_title, read_md,
    _extract_tags_from_text, _extract_status_from_text, _extract_type_from_text,
)
from site_utils.search import _extract_snippet

from .config import INDEX_FILE
from .backlinks import (
    _extract_links, refresh_backlinks_for, remove_backlinks_for, set_link_graph,
)


# ---------------------------------------------------------------------------
# In-Memory Index
# ---------------------------------------------------------------------------

class _PathIndex:
    """Path-keyed entry store that iterates like a list of entries.

    Lookup by path or work id, replace and remove are O(1); iteration yields
    a snapshot of the entries so existing readers (list(), for, len) keep working.
    """

    def __init__(self, entries=()):
        self._by_path: dict[str, dict] = {}
        self._by_work_id: dict[str, dict[str, None]] = {}
        for entry in entries:
            self.put(entry)

    def __iter__(self):
        return iter(list(self._by_path.values()))

    def __len__(self):
        return len(self._by_path)

    def __bool__(self):
        return bool(self._by_path)

    def get(self, path: str):
        return self._by_path.get(path)

    def get_by_work_id(self, work_id: str | None):
        """Return the first entry (in iteration order) carrying work_id, case-insensitive."""
        if not work_id:
            return None
        paths = self._by_work_id.get(work_id.upper())
        if not paths:
            return None
        return self._by_path.get(next(iter(paths)))

    def put(self, entry: dict):
        # Re-insert so a refreshed entry moves to the end, as with append.
        self.discard(entry["path"])
        self._by_path[entry["path"]] = entry
        work_id = entry.get("work_id")
        if work_id:
            self._by_work_id.setdefault(work_id.upper(), {})[entry["path"]] = None

    def discard(self, path: str):
        old = self._by_path.pop(path, None)
        work_id = old.get("work_id") if old else None
        if work_id:
            paths = self._by_work_id.get(work_id.upper())
            if paths is not None:
                paths.pop(path, None)
                if not paths:
                    del self._by_work_id[work_id.upper()]


_index = _PathIndex()
_index_lock = threading.Lock()
_rebuild_lock = threading.Lock()
# While a rebuild is reading disk, refreshes and removals record their result
# here (path -> md_text, or None for removed) so the swap can replay them.
_rebuild_touched: dict[str, str | None] | None = None


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
    elif parts[0] == "research":
        return "research"
    elif parts[0] == "context":
        return "context"
    elif parts[0] == "patterns":
        return "pattern"
    elif parts[0] == "analysis":
        return "analysis"
    elif parts[0] == "notes":
        return "note"
    elif parts[0] == "reference":
        return "reference"
    elif parts[0] == "templates":
        return "template"
    elif parts[0] == ".external":
        return "external"
    return "document"


def _read_doc(rel_path: Path) -> str | None:
    """Read a document under the hyperspace root, or None if unreadable."""
    full_path = HYPERSPACE_ROOT / rel_path
    if not full_path.exists():
        return None
    try:
        return read_md(full_path, warn=full_path.suffix.lower() == ".md")
    except (OSError, UnicodeDecodeError):
        return None


def _build_index_entry(rel_path: Path, md_text: str | None = None) -> dict | None:
    """Build an index entry from a markdown file (or from md_text already read)."""
    if md_text is None:
        md_text = _read_doc(rel_path)
        if md_text is None:
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
    global _index, _rebuild_touched
    with _rebuild_lock:
        with _index_lock:
            _rebuild_touched = {}
        try:
            files = collect_files(HYPERSPACE_ROOT)
            entries = []
            outlinks: dict[str, set[str]] = {}
            for rel in files:
                rel_str = str(rel).replace("\\", "/")
                md_text = _read_doc(rel)
                if md_text is None:
                    outlinks[rel_str] = set()
                    continue
                entries.append(_build_index_entry(rel, md_text))
                outlinks[rel_str] = _extract_links(md_text, rel_str)
            with _index_lock:
                touched, _rebuild_touched = _rebuild_touched, None
                new_index = _PathIndex(entries)
                # Replay refreshes and removals that landed during the disk walk.
                for rel_str in touched:
                    live = _index.get(rel_str)
                    new_index.discard(rel_str)
                    if live is not None:
                        new_index.put(live)
                _index = new_index
                set_link_graph(outlinks)
                for rel_str, md_text in touched.items():
                    if md_text is None:
                        remove_backlinks_for(rel_str)
                    else:
                        refresh_backlinks_for(rel_str, md_text)
        finally:
            with _index_lock:
                _rebuild_touched = None


def refresh_single(rel_path: str):
    """Refresh a single entry in the index (after create/update)."""
    md_text = _read_doc(Path(rel_path))
    entry = _build_index_entry(Path(rel_path), md_text) if md_text is not None else None
    with _index_lock:
        _index.discard(rel_path)
        if entry:
            _index.put(entry)
        if _rebuild_touched is not None:
            _rebuild_touched[rel_path] = md_text if md_text is not None else ""
    # Update backlink graph for this file from the same read
    refresh_backlinks_for(rel_path, md_text if md_text is not None else "")


def remove_from_index(rel_path: str):
    """Remove a path from the in-memory index."""
    with _index_lock:
        _index.discard(rel_path)
        if _rebuild_touched is not None:
            _rebuild_touched[rel_path] = None
    # Remove from backlink graph
    remove_backlinks_for(rel_path)


# ---------------------------------------------------------------------------
# File Watcher (watchdog)
# ---------------------------------------------------------------------------

_watcher_started = False
_DEBOUNCE_SECONDS = 0.1


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

            def __init__(self):
                super().__init__()
                self._timers: dict[str, threading.Timer] = {}
                self._timers_lock = threading.Lock()
                # Serializes refresh against delete/move so a refresh already
                # in flight cannot re-add a path that was just removed.
                self._apply_lock = threading.Lock()

            def _safe_refresh(self, rel):
                """Debounce per path: a burst of events refreshes the path once."""
                with self._timers_lock:
                    pending = self._timers.pop(rel, None)
                    if pending:
                        pending.cancel()
                    timer = threading.Timer(_DEBOUNCE_SECONDS, self._run_refresh, (rel,))
                    timer.daemon = True
                    self._timers[rel] = timer
                    timer.start()

            def _cancel_pending(self, rel):
                with self._timers_lock:
                    pending = self._timers.pop(rel, None)
                if pending:
                    pending.cancel()

            def _run_refresh(self, rel):
                with self._apply_lock:
                    with self._timers_lock:
                        if self._timers.pop(rel, None) is None:
                            return
                    refresh_single(rel)
                    # RAG incremental reindex for this file (no-op if RAG not yet initialized)
                    from .rag import on_file_changed
                    on_file_changed(rel)

            def _apply_removal(self, rel):
                self._cancel_pending(rel)
                with self._apply_lock:
                    remove_from_index(rel)
                    from .rag import on_file_deleted
                    on_file_deleted(rel)

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
                    self._apply_removal(rel)

            def on_moved(self, event):
                if event.is_directory:
                    return
                old_rel = self._rel(event.src_path)
                new_rel = self._rel(event.dest_path)
                if old_rel and not self._should_skip(old_rel):
                    self._apply_removal(old_rel)
                if new_rel and not self._should_skip(new_rel):
                    self._safe_refresh(new_rel)

        observer = Observer()
        observer.schedule(_HyperspaceHandler(), str(HYPERSPACE_ROOT), recursive=True)
        observer.daemon = True
        observer.start()
        _watcher_started = True
    except ImportError:
        pass
