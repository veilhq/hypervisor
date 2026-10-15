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


def import_external_file(filename, content, encoding="text"):
    """Import a dropped file into the .external/ directory.

    Markdown files get a metadata header injected if missing (so they render
    with a title and dates). Other supported types are written as-is: text
    types from their text content, binary/image types decoded from base64.

    Args:
        filename: Original filename (e.g. "meeting-notes.md", "chart.png").
        content: File content - plain text when encoding="text", base64 string
                 when encoding="base64".
        encoding: "text" (default) or "base64". The frontend sends base64 for
                  images and binaries, which cannot survive a text read.

    Returns:
        dict with ok/error status and relative path of imported file.
    """
    import base64

    from site_utils.external_render import SUPPORTED_EXTS

    lower = filename.lower()
    is_markdown = lower.endswith((".md", ".markdown"))
    ext = Path(filename).suffix.lower()

    if not is_markdown and ext not in SUPPORTED_EXTS:
        return {"ok": False, "error": f"Unsupported file type: {ext or filename}"}

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

    # Binary / image types: decode base64 and write bytes, no header injection.
    if encoding == "base64":
        try:
            raw = base64.b64decode(content)
        except (ValueError, TypeError) as e:
            return {"ok": False, "error": f"Invalid base64 content: {e}"}
        target.write_bytes(raw)
        return {"ok": True, "path": str(target.relative_to(HYPERSPACE_ROOT))}

    # Non-markdown text types (.txt/.sql): write as-is, no header injection.
    if not is_markdown:
        target.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(target.relative_to(HYPERSPACE_ROOT))}

    # Markdown: inject a metadata header if missing.
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
