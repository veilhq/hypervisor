"""
Backlink index builder — scans markdown documents for .md links and builds a reverse map.
"""

import re
from pathlib import PurePosixPath

from .config import HYPERSPACE_ROOT
from .file_utils import get_title, nice_name, href_for


def build_backlink_index(files):
    """Scan all documents for .md links and return a reverse map.

    Returns dict: {target_rel_posix: [(source_rel, source_title), ...]}
    where target_rel_posix is the normalized relative path of the linked doc.
    """
    backlinks = {}

    for rel in files:
        md_path = HYPERSPACE_ROOT / rel
        md_text = md_path.read_text(encoding="utf-8")
        source_title = get_title(md_text, nice_name(rel.name))
        source_posix = str(rel).replace("\\", "/")

        # Find all markdown-style links to .md documents
        # Matches [text](path.md) and [text](../path.md) etc.
        for m in re.finditer(r'\[([^\]]*)\]\(([^)]*?\.md)\)', md_text):
            link_path = m.group(2)

            # Resolve relative path against source document's directory
            source_dir = PurePosixPath(source_posix).parent
            resolved = _resolve_link(source_dir, link_path)

            if resolved and resolved != source_posix:
                if resolved not in backlinks:
                    backlinks[resolved] = []
                # Avoid duplicate entries from same source
                if not any(s[0] == source_posix for s in backlinks[resolved]):
                    backlinks[resolved].append((source_posix, source_title))

    return backlinks


def _resolve_link(source_dir, link_path):
    """Resolve a relative .md link against a source directory to a normalized path."""
    try:
        # Handle absolute-from-root paths (starting with /)
        if link_path.startswith("/"):
            resolved = PurePosixPath(link_path.lstrip("/"))
        else:
            resolved = (source_dir / link_path)

        # Normalize (resolve ..)
        parts = []
        for part in resolved.parts:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)

        if not parts:
            return None
        return str(PurePosixPath(*parts))
    except Exception:
        return None


def render_backlinks_html(backlinks_for_doc):
    """Render the 'Referenced By' HTML section for a document."""
    if not backlinks_for_doc:
        return ""

    items = []
    for source_posix, source_title in sorted(backlinks_for_doc, key=lambda x: x[1].lower()):
        href = href_for(PurePosixPath(source_posix))
        items.append(
            f'<li><a href="{href}"><i data-lucide="corner-down-right" class="backlink-icon"></i> '
            f'{source_title}</a>'
            f'<span class="backlink-path">{source_posix}</span></li>'
        )

    return (
        '<section class="backlinks-section">'
        '<h2><i data-lucide="link" class="section-icon"></i> Referenced By</h2>'
        '<ul class="backlinks-list">' +
        "\n".join(items) +
        '</ul></section>'
    )
