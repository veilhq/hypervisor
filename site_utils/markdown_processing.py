"""
Markdown rendering and HTML post-processing transforms.
"""

import re
import html as html_mod

from .config import MD


def normalize_tables(md_text: str) -> str:
    """Collapse blank lines within markdown table blocks.

    Some documents are double-spaced (blank line between every line). The markdown
    tables extension requires table rows to be contiguous, so we detect table blocks
    and strip internal blank lines to let the parser recognize them.
    """
    lines = md_text.split('\n')
    result = []
    table_buf = []
    in_table = False

    for line in lines:
        stripped = line.strip()
        is_table_line = stripped.startswith('|') and stripped.endswith('|')

        if is_table_line:
            if not in_table:
                in_table = True
                table_buf = []
            table_buf.append(line)
        elif stripped == '' and in_table:
            # Blank line inside a potential table — hold it, don't flush yet
            continue
        else:
            # Non-table, non-blank line: flush any buffered table
            if in_table:
                result.extend(table_buf)
                table_buf = []
                in_table = False
            result.append(line)

    # Flush any remaining table buffer at end of file
    if table_buf:
        result.extend(table_buf)

    return '\n'.join(result)


def render_markdown(md_text: str, source_path: str | None = None) -> tuple[str, str]:
    """Convert markdown text to post-processed HTML. Returns (html, toc_html).

    Args:
        md_text: Raw markdown content.
        source_path: Relative path to the source .md file (e.g. "work/to-do/item/story.md").
                     When provided, task list items get data-src/data-line attributes for write-back.
    """
    md_text = normalize_tables(md_text)
    MD.reset()
    html = MD.convert(md_text)
    toc_html = getattr(MD, 'toc', '')
    return post_process(html, source_path=source_path, md_text=md_text), toc_html


# ---------------------------------------------------------------------------
# HTML post-processing — transform raw MD output into structured layout
# ---------------------------------------------------------------------------

def post_process(html: str, source_path: str | None = None, md_text: str | None = None) -> str:
    """Transform flat markdown HTML into structured document layout."""
    html = rewrite_md_links(html, source_path=source_path)
    html = extract_metadata_block(html)
    html = convert_admonitions(html)
    html = convert_collapsible_sections(html)
    html = wrap_h2_sections(html)
    html = style_related_section(html)
    html = convert_mermaid_blocks(html)
    html = label_code_blocks(html)
    html = style_task_lists(html, source_path=source_path, md_text=md_text)
    return html


def rewrite_md_links(html: str, source_path: str | None = None) -> str:
    """Rewrite href="...something.md" links to point to the generated HTML pages.

    With absolute paths, each link is resolved against the source document's
    directory to produce an absolute /{resolved}/index.html href.
    """
    from pathlib import PurePosixPath as _PP

    # Determine the source document's directory for relative link resolution
    source_dir = _PP(source_path).parent if source_path else _PP(".")

    def rewrite(m):
        full_href = m.group(1)  # href="
        path = m.group(2)       # the relative path without .md

        # Don't touch absolute URLs or anchors
        if path.startswith(('http://', 'https://', '#')):
            return full_href + path + '.md"'

        # Already absolute (starts with /) — just convert .md to /index.html
        if path.startswith('/'):
            clean = path.lstrip('/')
            return full_href + '/' + clean + '/index.html"'

        # Resolve relative path against source document's directory
        resolved = source_dir / path
        # Normalize (resolve .. and .)
        parts = []
        for part in resolved.parts:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)

        if not parts:
            return full_href + '/index.html"'

        abs_href = "/" + "/".join(parts) + "/index.html"
        return full_href + abs_href + '"'

    return re.sub(r'(href=")([^"]+?)\.md"', rewrite, html)


