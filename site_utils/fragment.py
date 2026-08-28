"""
Content fragment generation for the SPA shell architecture.

Each markdown document is output as a JSON fragment containing just the
content, metadata, and rendering hints — rather than a full HTML page.
The single shell.html loads these fragments dynamically via fetch.
"""

import json
import re
from pathlib import PurePosixPath


# Mermaid detection — same keywords as markdown_processing.convert_mermaid_blocks
_MERMAID_KEYWORDS = (
    'erDiagram', 'flowchart', 'sequenceDiagram', 'classDiagram',
    'stateDiagram', 'gantt', 'pie', 'gitgraph', 'mindmap', 'timeline',
    'graph ', 'graph\n', 'C4Context', 'C4Container', 'C4Component',
    'C4Deployment', 'journey', 'quadrantChart', 'xychart-beta',
    'block-beta', 'sankey-beta', 'packet-beta',
)


def has_mermaid(content_html):
    """Detect whether rendered HTML contains mermaid diagrams."""
    return 'class="mermaid"' in content_html


def make_breadcrumb_parts(rel_path_str):
    """Return breadcrumb path parts as a list of strings.

    Example: "work/to-do/my-item.md" → ["work", "to-do", "my-item"]
    """
    parts = PurePosixPath(rel_path_str).parts
    return [p.replace(".md", "") for p in parts]


def build_fragment(content_html, title, rel_path_str, toc_html="",
                   backlinks_html="", page_type="doc", source_path=None):
    """Build a content fragment dict ready for JSON serialization.

    Args:
        content_html: The rendered article HTML (inner content).
        title: Document title.
        rel_path_str: Relative path used for breadcrumbs and routing.
        toc_html: Table of contents HTML (the <ul> from markdown TOC extension).
        backlinks_html: Rendered backlinks section HTML.
        page_type: One of: doc, index, home, utility, learn, pinboard.
        source_path: Path to the source .md file (for writeback features).

    Returns:
        dict with the fragment schema fields.
    """
    # Extract the styled Related/See Also/References section from content body
    related_html, content_html = _extract_related_section(content_html)

    # Build unified connections section from backlinks + related
    connections_html = _build_connections_section(backlinks_html, related_html)

    full_html = content_html
    if connections_html:
        full_html += "\n" + connections_html

    # Determine if TOC should be shown (same logic as page_generation.build_page)
    show_toc = ""
    if toc_html and toc_html.strip() and '<li>' in toc_html:
        li_count = toc_html.count('<li>')
        if li_count >= 3:
            show_toc = toc_html

    return {
        "title": title,
        "html": full_html,
        "toc": show_toc,
        "breadcrumbs": make_breadcrumb_parts(rel_path_str),
        "sourcePath": source_path or rel_path_str,
        "hasMermaid": has_mermaid(full_html),
        "pageType": page_type,
    }


def write_fragment(fragment_dict, output_path):
    """Serialize a fragment dict to a JSON file.

    Args:
        fragment_dict: The fragment data from build_fragment().
        output_path: pathlib.Path where the JSON file should be written.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(fragment_dict, ensure_ascii=False, separators=(',', ':'))
    output_path.write_text(json_str, encoding="utf-8")


# ---------------------------------------------------------------------------
# Connections section — unified Related + Referenced By
# ---------------------------------------------------------------------------

# Pattern matches the <details class="doc-section" ...> wrapper produced by
# style_related_section() for Related/See Also/References headings.
# Key marker: inner div has class "related-section-content" — distinguishes
# the restyled link-list from regular content sections titled "Related X".
_RELATED_SECTION_RE = re.compile(
    r'<details class="doc-section"[^>]*>.*?<div class="doc-section-content related-section-content">.*?</details>',
    re.DOTALL,
)


def _extract_related_section(content_html):
    """Remove the styled Related/See Also section from content HTML.

    Returns (extracted_html, cleaned_content_html).
    """
    match = _RELATED_SECTION_RE.search(content_html)
    if not match:
        return "", content_html
    extracted = match.group(0)
    cleaned = content_html[:match.start()] + content_html[match.end():]
    return extracted, cleaned


def _build_connections_section(backlinks_html, related_html):
    """Merge backlinks and related content into one unified connections section."""
    if not backlinks_html and not related_html:
        return ""

    inner = ""

    # Related documents group (from in-document ## Related section)
    if related_html:
        # Extract the inner content from the <details> wrapper
        content_match = re.search(
            r'<div class="doc-section-content[^"]*">(.*?)</div>\s*</details>',
            related_html, re.DOTALL
        )
        if content_match:
            inner += (
                '<div class="connections-group">'
                '<div class="connections-group-label">'
                '<i data-lucide="external-link" class="backlink-icon"></i> Related'
                '</div>'
                f'{content_match.group(1)}'
                '</div>'
            )

    # Referenced By group (from backlink index)
    if backlinks_html:
        # Extract just the <ul> from the backlinks section
        list_match = re.search(
            r'<ul class="backlinks-list">(.*?)</ul>',
            backlinks_html, re.DOTALL
        )
        if list_match:
            inner += (
                '<div class="connections-group">'
                '<div class="connections-group-label">'
                '<i data-lucide="link" class="backlink-icon"></i> Referenced By'
                '</div>'
                f'<ul class="backlinks-list">{list_match.group(1)}</ul>'
                '</div>'
            )

    if not inner:
        return ""

    return (
        '<section class="connections-section">'
        '<h2><i data-lucide="network" class="section-icon"></i> Connections</h2>'
        f'{inner}'
        '</section>'
    )
