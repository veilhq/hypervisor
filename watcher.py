"""
File watcher for the Hypervisor desktop app.

Watches .hyperspace/**/*.md for changes and triggers incremental rebuilds.
Changes are queued and coalesced: the build runs once after a quiet period
(or a maximum hold), or immediately on flush(), covering every queued file.

Content hashing is used to suppress phantom events - on Windows, reading a
file during a build can update its access time, which watchdog may report as
a modification. By comparing MD5 hashes of file content, we only trigger
rebuilds when the file's actual bytes have changed.
"""

import hashlib
import sys
import time
import threading
from pathlib import Path, PurePosixPath

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from site_utils.config import HYPERSPACE_ROOT, OUTPUT_DIR

# Structured logging (shared ecosystem logger)
sys.path.insert(0, str(Path(__file__).parent.parent.resolve() / ".hyperkit" / "python"))
from hyper_logging import setup_logger  # noqa: E402

logger = setup_logger("hypervisor")


class MarkdownHandler(FileSystemEventHandler):
    """Watches for .md file changes and triggers rebuilds with debouncing."""

    # Directories to ignore (relative to HYPERSPACE_ROOT)
    IGNORE_DIRS = {".hypervisor", "__pycache__", ".scratch"}

    def __init__(self, rebuild_callback, hold_seconds=3.0, max_hold_seconds=15.0,
                 queue_callback=None):
        super().__init__()
        self.rebuild_callback = rebuild_callback
        self.hold_seconds = hold_seconds
        self.max_hold_seconds = max_hold_seconds
        self.queue_callback = queue_callback
        self._timer = None
        self._lock = threading.Lock()
        # Queued changes: incremental paths plus a flag for "needs a full build".
        self._pending_paths = set()
        self._pending_full = False
        self._first_event_at = None
        # Paths written programmatically - events for these are ignored
        # until their grace period expires. Maps resolved path → expiry timestamp.
        self._ignored_paths = {}
        self._ignored_lock = threading.Lock()
        # Content hash cache - maps resolved path → MD5 hex digest.
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
            # Grace period expired - clean up
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
            # Can't read the file - treat as changed to be safe
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
        # New file - store its hash and proceed
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
        """Handle file/directory moves - trigger a full rebuild.

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
        # Drop the old path's cached hash so renames don't leave stale keys
        # accumulating in _content_hashes for the life of the process.
        if src_md:
            self._remove_hash(event.src_path)
        # File moved - full rebuild to handle old path removal + new path generation
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
        """Queue a change (None = full rebuild) and restart the hold timer.

        The timer waits for a quiet period of hold_seconds, but never longer
        than max_hold_seconds after the first queued change.
        """
        with self._lock:
            now = time.monotonic()
            if self._first_event_at is None:
                self._first_event_at = now
            if rel_path is None:
                self._pending_full = True
            else:
                self._pending_paths.add(rel_path)
            if self._timer is not None:
                self._timer.cancel()
            remaining = self.max_hold_seconds - (now - self._first_event_at)
            self._timer = threading.Timer(max(0.0, min(self.hold_seconds, remaining)), self._fire)
            self._timer.daemon = True
            self._timer.start()
            count = self._count_locked()
            full = self._pending_full
        self._notify_queue(count, full)

    def _count_locked(self):
        return len(self._pending_paths) + (1 if self._pending_full else 0)

    def _notify_queue(self, count, full):
        if self.queue_callback is None:
            return
        try:
            self.queue_callback(count, full)
        except Exception as e:  # a UI hiccup must never block the queue
            logger.debug("watcher: queue callback failed: %s", e)

    def pending_count(self):
        """Number of queued changes waiting for the next build."""
        with self._lock:
            return self._count_locked()

    def flush(self):
        """Run the queued rebuild now. Returns the number of changes flushed."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
        return self._fire()

    def _fire(self):
        """Hand the queued changes to the rebuild callback as one batch."""
        with self._lock:
            paths = sorted(self._pending_paths)
            full = self._pending_full
            self._pending_paths = set()
            self._pending_full = False
            self._first_event_at = None
            self._timer = None
        if not paths and not full:
            return 0
        if full:
            logger.info("watcher: %d queued change(s), full rebuild", len(paths))
        else:
            logger.info("watcher: rebuilding %d queued file(s)", len(paths))
        self._notify_queue(0, False)
        self.rebuild_callback(paths, full)
        return len(paths) + (1 if full else 0)


class FileWatcher:
    """Manages the watchdog observer for .hyperspace markdown files."""

    def __init__(self, rebuild_callback, hold_seconds=3.0, max_hold_seconds=15.0,
                 queue_callback=None):
        self.handler = MarkdownHandler(
            rebuild_callback, hold_seconds, max_hold_seconds, queue_callback)
        self.observer = Observer()
        self.observer.daemon = True

    def flush(self):
        """Rebuild queued changes immediately. Returns how many were flushed."""
        return self.handler.flush()

    def pending_count(self):
        return self.handler.pending_count()

    def start(self):
        """Start watching .hyperspace/ for markdown changes."""
        watch_path = str(HYPERSPACE_ROOT.resolve())
        self.observer.schedule(self.handler, watch_path, recursive=True)
        self.observer.start()
        logger.info("watcher started: %s", watch_path)
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