def linkify_md_paths(val: str) -> str:
    """Convert .md file paths in meta values (including inside <code> tags) to links."""
    def code_to_link(m):
        path = m.group(1)
        link_path = path
        if link_path.startswith('.hyperspace/'):
            link_path = link_path[len('.hyperspace/'):]
        link_path = re.sub(r'\.md$', '/index.html', link_path)
        return f'<a href="/{link_path}">{path}</a>'

    return re.sub(r'<code>([^<]*?\.md)</code>', code_to_link, val)


def convert_admonitions(html: str) -> str:
    """Convert GitHub-style admonition blockquotes into styled callout boxes.

    Detects patterns like:
        > [!NOTE]
        > This is a note about something.

    Supported types: NOTE, TIP, WARNING, CAUTION, IMPORTANT

    The markdown engine may combine adjacent blockquotes into a single <blockquote>
    with multiple <p> tags, so we handle both single and multi-paragraph cases.
    """
    ADMONITION_ICONS = {
        "NOTE": "info",
        "TIP": "lightbulb",
        "WARNING": "alert-triangle",
        "CAUTION": "alert-octagon",
        "IMPORTANT": "alert-circle",
    }

    ADMONITION_PATTERN = re.compile(
        r'\[!(NOTE|TIP|WARNING|CAUTION|IMPORTANT)\]\s*(?:<br\s*/?>|\n)?\s*',
        re.IGNORECASE
    )

    def process_blockquote(m):
        """Process a single <blockquote> that may contain one or more admonitions."""
        inner = m.group(1)

        # Check if this blockquote contains any admonition markers
        if not ADMONITION_PATTERN.search(inner):
            return m.group(0)  # Not an admonition, leave as-is

        # Split on <p> boundaries to handle each paragraph
        paragraphs = re.split(r'</p>\s*<p>', inner)
        result_parts = []

        for para in paragraphs:
            # Clean up leading/trailing <p> tags from the split
            para_clean = re.sub(r'^\s*<p>\s*', '', para)
            para_clean = re.sub(r'\s*</p>\s*$', '', para_clean)

            adm_match = ADMONITION_PATTERN.match(para_clean)
            if adm_match:
                admonition_type = adm_match.group(1).upper()
                content = para_clean[adm_match.end():].strip()
                icon = ADMONITION_ICONS.get(admonition_type, "info")
                css_class = admonition_type.lower()
                label = admonition_type.capitalize()

                result_parts.append(
                    f'<div class="admonition admonition-{css_class}">'
                    f'<div class="admonition-title">'
                    f'<i data-lucide="{icon}" class="admonition-icon"></i> {label}</div>'
                    f'<div class="admonition-content"><p>{content}</p></div>'
                    f'</div>'
                )
            else:
                # Non-admonition paragraph inside a blockquote that has admonitions
                # Append to the previous admonition's content if possible
                if result_parts and result_parts[-1].endswith('</div></div>'):
                    # Insert before the closing </div></div>
                    last = result_parts[-1]
                    insert_point = last.rfind('</div></div>')
                    result_parts[-1] = last[:insert_point] + f'<p>{para_clean}</p></div></div>'
                else:
                    result_parts.append(f'<blockquote><p>{para_clean}</p></blockquote>')

        return '\n'.join(result_parts)

    # Match all blockquotes and process them
    html = re.sub(
        r'<blockquote>\s*(.*?)\s*</blockquote>',
        process_blockquote, html, flags=re.DOTALL
    )

    return html


def convert_collapsible_sections(html: str) -> str:
    """Convert +++ markers into <details>/<summary> collapsible sections.

    Markdown pattern:
        +++ Section Title
        Content here...
        +++

    Rendered HTML input (after markdown processing):
        <p>+++ Section Title</p>
        <p>Content...</p>
        <p>+++</p>

    The opening +++ can also appear as the start of a paragraph with content following.
    """
    # Match <p>+++ Title</p> ... <p>+++</p> blocks
    def replace_collapsible(m):
        title = m.group(1).strip()
        content = m.group(2).strip()
        return (
            f'<details class="collapsible">'
            f'<summary class="collapsible-title">{title}</summary>'
            f'<div class="collapsible-content">{content}</div>'
            f'</details>'
        )

    html = re.sub(
        r'<p>\+\+\+\s+(.+?)</p>\s*(.*?)\s*<p>\+\+\+</p>',
        replace_collapsible, html, flags=re.DOTALL
    )

    return html


