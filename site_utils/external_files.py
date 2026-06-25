"""External file operations — import and delete .external/ documents.

Pure file-manipulation functions with no PyWebView or window dependencies.
Called by HypervisorAPI methods that handle rebuild/UI concerns.
"""

from datetime import datetime
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT


def has_metadata_header(text):
    """Check if markdown text already has a Created: metadata line."""
    for line in text.split("\n")[:10]:
        if line.strip().startswith("- Created:"):
            return True
    return False


def import_external_file(filename, content):
    """Import a markdown file into .external/ directory.

    Handles filename collisions and injects metadata header if missing.

    Args:
        filename: Original filename (e.g., "meeting-notes.md")
        content: Plain text content of the markdown file

    Returns:
        dict with ok/error status and relative path of imported file.
    """
    # Only accept markdown
    if not filename.lower().endswith((".md", ".markdown")):
        return {"ok": False, "error": "Only .md files are accepted"}

    external_dir = HYPERSPACE_ROOT / ".external"
    external_dir.mkdir(parents=True, exist_ok=True)

    # Handle filename collisions
    target = external_dir / filename
    if target.exists():
        stem = target.stem
        suffix = target.suffix
        counter = 1
        while target.exists():
            target = external_dir / f"{stem}-{counter}{suffix}"
            counter += 1

    text_content = content
    if not has_metadata_header(text_content):
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        header = (
            f"\n\n- Created: {now}\n"
            f"- Updated: {now}\n"
            f"- Tags: external\n"
            f"\n---\n\n"
        )
        if text_content.startswith("# "):
            first_newline = text_content.index("\n")
            text_content = (
                text_content[:first_newline]
                + "\n"
                + header
                + text_content[first_newline + 1:]
            )
        else:
            # Derive a title from the filename
            title = (
                filename.rsplit(".", 1)[0]
                .replace("-", " ")
                .replace("_", " ")
                .title()
            )
            text_content = f"# {title}\n" + header + text_content

    target.write_text(text_content, encoding="utf-8")
    return {"ok": True, "path": str(target.relative_to(HYPERSPACE_ROOT))}


def delete_external_file(filename):
    """Delete a file from the .external/ directory.

    Args:
        filename: Filename relative to .external/ (e.g., "meeting-notes.md")

    Returns:
        dict with ok/error status.
    """
    external_dir = HYPERSPACE_ROOT / ".external"
    target = external_dir / filename

    # Safety: only allow deletion within .external/
    try:
        target.resolve().relative_to(external_dir.resolve())
    except ValueError:
        return {"ok": False, "error": "Path traversal not allowed"}

    if not target.exists():
        return {"ok": False, "error": f"File not found: {filename}"}

    target.unlink()
    return {"ok": True}
