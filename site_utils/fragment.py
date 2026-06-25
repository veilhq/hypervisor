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
    # Combine content + backlinks (same as current build_page behavior)
    full_html = content_html
    if backlinks_html:
        full_html += "\n" + backlinks_html

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