def extract_metadata_block(html: str) -> str:
    """
    Pull metadata lines (Date, Tags, Status, Technologies, etc.) from the
    <ul> immediately after the first <h1> and render as a styled header block.
    """
    # Match a <ul> right after </h1> where items look like key: value
    pattern = re.compile(
        r'(</h1>\s*)'                          # end of h1
        r'(<p>.*?</p>\s*)?'                    # optional subtitle paragraph (may contain inline HTML)
        r'(<ul>\s*(?:<li>[^<]*?:.*?</li>\s*)+</ul>)',  # metadata list
        re.DOTALL
    )

    def replace_meta(m):
        h1_end = m.group(1)
        subtitle = m.group(2) or ""
        meta_ul = m.group(3)

        # Parse <li> items
        items = re.findall(r'<li>(.*?)</li>', meta_ul, re.DOTALL)
        meta_html = ['<div class="doc-meta">']
        for item in items:
            item_clean = item.strip()
            # Split on <br /> in case multiple metadata lines are joined
            sub_items = re.split(r'<br\s*/?>', item_clean)
            for sub in sub_items:
                sub = sub.strip()
                if not sub:
                    continue
                # Try "Key: Value" pattern
                kv = re.match(r'^(?:<strong>)?([^:<]+?)(?:</strong>)?\s*:\s*(.+)$', sub, re.DOTALL)
                if kv:
                    key = kv.group(1).strip()
                    val = linkify_md_paths(kv.group(2).strip())
                    item_class = "meta-item meta-item-status" if key.lower() == "status" else "meta-item"
                    meta_html.append(f'<div class="{item_class}"><span class="meta-key">{key}</span>'
                                     f'<span class="meta-val">{val}</span></div>')
                else:
                    meta_html.append(f'<div class="meta-item"><span class="meta-val">{sub}</span></div>')
        meta_html.append('</div>')

        return h1_end + subtitle + "\n".join(meta_html)

    result = pattern.sub(replace_meta, html, count=1)

    # Also handle "Created: ...\nTags: ..." as plain <p> lines after h1
    p_meta_pattern = re.compile(
        r'(</h1>\s*)'
        r'(<p>[^<]*?</p>\s*)?'  # optional subtitle
        r'((?:<p>[A-Z][a-z]+:\s*.+?</p>\s*)+)',  # consecutive "Key: value" paragraphs
        re.DOTALL
    )

    def replace_p_meta(m):
        h1_end = m.group(1)
        subtitle = m.group(2) or ""
        meta_ps = m.group(3)

        items = re.findall(r'<p>([A-Z][a-z]+:\s*.+?)</p>', meta_ps, re.DOTALL)
        if not items:
            return m.group(0)

        meta_html = ['<div class="doc-meta">']
        for item in items:
            kv = re.match(r'^([^:]+?):\s*(.+)$', item.strip(), re.DOTALL)
            if kv:
                key = kv.group(1).strip()
                item_class = "meta-item meta-item-status" if key.lower() == "status" else "meta-item"
                meta_html.append(f'<div class="{item_class}"><span class="meta-key">{key}</span>'
                                 f'<span class="meta-val">{kv.group(2).strip()}</span></div>')
        meta_html.append('</div>')
        return h1_end + subtitle + "\n".join(meta_html)

    result = p_meta_pattern.sub(replace_p_meta, result, count=1)
    return result


