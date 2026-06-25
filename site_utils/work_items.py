"""Work item operations — mark done, move files, update _index.md.

Pure file-manipulation functions with no PyWebView or window dependencies.
Called by HypervisorAPI methods that handle watcher/rebuild/UI concerns.
"""

import re
import time
from datetime import datetime
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT


def mark_done(file_path):
    """Move a work item from work/to-do/ to work/done/.

    Performs:
    1. Reads source, updates Status to Complete + Updated timestamp
    2. Writes the updated content directly to work/done/ (avoids watcher race)
    3. Deletes the source file from work/to-do/ (with retry for Windows locks)
    4. Regenerates _index.md

    Args:
        file_path: Path relative to .hyperspace/ (e.g. "work/to-do/my-item.md")

    Returns:
        dict with ok/error status, new_path on success, and
        ignore_paths list for watcher suppression.
    """
    full_path = HYPERSPACE_ROOT / file_path
    if not full_path.exists():
        return {"ok": False, "error": f"File not found: {file_path}"}

    # Validate it's in work/to-do/
    rel = Path(file_path)
    parts = rel.parts
    if len(parts) < 3 or parts[0] != "work" or parts[1] != "to-do":
        return {"ok": False, "error": "File is not in work/to-do/"}

    filename = rel.name
    done_dir = HYPERSPACE_ROOT / "work" / "done"
    done_dir.mkdir(parents=True, exist_ok=True)
    done_path = done_dir / filename

    # Prevent overwrite
    if done_path.exists():
        return {"ok": False, "error": f"A file named '{filename}' already exists in work/done/"}

    # 1. Read and update metadata
    text = full_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    status_pattern = re.compile(r'^(\s*-\s*Status\s*:\s*)(.+)$', re.IGNORECASE)
    updated_pattern = re.compile(r'^(\s*-\s*Updated\s*:\s*)(.+)$', re.IGNORECASE)

    for i, line in enumerate(lines):
        m = status_pattern.match(line)
        if m:
            lines[i] = m.group(1) + "Complete"
            continue
        m = updated_pattern.match(line)
        if m:
            lines[i] = m.group(1) + now

    # 2. Write directly to destination (skips modifying the source file,
    #    which would trigger the watcher and cause a file-lock race on Windows)
    done_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 3. Delete source — retry on Windows file-locking from concurrent builds/watcher
    deleted = False
    for attempt in range(5):
        try:
            full_path.unlink()
            deleted = True
            break
        except PermissionError:
            # File likely locked by watcher or background build thread
            time.sleep(0.2 * (attempt + 1))
        except OSError:
            break

    # 4. Regenerate _index.md
    _regenerate_index()

    return {
        "ok": True,
        "new_path": f"work/done/{filename}",
        "source_deleted": deleted,
        "ignore_paths": [str(full_path), str(done_path)],
    }


def _regenerate_index():
    """Regenerate _index.md using the MCP index_file module directly.

    Imports the hv_mcp package functions to rebuild the in-memory index
    and regenerate _index.md. This ensures the desktop app and MCP server
    produce identical index output.
    """
    import sys

    # Ensure hv_mcp is importable
    hypervisor_dir = Path(__file__).resolve().parent.parent
    if str(hypervisor_dir) not in sys.path:
        sys.path.insert(0, str(hypervisor_dir))

    try:
        from hv_mcp.index import rebuild_index
        from hv_mcp.index_file import regenerate_index_file

        rebuild_index()
        regenerate_index_file()
    except Exception:
        # Best effort — don't crash the app if module import fails
        pass
