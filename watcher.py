"""
File watcher for the Hypervisor desktop app.

Watches .hyperspace/**/*.md for changes and triggers incremental rebuilds.
Uses watchdog with debouncing to handle rapid successive saves.

Content hashing is used to suppress phantom events — on Windows, reading a
file during a build can update its access time, which watchdog may report as
a modification. By comparing MD5 hashes of file content, we only trigger
rebuilds when the file's actual bytes have changed.
"""

import hashlib
import time
import threading
from pathlib import Path, PurePosixPath

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from site_utils.config import HYPERSPACE_ROOT, OUTPUT_DIR


class MarkdownHandler(FileSystemEventHandler):
    """Watches for .md file changes and triggers rebuilds with debouncing."""

    # Directories to ignore (relative to HYPERSPACE_ROOT)
    IGNORE_DIRS = {".hypervisor", "__pycache__", ".scratch"}

    def __init__(self, rebuild_callback, debounce_seconds=0.3):
        super().__init__()
        self.rebuild_callback = rebuild_callback
        self.debounce_seconds = debounce_seconds
        self._timer = None
        self._lock = threading.Lock()
        self._pending_path = None
        # Paths written programmatically — events for these are ignored
        # until their grace period expires. Maps resolved path → expiry timestamp.
        self._ignored_paths = {}
        self._ignored_lock = threading.Lock()
        # Content hash cache — maps resolved path → MD5 hex digest.
        # Used to detect phantom events where the OS reports a modification
        # but the file content hasn't actually changed.
        self._content_hashes = {}
        self._hash_lock = threading.Lock()

    def ignore_path(self, abs_path, grace_seconds=2.0):
        """Register a path to ignore events for during the grace period.

        Call this before writing a file programmatically so the watcher
        doesn't treat the write as an external change.
        """
        resolved = str(Path(abs_path).resolve())
        with self._ignored_lock:
            self._ignored_paths[resolved] = time.time() + grace_seconds

    def _is_ignored(self, abs_path):
        """Check if events for this path should be suppressed."""
        resolved = str(Path(abs_path).resolve())
        with self._ignored_lock:
            expiry = self._ignored_paths.get(resolved)
            if expiry is None:
                return False
            if time.time() < expiry:
                return True
            # Grace period expired — clean up
            del self._ignored_paths[resolved]
            return False

    def _hash_file(self, abs_path):
        """Compute MD5 hash of a file's content. Returns None if unreadable."""
        try:
            data = Path(abs_path).read_bytes()
            return hashlib.md5(data).hexdigest()
        except (OSError, IOError):
            return None

    def _has_content_changed(self, abs_path):
        """Check if the file's content has actually changed since last seen.

        Returns True if the content is new or different, False if identical.
        Also updates the stored hash when content has changed.
        """
        resolved = str(Path(abs_path).resolve())
        current_hash = self._hash_file(abs_path)
        if current_hash is None:
            # Can't read the file — treat as changed to be safe
            return True
        with self._hash_lock:
            previous_hash = self._content_hashes.get(resolved)
            if previous_hash == current_hash:
                return False
            self._content_hashes[resolved] = current_hash
            return True

    def _remove_hash(self, abs_path):
        """Remove a file's cached hash (e.g., on deletion)."""
        resolved = str(Path(abs_path).resolve())
        with self._hash_lock:
            self._content_hashes.pop(resolved, None)

    def _should_ignore(self, path):
        """Check if the path is inside an ignored directory or not a watched file type."""
        if not (path.endswith(".md") or path.endswith(".html")):
            return True
        try:
            rel = Path(path).resolve().relative_to(HYPERSPACE_ROOT.resolve())
            parts = rel.parts
            return any(part in self.IGNORE_DIRS for part in parts)
        except ValueError:
            return True

    def _get_relative_path(self, abs_path):
        """Convert an absolute path to a path relative to HYPERSPACE_ROOT."""
        try:
            rel = Path(abs_path).resolve().relative_to(HYPERSPACE_ROOT.resolve())
            return str(PurePosixPath(rel))
        except ValueError:
            return None

    def on_modified(self, event):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if self._is_ignored(event.src_path):
            return
        if not self._has_content_changed(event.src_path):
            return
        self._handle(event.src_path)

    def on_created(self, event):
        if event.is_directory:
            return
        if self._should_ignore(event.src_path):
            return
        if self._is_ignored(event.src_path):
            return
        # New file — store its hash and proceed
        self._has_content_changed(event.src_path)
        self._handle(event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            return
        if self._is_ignored(event.src_path):
            return
        if not (event.src_path.endswith(".md") or event.src_path.endswith(".html")):
            return
        if self._should_ignore(event.src_path):
            return
        # Remove stale hash entry
        self._remove_hash(event.src_path)
        # For deletions, trigger a full rebuild since the file is gone
        self._debounce(None)

    def on_moved(self, event):
        """Handle file/directory moves — trigger a full rebuild.

        watchdog fires MoveEvents (not create+delete pairs) for renames
        and moves. A full rebuild is needed because the old path's page
        must be removed and the new path's page must be generated.
        """
        if event.is_directory:
            # Directory move (e.g., work item folder moved to-do → done).
            # Trigger full rebuild so all child pages get regenerated.
            self._debounce(None)
            return
        if self._is_ignored(event.src_path):
            return
        src_md = event.src_path.endswith(".md")
        dest_md = event.dest_path.endswith(".md")
        if not src_md and not dest_md:
            return
        # File moved — full rebuild to handle old path removal + new path generation
        self._debounce(None)

    def _handle(self, src_path):
        """Handle a file change event with debouncing."""
        if self._should_ignore(src_path):
            return
        # HTML files trigger a full rebuild (no incremental path)
        if src_path.endswith(".html"):
            self._debounce(None)
            return
        rel_path = self._get_relative_path(src_path)
        self._debounce(rel_path)

    def _debounce(self, rel_path):
        """Debounce rapid events — only fire the callback after the quiet period."""
        with self._lock:
            self._pending_path = rel_path
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce_seconds, self._fire)
            self._timer.start()

    def _fire(self):
        """Execute the rebuild callback after the debounce period."""
        with self._lock:
            path = self._pending_path
            self._pending_path = None
            self._timer = None
        self.rebuild_callback(path)


class FileWatcher:
    """Manages the watchdog observer for .hyperspace markdown files."""

    def __init__(self, rebuild_callback, debounce_seconds=0.3):
        self.handler = MarkdownHandler(rebuild_callback, debounce_seconds)
        self.observer = Observer()
        self.observer.daemon = True

    def start(self):
        """Start watching .hyperspace/ for markdown changes."""
        watch_path = str(HYPERSPACE_ROOT.resolve())
        self.observer.schedule(self.handler, watch_path, recursive=True)
        self.observer.start()
        print(f"  Watching: {watch_path}")

    def stop(self):
        """Stop the file watcher."""
        self.observer.stop()
        self.observer.join(timeout=2)

    def ignore_path(self, abs_path, grace_seconds=2.0):
        """Register a file path to ignore watcher events for.

        Use this before programmatic writes so the watcher doesn't
        treat them as external edits. The ignore expires automatically
        after grace_seconds.
        """
        self.handler.ignore_path(abs_path, grace_seconds)