def wrap_h2_sections(html: str) -> str:
    """Wrap content between <h2> tags in collapsible <details> elements.

    Each H2 section becomes a <details open> with the H2 text as the <summary>,
    allowing users to collapse/expand sections while keeping them open by default.
    """
    parts = re.split(r'(<h2[^>]*>)', html)

    if len(parts) <= 1:
        return html

    # First part is everything before the first h2 (intro content)
    output = [parts[0]]

    i = 1
    while i < len(parts):
        h2_tag = parts[i]
        # Content after this h2 until the next h2
        content = parts[i + 1] if i + 1 < len(parts) else ""

        # Extract the h2 text and id for the summary
        h2_id_match = re.search(r'id="([^"]*)"', h2_tag)
        h2_id = h2_id_match.group(1) if h2_id_match else ""
        # Get the text between <h2...> and </h2> from the content
        h2_close_match = re.match(r'(.*?)</h2>(.*)', content, re.DOTALL)
        if h2_close_match:
            h2_inner = h2_close_match.group(1)
            section_content = h2_close_match.group(2)
        else:
            h2_inner = ""
            section_content = content

        id_attr = f' id="{h2_id}"' if h2_id else ""
        output.append(
            f'<details class="doc-section" open{id_attr}>'
            f'<summary class="doc-section-summary">{h2_inner}</summary>'
            f'<div class="doc-section-content">{section_content}</div>'
            f'</details>'
        )
        i += 2

    return "".join(output)


def style_related_section(html: str) -> str:
    """Restyle H2 sections titled 'Related' or 'See Also' into a panel matching the backlinks style.

    Also groups plain-text list items by category prefix (Model, Component, API, Backend, etc.)
    under sub-headers, and restructures each item into a path + description layout.
    """
    def _restructure_categorized_item(li_content, category):
        """Parse a categorized item and restructure into path + description blocks.

        Input patterns:
          Model: `Name` in `file/path.py` — has `field1`, `field2`
          Component: `file/path.js` — description
          API: `file/path.js` — `funcName()` description
          Backend: `file/path.py` — `View1`, `View2` (description)
        """
        # Strip the category prefix (e.g. "Model:" or "Component:") from the raw HTML
        # The prefix appears as plain text before any <code> tags
        text = li_content
        prefix_pattern = re.compile(
            r'^' + re.escape(category) + r':\s*', re.IGNORECASE
        )
        # Strip from the plain-text representation to find where content starts
        plain = re.sub(r'<[^>]+>', '', text).strip()
        prefix_match = prefix_pattern.match(plain)
        if prefix_match:
            # Find the same prefix in the HTML and strip it
            html_prefix = re.compile(
                r'^' + re.escape(category) + r':\s*', re.IGNORECASE
            )
            text = html_prefix.sub('', text.strip(), count=1)

        # Split on em-dash (— or &#8212;) to separate path from description
        dash_split = re.split(r'\s*(?:—|&#8212;|&mdash;)\s*', text, maxsplit=1)

        path_part = dash_split[0].strip()
        desc_part = dash_split[1].strip() if len(dash_split) > 1 else ""

        result = '<li class="related-item">'
        result += f'<span class="related-item-path">{path_part}</span>'
        if desc_part:
            result += f'<span class="related-item-desc">{desc_part}</span>'
        result += '</li>'
        return result

    def restyle(m):
        title = m.group(1)
        content = m.group(2)
        icon = "git-compare" if title.lower() == "related" else "external-link"
        # Generate id from title (lowercase, spaces to hyphens)
        section_id = title.strip().lower().replace(' ', '-')

        li_items = re.findall(r'<li>(.*?)</li>', content, flags=re.DOTALL)

        CATEGORY_PREFIXES = (
            "Model:", "Component:", "API:", "Backend:", "View:", "Template:",
            "Endpoint:", "Service:", "Middleware:", "Serializer:", "URL:",
        )
        groups = []
        current_group = None

        for li_content in li_items:
            link_match = re.search(r'<a href="([^"]*)"[^>]*>([^<]*)</a>', li_content)
            stripped = re.sub(r'<[^>]+>', '', li_content).strip()

            category = None
            for prefix in CATEGORY_PREFIXES:
                if stripped.startswith(prefix):
                    category = prefix.rstrip(":")
                    break

            if link_match and not category:
                href = link_match.group(1)
                link_text = link_match.group(2)
                display_path = href.replace('/index.html', '.md').lstrip('./')
                item_html = (
                    f'<li><a href="{href}">'
                    f'<i data-lucide="corner-down-right" class="backlink-icon"></i> '
                    f'{link_text}</a>'
                    f'<span class="backlink-path">{display_path}</span></li>'
                )
                group_label = "Links"
            elif category:
                item_html = _restructure_categorized_item(li_content, category)
                group_label = category
            else:
                item_html = f'<li>{li_content}</li>'
                group_label = "Other"

            if current_group and current_group[0] == group_label:
                current_group[1].append(item_html)
            else:
                current_group = (group_label, [item_html])
                groups.append(current_group)

        has_multiple_groups = len(set(g[0] for g in groups)) > 1
        list_html = ""

        if has_multiple_groups:
            for group_label, items in groups:
                list_html += f'<div class="related-group">'
                list_html += f'<div class="related-group-label">{group_label}</div>'
                list_html += f'<ul class="backlinks-list">{"".join(items)}</ul>'
                list_html += f'</div>'
        else:
            all_items = []
            for _, items in groups:
                all_items.extend(items)
            list_html = f'<ul class="backlinks-list">{"".join(all_items)}</ul>'

        return (
            f'<section class="related-section">'
            f'<h2 id="{section_id}">'
            f'<i data-lucide="{icon}" class="section-icon"></i> {title}</h2>'
            f'{list_html}</section>'
        )

    html = re.sub(
        r'<details class="doc-section"[^>]*>\s*<summary class="doc-section-summary">\s*(Related(?:\s+Docs)?|References|See Also)\s*</summary>\s*<div class="doc-section-content">(.*?)</div>\s*</details>',
        restyle, html, flags=re.DOTALL | re.IGNORECASE
    )
    return html


