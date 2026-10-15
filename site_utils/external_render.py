"""Rendering for non-markdown files in the .external/ directory.

The .external/ directory accepts assorted dropped-in files, not just markdown.
This module turns each supported non-md file into a content fragment HTML
string that renders inside one shared visual frame (wrap_external), so a .txt,
a .sql, and a .png all look like they belong in the same app - only the body
of the frame differs by type.

Scope boundary: these extensions are recognized only under the .external/
prefix. Markdown stays the only recognized type everywhere else in hyperspace.

Type routing:
  - text (.txt, .log)        -> escaped text in a <pre>
  - code (.sql)              -> pygments-highlighted code
  - images (.png/.jpg/...)   -> <img> pointing at the asset copied into site/
  - binaries (.xlsx/.docx/.zip) -> header-only info page (no copy, no download);
                                   the file already lives on the operator's disk
  - .rtf                     -> not listed here, so it stays ignored
"""

import html as _html
from pathlib import Path, PurePosixPath

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

# --- Supported extension sets (lowercase, with leading dot) ---

TEXT_EXTS = {".txt", ".log"}
# Map code extensions to their pygments lexer name.
CODE_EXTS = {".sql": "sql"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
BINARY_EXTS = {".xlsx", ".docx", ".zip"}

# Every non-md extension the .external/ pipeline recognizes.
SUPPORTED_EXTS = TEXT_EXTS | set(CODE_EXTS) | IMAGE_EXTS | BINARY_EXTS

# Extensions whose content is readable text (fed into search as raw text).
TEXT_LIKE_EXTS = TEXT_EXTS | set(CODE_EXTS)

# Extensions whose bytes must be copied into site/ to be viewable in-app.
COPY_EXTS = IMAGE_EXTS

# Lucide icon name per extension, for the frame header and index rows.
_ICON_FOR_EXT = {
    ".txt": "file-text",
    ".log": "file-text",
    ".sql": "database",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".gif": "image",
    ".webp": "image",
    ".svg": "image",
    ".xlsx": "sheet",
    ".docx": "file-type",
    ".zip": "file-archive",
}


def is_supported_external(rel_posix: str) -> bool:
    """True if rel_posix is a .external/ file with a supported non-md extension."""
    p = PurePosixPath(rel_posix)
    if not rel_posix.startswith(".external/"):
        return False
    return p.suffix.lower() in SUPPORTED_EXTS


def icon_for_ext(ext: str) -> str:
    """Lucide icon name for a file extension (falls back to a generic file icon)."""
    return _ICON_FOR_EXT.get(ext.lower(), "file")


def external_title(rel_posix: str) -> str:
    """Derive a human title from a non-md external file's name.

    Non-md files have no markdown '# Title' header, so the filename is the
    best available title. The extension is kept visible so the type reads at
    a glance in listings and breadcrumbs.
    """
    return PurePosixPath(rel_posix).name


def external_date(abs_path: Path) -> str:
    """Filesystem mtime as a YYYY-MM-DDTHH:MM string for index sorting.

    Non-md files carry no 'Updated:' metadata, so the file's modification time
    is the sort key. Returns the undated sentinel if the file is missing.
    """
    from datetime import datetime
    try:
        ts = abs_path.stat().st_mtime
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M")
    except OSError:
        return "0000-00-00T00:00"


def _human_size(num_bytes: int) -> str:
    """Format a byte count as a short human-readable size."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def wrap_external(body_html: str, *, name: str, ext: str, size: int) -> str:
    """Wrap type-specific body HTML in the shared .external-doc frame.

    Every non-md external renderer emits this same outer structure, so the
    header (icon, filename, type badge, size) is identical across types and
    only body_html varies. One CSS block (.external-doc) styles the frame.

    Previewable external files render on the plain content area (page type
    "external-doc"), not inside the recessed markdown doc surface, so this
    bordered card is the single container - no surface well behind it.
    """
    icon = icon_for_ext(ext)
    badge = ext.lstrip(".").upper()
    size_str = _human_size(size)
    return (
        '<div class="external-doc">'
        '<div class="external-doc-header">'
        f'<i data-lucide="{icon}" class="external-doc-icon"></i>'
        f'<span class="external-doc-name">{_html.escape(name)}</span>'
        f'<span class="external-doc-badge">{badge}</span>'
        f'<span class="external-doc-meta">{size_str}</span>'
        '</div>'
        f'<div class="external-doc-body">{body_html}</div>'
        '</div>'
    )


def _render_text_body(text: str) -> str:
    """Plain text in a <pre> block, HTML-escaped."""
    return f'<pre class="external-text">{_html.escape(text)}</pre>'


def _render_code_body(text: str, lexer_name: str) -> str:
    """Syntax-highlighted code via pygments.

    Uses cssclass 'highlight' so the output reuses the codehilite CSS already
    shipped in the stack - no new highlight stylesheet needed.
    """
    try:
        lexer = get_lexer_by_name(lexer_name)
    except ClassNotFound:
        # Unknown lexer - degrade to plain text rather than crash the build.
        return _render_text_body(text)
    formatter = HtmlFormatter(cssclass="highlight", nowrap=False)
    return highlight(text, lexer, formatter)


def _render_image_body(asset_href: str, name: str) -> str:
    """An <img> pointing at the asset copied into site/.external/."""
    return (
        f'<img class="external-image" src="{asset_href}" '
        f'alt="{_html.escape(name)}" loading="lazy">'
    )


def _render_binary_body(ext: str) -> str:
    """Standalone centered card for a binary type - no preview, no download.

    The file already lives in the operator's .external/ directory on disk, so
    there is nothing to download. Rendered as a single centered card holding a
    broken-file icon stacked above a short description. The page opts out of the
    recessed doc surface (see build_doc_pages page type) so the card floats on
    its own in the content area.
    """
    kind = ext.lstrip(".").upper()
    return (
        '<div class="hv-empty-state">'
        '<i data-lucide="file-x" class="hv-empty-state-icon"></i>'
        '<p class="hv-empty-state-title">No preview available</p>'
        '<p class="hv-empty-state-msg">'
        f'This {kind} file is stored in <code>.external/</code>. '
        'Open it from your filesystem.'
        '</p>'
        '</div>'
    )


def read_text_fallback(abs_path: Path) -> str:
    """Read a text-like file with encoding fault tolerance (for render + search)."""
    try:
        return abs_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def render_external_file(abs_path: Path, rel_posix: str, asset_href: str | None = None) -> str:
    """Render a non-md external file to its shared-frame content HTML.

    Args:
        abs_path: Absolute path to the source file.
        rel_posix: Posix relative path (e.g. ".external/scripts/phase1-validate.sql").
        asset_href: For image types, the href the <img> should point at (the
                    file copied into site/). Ignored for other types.

    Returns:
        Content HTML string ready to be the fragment 'html' field. Returns an
        empty string if the extension is not supported.
    """
    ext = PurePosixPath(rel_posix).suffix.lower()
    name = PurePosixPath(rel_posix).name
    try:
        size = abs_path.stat().st_size
    except OSError:
        size = 0

    # Binaries have no preview: render just the centered empty-state, with no
    # surrounding frame or header chrome - the icon + message float in the
    # content area on their own.
    if ext in BINARY_EXTS:
        return _render_binary_body(ext)

    if ext in TEXT_EXTS:
        body = _render_text_body(read_text_fallback(abs_path))
    elif ext in CODE_EXTS:
        body = _render_code_body(read_text_fallback(abs_path), CODE_EXTS[ext])
    elif ext in IMAGE_EXTS:
        body = _render_image_body(asset_href or "", name)
    else:
        return ""

    return wrap_external(body, name=name, ext=ext, size=size)
