"""Idea operations — delete implemented ideas.

Pure file-manipulation functions with no PyWebView or window dependencies.
Called by HypervisorAPI methods that handle watcher/rebuild/UI concerns.
"""

import time
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT


def delete_idea(filename):
    """Delete an idea file from the ideas/ directory.

    Used when an idea has been implemented (promoted to a work item and completed)
    or is no longer relevant.

    Args:
        filename: Filename relative to ideas/ (e.g., "my-cool-idea.md")

    Returns:
        dict with ok/error status.
    """
    ideas_dir = HYPERSPACE_ROOT / "ideas"
    target = ideas_dir / filename

    # Safety: only allow deletion within ideas/
    try:
        target.resolve().relative_to(ideas_dir.resolve())
    except ValueError:
        return {"ok": False, "error": "Path traversal not allowed"}

    if not target.exists():
        return {"ok": False, "error": f"File not found: {filename}"}

    # Don't allow deleting the conventions file
    if filename == "_conventions.md":
        return {"ok": False, "error": "Cannot delete the conventions file"}

    # Retry on Windows file-locking from concurrent builds/watcher
    deleted = False
    for attempt in range(5):
        try:
            target.unlink()
            deleted = True
            break
        except PermissionError:
            time.sleep(0.2 * (attempt + 1))
        except OSError as e:
            return {"ok": False, "error": str(e)}

    if not deleted:
        return {"ok": False, "error": "Could not delete file (locked)"}

    # Regenerate _index.md
    _regenerate_index()

    return {"ok": True}


def _regenerate_index():
    """Regenerate _index.md using the MCP index_file module."""
    import sys

    hypervisor_dir = Path(__file__).resolve().parent.parent
    if str(hypervisor_dir) not in sys.path:
        sys.path.insert(0, str(hypervisor_dir))

    try:
        from hv_mcp.index import rebuild_index
        from hv_mcp.index_file import regenerate_index_file

        rebuild_index()
        regenerate_index_file()
    except Exception:
        pass