def _extract_id(h2_tag):
    """Extract the id attribute from an h2 tag."""
    m = re.search(r'id="([^"]*)"', h2_tag)
    return m.group(1) if m else ""


def convert_mermaid_blocks(html: str) -> str:
    """Convert mermaid code blocks into <pre class="mermaid"> for client-side rendering.

    Since codehilite strips the 'mermaid' language identifier, we detect mermaid
    blocks by their content patterns (erDiagram, flowchart, sequenceDiagram, etc.)
    in generic highlight blocks that have no syntax-highlighted spans.
    """
    # Mermaid diagram type keywords that appear at the start of the code
    mermaid_keywords = (
        'erDiagram', 'flowchart', 'sequenceDiagram', 'classDiagram',
        'stateDiagram', 'gantt', 'pie', 'gitgraph', 'mindmap', 'timeline',
        'graph ', 'graph\n', 'C4Context', 'C4Container', 'C4Component',
        'C4Deployment', 'journey', 'quadrantChart', 'xychart-beta',
        'block-beta', 'sankey-beta', 'packet-beta',
    )

    def maybe_mermaid(m):
        raw = m.group(1)
        # Only match blocks with no Pygments syntax spans (unrecognized language)
        if '<span class="' in raw and 'class="mermaid"' not in raw:
            return m.group(0)
        text = html_mod.unescape(raw.strip())
        # Check if content starts with a mermaid keyword
        if any(text.startswith(kw) for kw in mermaid_keywords):
            return f'<div class="mermaid-wrap"><pre class="mermaid">{text}</pre></div>'
        return m.group(0)

    # Match generic codehilite output: <div class="highlight"><pre><span></span><code>...</code></pre></div>
    html = re.sub(
        r'<div class="highlight"><pre><span></span><code>(.*?)</code></pre></div>',
        maybe_mermaid, html, flags=re.DOTALL
    )
    return html


