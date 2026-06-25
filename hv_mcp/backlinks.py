"""
Backlink graph — eagerly built at startup, incrementally updated via watcher.

Maps each document path to the set of other documents that link to it.
Used by context_for_work_item to instantly retrieve all documents referencing a target.
"""

import re
import threading
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import collect_files


# ---------------------------------------------------------------------------
# Backlink Graph
# ---------------------------------------------------------------------------

# _backlinks[target_path] = {source_path, source_path, ...}
# "Which docs link TO this path?"
_backlinks: dict[str, set[str]] = {}

# _outlinks[source_path] = {target_path, target_path, ...}
# "Which docs does this path link TO?" (needed for incremental updates)
_outlinks: dict[str, set[str]] = {}

_backlinks_lock = threading.Lock()

# Regex to match markdown links: [text](path.md) or [text](../relative/path.md)
_LINK_PATTERN = re.compile(r'\[([^\]]*)\]\(([^)]+\.md(?:#[^)]*)?)\)')


def get_backlinks_lock() -> threading.Lock:
    """Return the backlinks lock for thread-safe reads."""
    return _backlinks_lock


def get_backlinks_for(target_path: str) -> set[str]:
    """Get all documents that link TO the given path.

    Args:
        target_path: Relative path (e.g., 'work/to-do/my-item.md')

    Returns:
        Set of relative paths that contain links to target_path.
    """
    with _backlinks_lock:
        return set(_backlinks.get(target_path, set()))


def get_outlinks_for(source_path: str) -> set[str]:
    """Get all documents that the given path links TO.

    Args:
        source_path: Relative path (e.g., 'work/to-do/my-item.md')

    Returns:
        Set of relative paths that source_path links to.
    """
    with _backlinks_lock:
        return set(_outlinks.get(source_path, set()))


def _extract_links(md_text: str, source_rel: str) -> set[str]:
    """Extract all resolved relative .md link targets from markdown text.

    Resolves relative paths (../foo/bar.md) against the source file's directory.
    Returns normalized forward-slash paths relative to HYPERSPACE_ROOT.
    """
    source_dir = str(Path(source_rel).parent).replace("\\", "/")
    if source_dir == ".":
        source_dir = ""

    targets = set()
    # Skip links inside fenced code blocks
    in_code = False
    for line in md_text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue

        for match in _LINK_PATTERN.finditer(line):
            href = match.group(2)

            # Strip fragment (#section)
            if "#" in href:
                href = href.split("#")[0]
            if not href:
                continue

            # Skip external links
            if href.startswith(("http://", "https://", "mailto:")):
                continue

            # Resolve relative path
            if source_dir:
                resolved = str((Path(source_dir) / href).as_posix())
            else:
                resolved = href

            # Normalize: collapse ../
            try:
                resolved = str(Path(resolved).as_posix())
                # Remove leading ./ if present
                if resolved.startswith("./"):
                    resolved = resolved[2:]
                # Use pathlib to resolve .. segments
                parts = resolved.split("/")
                normalized = []
                for part in parts:
                    if part == "..":
                        if normalized:
                            normalized.pop()
                    elif part != ".":
                        normalized.append(part)
                resolved = "/".join(normalized)
            except (ValueError, OSError):
                continue

            if resolved.endswith(".md"):
                targets.add(resolved)

    return targets


def _index_single_file(rel_path: str) -> set[str]:
    """Parse a single file and return its outgoing link targets."""
    full_path = HYPERSPACE_ROOT / rel_path.replace("/", "\\")
    if not full_path.exists():
        return set()
    try:
        md_text = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return _extract_links(md_text, rel_path)


def rebuild_backlinks():
    """Full rebuild of the backlink graph from disk."""
    global _backlinks, _outlinks

    files = collect_files(HYPERSPACE_ROOT)
    new_backlinks: dict[str, set[str]] = {}
    new_outlinks: dict[str, set[str]] = {}

    for rel in files:
        rel_str = str(rel).replace("\\", "/")
        targets = _index_single_file(rel_str)
        new_outlinks[rel_str] = targets
        for target in targets:
            new_backlinks.setdefault(target, set()).add(rel_str)

    with _backlinks_lock:
        _backlinks = new_backlinks
        _outlinks = new_outlinks


def refresh_backlinks_for(rel_path: str):
    """Incrementally update the backlink graph for a single changed file.

    Called when a file is created or modified. Removes old outlinks from this
    file and adds new ones based on current content.
    """
    global _backlinks, _outlinks

    with _backlinks_lock:
        # Remove old outlinks from this file
        old_targets = _outlinks.get(rel_path, set())
        for target in old_targets:
            if target in _backlinks:
                _backlinks[target].discard(rel_path)
                if not _backlinks[target]:
                    del _backlinks[target]

        # Parse new outlinks
        new_targets = _index_single_file(rel_path)
        _outlinks[rel_path] = new_targets

        # Register new backlinks
        for target in new_targets:
            _backlinks.setdefault(target, set()).add(rel_path)


def remove_backlinks_for(rel_path: str):
    """Remove a file from the backlink graph (file deleted).

    Removes all outlinks from this file and cleans up backlink entries.
    Also removes this file as a backlink target.
    """
    global _backlinks, _outlinks

    with _backlinks_lock:
        # Remove outlinks from this file
        old_targets = _outlinks.pop(rel_path, set())
        for target in old_targets:
            if target in _backlinks:
                _backlinks[target].discard(rel_path)
                if not _backlinks[target]:
                    del _backlinks[target]

        # Remove this file as a target
        _backlinks.pop(rel_path, None)
