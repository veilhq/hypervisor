"""
Build cache — tracks content hashes to skip re-rendering unchanged documents.

Stores MD5 hashes of source .md files and a global "template hash" derived from
the page template + CSS + JS assets. If a doc's content hash matches the cache
AND the template hash hasn't changed, the rendered HTML is still valid and can
be skipped during a full build.
"""

import hashlib
import json
from pathlib import Path

from .config import OUTPUT_DIR, ASSETS_DIR


CACHE_PATH = OUTPUT_DIR.parent / ".build_cache.json"
CSS_DIR = ASSETS_DIR / "css"
JS_DIR = ASSETS_DIR / "js"
SITE_UTILS_DIR = Path(__file__).resolve().parent


class BuildCache:
    """Manages content hashes for incremental full builds."""

    def __init__(self):
        self._cache = {}
        self._template_hash = ""
        self._load()
        self._current_template_hash = self._compute_template_hash()
        # If template/assets changed, invalidate entire cache
        if self._current_template_hash != self._template_hash:
            self._cache = {}
            self._template_hash = self._current_template_hash

    def _load(self):
        """Load cache from disk."""
        if CACHE_PATH.exists():
            try:
                data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
                self._cache = data.get("files", {})
                self._template_hash = data.get("template_hash", "")
            except (json.JSONDecodeError, OSError):
                self._cache = {}
                self._template_hash = ""

    def save(self):
        """Persist cache to disk."""
        data = {
            "template_hash": self._current_template_hash,
            "files": self._cache,
        }
        CACHE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_unchanged(self, rel_path, md_text):
        """Check if a document's content matches the cached hash.

        Returns True if the doc can be skipped (content unchanged and output exists).
        """
        rel_key = str(rel_path).replace("\\", "/")
        current_hash = hashlib.md5(md_text.encode("utf-8")).hexdigest()

        cached_hash = self._cache.get(rel_key)
        if cached_hash != current_hash:
            return False

        # Verify the output file still exists on disk
        from .file_utils import html_dir_for
        out_file = OUTPUT_DIR / html_dir_for(rel_path) / "index.html"
        return out_file.exists()

    def update(self, rel_path, md_text):
        """Store the current hash for a document."""
        rel_key = str(rel_path).replace("\\", "/")
        self._cache[rel_key] = hashlib.md5(md_text.encode("utf-8")).hexdigest()

    def invalidated(self):
        """Returns True if the template/assets changed (full cache was cleared)."""
        return self._template_hash != self._current_template_hash

    def prune(self, current_files):
        """Remove cache entries for files that no longer exist on disk.

        Args:
            current_files: iterable of relative paths (PurePosixPath or Path)
                           representing the current set of source .md files.
        """
        current_keys = {str(rel).replace("\\", "/") for rel in current_files}
        stale_keys = [k for k in self._cache if k not in current_keys]
        for k in stale_keys:
            del self._cache[k]

    @property
    def stats(self):
        """Return cache hit/miss stats after a build."""
        return {"cached_files": len(self._cache)}

    def _compute_template_hash(self):
        """Hash all CSS + JS assets and Python build modules to detect changes."""
        hasher = hashlib.md5()

        # Hash CSS modules
        if CSS_DIR.exists():
            for css_file in sorted(CSS_DIR.glob("*.css")):
                hasher.update(css_file.read_bytes())

        # Hash JS modules
        if JS_DIR.exists():
            for js_file in sorted(JS_DIR.glob("*.js")):
                hasher.update(js_file.read_bytes())

        # Hash Python build modules (processing logic changes should invalidate cache)
        if SITE_UTILS_DIR.exists():
            for py_file in sorted(SITE_UTILS_DIR.glob("*.py")):
                hasher.update(py_file.read_bytes())

        return hasher.hexdigest()