def label_code_blocks(html: str) -> str:
    """Add a language label to fenced code blocks based on codehilite classes."""
    lang_map = {
        "python": "python", "javascript": "javascript", "jsx": "jsx",
        "typescript": "typescript", "tsx": "tsx", "bash": "bash",
        "shell": "shell", "sql": "sql", "json": "json", "yaml": "yaml",
        "html": "html", "css": "css", "terraform": "terraform",
        "hcl": "hcl", "markdown": "markdown", "text": "text",
        "nix": "nix",
    }

    def add_label(m):
        pre_tag = m.group(0)
        # Try to find language from class
        cls_match = re.search(r'class="[^"]*\blanguage-(\w+)', pre_tag)
        if not cls_match:
            cls_match = re.search(r'class="[^"]*\bhighlight (\w+)', pre_tag)
        if not cls_match:
            # Check inside <code> tag
            code_cls = re.search(r'<code class="[^"]*\blanguage-(\w+)', pre_tag)
            if code_cls:
                cls_match = code_cls

        if cls_match:
            lang = cls_match.group(1).lower()
            label = lang_map.get(lang, lang)
            return f'<div class="code-block"><span class="code-lang">{label}</span>{pre_tag}</div>'
        return f'<div class="code-block">{pre_tag}</div>'

    return re.sub(r'<div class="highlight"><pre>.*?</pre></div>|<pre><code.*?</code></pre>',
                  add_label, html, flags=re.DOTALL)


def style_task_lists(html: str, source_path: str | None = None, md_text: str | None = None) -> str:
    """Convert [ ] and [x] checkbox patterns into styled elements.

    When source_path and md_text are provided, each task <li> gets data-src and
    data-line attributes so the desktop app can write changes back to the source file.
    """
    # Build an ordered list of source line numbers for task items.
    # Tasks appear in the HTML in the same order as in the source markdown,
    # so we can pair them by index.
    task_line_numbers = []
    if source_path and md_text:
        for line_num, line in enumerate(md_text.splitlines()):
            stripped = line.strip()
            if stripped.startswith('- [ ] ') or stripped.startswith('- [x] ') or stripped.startswith('- [X] '):
                task_line_numbers.append(line_num)

    task_index = [0]  # mutable counter for closure

    # Scan through the HTML, replacing task <li> elements in order
    result = []
    pos = 0
    open_pattern = re.compile(r'<li>\s*(?:<p>)?\s*\[ \]\s*')
    done_pattern = re.compile(r'<li>\s*(?:<p>)?\s*\[x\]\s*', re.IGNORECASE)

    while pos < len(html):
        open_match = open_pattern.search(html, pos)
        done_match = done_pattern.search(html, pos)

        # Find the earliest match
        match = None
        is_open = True
        if open_match and done_match:
            if open_match.start() <= done_match.start():
                match = open_match
                is_open = True
            else:
                match = done_match
                is_open = False
        elif open_match:
            match = open_match
            is_open = True
        elif done_match:
            match = done_match
            is_open = False

        if not match:
            result.append(html[pos:])
            break

        # Append everything before this match
        result.append(html[pos:match.start()])

        # Add data attributes if we have source info for this task
        data_attrs = ""
        if source_path and task_index[0] < len(task_line_numbers):
            line_num = task_line_numbers[task_index[0]]
            data_attrs = f' data-src="{source_path}" data-line="{line_num}"'
        task_index[0] += 1

        if is_open:
            result.append(f'<li class="task task-open"{data_attrs}><span class="task-box">&#9744;</span> ')
        else:
            result.append(f'<li class="task task-done"{data_attrs}><span class="task-box">&#9745;</span> ')

        pos = match.end()

    return "".join(result)
