"""
Markdown rendering and HTML post-processing transforms.
"""

import re
import html as html_mod

from .config import MD
from chips import render_chip


_LIST_ITEM_RE = re.compile(r'^\s*(?:\d+[.)]|[-*+])\s')

def separate_glued_lists(md_text: str) -> str:
    """Insert a blank line before a list that directly follows a paragraph line.

    Python-Markdown (core) will not let a list interrupt a paragraph without a
    blank line between them - a very common authoring pattern across the corpus
    (`intro:\\n1. item`) otherwise renders as one run-together paragraph. This
    inserts the required blank line when a list marker line follows a non-blank,
    non-list, non-structural line, so authors can write either way.

    Skips lines inside fenced code blocks so sample code is never rewritten.
    """
    out = []
    lines = md_text.split('\n')
    in_fence = False
    fence_re = re.compile(r'^\s*(```|~~~)')
    for i, line in enumerate(lines):
        if fence_re.match(line):
            in_fence = not in_fence
        if (not in_fence and i > 0 and _LIST_ITEM_RE.match(line)):
            prev = lines[i - 1]
            prev_stripped = prev.strip()
            if (prev_stripped
                    and not _LIST_ITEM_RE.match(prev)
                    and not prev.lstrip().startswith(('#', '|', '>'))):
                out.append('')  # the separator the parser needs
        out.append(line)
    return '\n'.join(out)


def normalize_tables(md_text: str) -> str:
    """Collapse blank lines *interior* to markdown table blocks.

    Some documents are double-spaced (blank line between every line). The markdown
    tables extension requires table rows to be contiguous, so we detect table blocks
    and strip blank lines that sit *between two table rows* to let the parser
    recognize them.

    A blank line is only interior - and therefore droppable - when another table
    row follows it. A blank that is followed by non-table content marks the end of
    the table and must be preserved; dropping it would glue the next block (e.g. a
    following '## Sources' heading) onto the table, causing the parser to absorb it
    as a trailing table row.
    """
    lines = md_text.split('\n')
    result = []
    table_buf = []
    pending_blanks = []  # blank lines held while inside a table, fate undecided
    in_table = False

    for line in lines:
        stripped = line.strip()
        is_table_line = stripped.startswith('|') and stripped.endswith('|')

        if is_table_line:
            if not in_table:
                in_table = True
                table_buf = []
            # A table row after held blanks confirms those blanks were interior;
            # drop them (do not re-emit) so the rows stay contiguous.
            pending_blanks = []
            table_buf.append(line)
        elif stripped == '' and in_table:
            # Blank inside a table - hold it; only drop if a table row follows.
            pending_blanks.append(line)
        else:
            # Non-table, non-blank line: the table has ended. Flush its rows,
            # then re-emit any held blanks as the separator before this line.
            if in_table:
                result.extend(table_buf)
                result.extend(pending_blanks)
                table_buf = []
                pending_blanks = []
                in_table = False
            result.append(line)

    # Flush any remaining table buffer at end of file (trailing blanks dropped).
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
    md_text = separate_glued_lists(md_text)
    MD.reset()
    html = MD.convert(md_text)
    toc_html = getattr(MD, 'toc', '')
    return post_process(html, source_path=source_path, md_text=md_text), toc_html


# ---------------------------------------------------------------------------
# HTML post-processing - transform raw MD output into structured layout
# ---------------------------------------------------------------------------

def post_process(html: str, source_path: str | None = None, md_text: str | None = None) -> str:
    """Transform flat markdown HTML into structured document layout."""
    html = rewrite_md_links(html, source_path=source_path)
    html = link_citations(html)
    html = structure_sources(html)
    html = extract_metadata_block(html)
    html = convert_admonitions(html)
    html = convert_collapsible_sections(html)
    html = wrap_h2_sections(html)
    html = style_related_section(html)
    html = convert_mermaid_blocks(html)
    html = label_code_blocks(html)
    html = style_task_lists(html, source_path=source_path, md_text=md_text)
    html = convert_bookmark_links(html)
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

        # Already absolute (starts with /) - just convert .md to /index.html
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


# Matches a run of one or more adjacent bracketed citation numbers: [1], [2][5].
# Anchored on the token itself; surrounding-context guards are applied by the
# caller so array indices and glob patterns inside prose are left alone.
_CITATION_RUN_RE = re.compile(r'(?:\[\d{1,3}\])+')
# A single [N] within a run.
_CITATION_NUM_RE = re.compile(r'\[(\d{1,3})\]')
# Splits HTML into code/non-code segments so citations inside <code>/<pre> are skipped.
_CODE_SEGMENT_RE = re.compile(r'(<pre\b.*?</pre>|<code\b.*?</code>)', re.DOTALL | re.IGNORECASE)


def link_citations(html: str) -> str:
    """Link inline [N] citations to a numbered Sources/References list.

    Convention (see the analysis skill's Source Citation section): a document
    ends with a numbered `## Sources` (or `## References`) list, and every
    substantive claim carries an inline [N] - or grouped [2][5] - referencing
    the matching source number. This transform is a no-op unless such a section
    is present, so ordinary docs that happen to contain [0]-style brackets are
    untouched.

    Two passes:
    1. Tag each numbered source <li> with id="source-N" and a wrapping class so
       the list becomes a link target and can be styled as the sources area.
    2. Rewrite inline [N] tokens in the body into anchor links pointing at the
       matching source-N, skipping anything inside <pre>/<code> and skipping the
       sources list itself (its own numbering must stay plain).

    Runs on flat markdown HTML before section-wrapping, while the Sources
    heading is still a top-level <h2> immediately followed by its <ol>.
    """
    # Locate the Sources/References heading. Everything from here to the next
    # top-level heading (or end of document) is the sources region.
    heading_re = re.compile(
        r'<h2\b[^>]*>\s*(?:<[^>]+>)*\s*(?:Sources|References)\s*(?:</[^>]+>)*\s*</h2>\s*',
        re.IGNORECASE,
    )
    hmatch = heading_re.search(html)
    if not hmatch:
        return html

    # The sources region may contain multiple <ol> lists - the ratified format
    # allows grouping sources under ### sub-headers (Codebase / Live AWS / ...),
    # and markdown restarts <ol> numbering per group. We number every <li> across
    # all lists in the region continuously so [7] resolves to the 7th source
    # overall even when it lives in the second <ol> as its own item 1.
    region_start = hmatch.end()
    next_h2 = re.compile(r'<h[12]\b', re.IGNORECASE).search(html, region_start)
    region_end = next_h2.start() if next_h2 else len(html)

    region = html[region_start:region_end]
    if '<ol' not in region:
        return html

    # --- Pass 1: id each source <li> continuously across every <ol>. ---
    li_counter = [0]

    def _tag_li(m):
        li_counter[0] += 1
        return f'<li id="source-{li_counter[0]}" class="source-item">'

    tagged_region = re.sub(r'<li\b[^>]*>', _tag_li, region)
    tagged_region = re.sub(
        r'<ol\b', '<ol class="sources-list"', tagged_region, flags=re.IGNORECASE
    )
    source_count = li_counter[0]
    if source_count == 0:
        return html

    body_before = html[:region_start]
    body_after = html[region_end:]

    # --- Pass 2: rewrite inline [N] runs in the body, skipping code spans. ---
    def _rewrite_run(m):
        run = m.group(0)
        links = []
        any_matched = False
        for num_m in _CITATION_NUM_RE.finditer(run):
            n = int(num_m.group(1))
            # Only link numbers that actually have a matching source entry.
            if 1 <= n <= source_count:
                any_matched = True
                links.append(
                    f'<a href="#source-{n}" class="citation" '
                    f'data-citation="{n}">{n}</a>'
                )
            else:
                links.append(num_m.group(0))
        # If nothing in the run maps to a real source, leave the original text
        # untouched - don't superscript stray brackets that aren't citations.
        if not any_matched:
            return run
        return f'<sup class="citation-group">{"".join(links)}</sup>'

    def _rewrite_segment(segment: str) -> str:
        return _CITATION_RUN_RE.sub(_rewrite_run, segment)

    # Split on code spans; rewrite only the non-code parts (odd indices are code).
    parts = _CODE_SEGMENT_RE.split(body_before)
    for i in range(0, len(parts), 2):
        parts[i] = _rewrite_segment(parts[i])
    body_before = "".join(parts)

    return body_before + tagged_region + body_after


# Matches a single source <li> tagged by link_citations (id + class source-item).
# Captures the id number and the inner HTML up to the closing </li>.
_SOURCE_ITEM_RE = re.compile(
    r'<li id="source-(\d+)" class="source-item">(.*?)</li>',
    re.DOTALL,
)
# A segment that leads with a <code> span: that code is the ref's source key.
_LEADING_CODE_RE = re.compile(r'^\s*(<code>.*?</code>)(.*)$', re.DOTALL)


def structure_sources(html: str) -> str:
    """Restructure each ## Sources <li> into a stacked, keyed layout.

    The sources convention writes one numbered item per claim, where an item
    may pack several file refs separated by '; ', each ref leading with a
    backtick path (rendered <code>) and trailed by a prose description. Rendered
    flat, that is a wall of run-on text. This transform rebuilds each item's
    inner HTML into stacked sub-rows:

        <li id="source-N" class="source-item">
          <div class="source-ref">
            <code class="source-key">path</code>
            <span class="source-desc">...trailing description...</span>
          </div>
          <div class="source-ref">...next ';'-split ref...</div>
        </li>

    The <li> id stays on the group, so inline [N] citations still resolve to the
    whole source. A segment that does not lead with a <code> path (ADO/web
    sources like "Azure DevOps PR 1162 metadata ...") renders as a single
    description-only row - never mangled. Runs after link_citations (which tags
    the items) and before wrap_h2_sections.
    """
    def _rebuild(m):
        num = m.group(1)
        inner = m.group(2).strip()
        if not inner:
            return m.group(0)

        li_open = f'<li id="source-{num}" class="source-item ref-card">'

        # A source is only a splittable multi-ref manifest when it LEADS with a
        # code path AND every '; '-split segment also leads with a code path.
        # Otherwise '; ' is just sentence punctuation (prose sources like an ADO
        # merge-state explanation: "...metadata: `status:1`; `git branch...`
        # lists only `x` -> `y` ... not merged"), and splitting shreds one
        # sentence into ragged left-aligned fragments. Prose sources render as a
        # single row, untouched.
        segments = [s.strip() for s in inner.split('; ') if s.strip()]
        is_manifest = (
            len(segments) >= 1
            and all(_LEADING_CODE_RE.match(seg) for seg in segments)
        )

        if not is_manifest:
            # Single prose row - keep the whole sentence together. If it happens
            # to start with a code path, still promote just that leading token as
            # the key so a single-ref source stays keyed.
            code_m = _LEADING_CODE_RE.match(inner)
            if code_m and len(segments) == 1:
                key_html = code_m.group(1).replace(
                    '<code>', '<code class="ref-card-key">', 1
                )
                desc_html = re.sub(r'^\s*[\u2014\u2013\-:]\s*', '', code_m.group(2).strip())
                desc_part = (
                    f'<span class="ref-card-desc">{desc_html}</span>' if desc_html else ''
                )
                return li_open + f'<div class="ref-card-ref">{key_html}{desc_part}</div></li>'
            return li_open + f'<div class="ref-card-ref ref-card-ref-prose">{inner}</div></li>'

        # Manifest: each segment is a keyed file ref, stacked under the one card.
        rows = []
        for seg in segments:
            code_m = _LEADING_CODE_RE.match(seg)
            key_html = code_m.group(1).replace('<code>', '<code class="ref-card-key">', 1)
            desc_html = re.sub(r'^\s*[\u2014\u2013\-:]\s*', '', code_m.group(2).strip())
            desc_part = (
                f'<span class="ref-card-desc">{desc_html}</span>' if desc_html else ''
            )
            rows.append(f'<div class="ref-card-ref">{key_html}{desc_part}</div>')

        return li_open + ''.join(rows) + '</li>'

    return _SOURCE_ITEM_RE.sub(_rebuild, html)


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

            # Further split on <br> or newlines in case the markdown engine
            # merged consecutive admonitions into a single paragraph.
            segments = re.split(r'(?:<br\s*/?>|\n)\s*(?=\[!(?:NOTE|TIP|WARNING|CAUTION|IMPORTANT)\])', para_clean, flags=re.IGNORECASE)

            for segment in segments:
                segment = segment.strip()
                if not segment:
                    continue

                adm_match = ADMONITION_PATTERN.match(segment)
                if adm_match:
                    admonition_type = adm_match.group(1).upper()
                    # Content may contain <br> for multi-line within the same admonition
                    content = segment[adm_match.end():].strip()
                    # Convert remaining <br> to paragraph breaks for cleaner rendering
                    content = re.sub(r'\s*<br\s*/?>\s*', '</p><p>', content)
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
                    # Non-admonition content - append to the previous admonition if possible
                    if result_parts and result_parts[-1].endswith('</div></div>'):
                        last = result_parts[-1]
                        insert_point = last.rfind('</div></div>')
                        result_parts[-1] = last[:insert_point] + f'<p>{segment}</p></div></div>'
                    else:
                        result_parts.append(f'<blockquote><p>{segment}</p></blockquote>')

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
    Pull metadata lines (Created, Updated, Tags, Status, Project, ID, etc.)
    from the <ul> immediately after the first <h1> and render them as a
    chip-strip header row that speaks the Pulse visual vocabulary.

    Layout (three columns via grid):
      [WI-XX] [status]     project-tag · topic tags        Updated / Created
    """
    # Match the <h1> plus the <ul> metadata right after it (optionally with a
    # subtitle <p> between). The full <h1> is captured so the title can be
    # wrapped into a flex title-row with the topic tags pulled to its right.
    pattern = re.compile(
        r'(<h1\b[^>]*>.*?</h1>)\s*'            # full h1 (captured)
        r'(<p>.*?</p>\s*)?'                    # optional subtitle paragraph
        r'(<ul>\s*(?:<li>[^<]*?:.*?</li>\s*)+</ul>)',  # metadata list
        re.DOTALL
    )

    KNOWN_KEYS = {"id", "status", "project", "tags", "created", "updated", "related", "type", "assignee", "horizon",
                  "pr author", "pr created", "pr link"}

    def _parse_items(items):
        """Return a dict of key.lower() -> raw value string, plus a list of
        (key, value) tuples for unrecognized keys."""
        parsed = {}
        extras = []
        for item in items:
            item_clean = item.strip()
            for sub in re.split(r'<br\s*/?>', item_clean):
                sub = sub.strip()
                if not sub:
                    continue
                kv = re.match(r'^(?:<strong>)?([^:<]+?)(?:</strong>)?\s*:\s*(.+)$', sub, re.DOTALL)
                if not kv:
                    continue
                key = kv.group(1).strip()
                val = kv.group(2).strip()
                if key.lower() in KNOWN_KEYS:
                    parsed[key.lower()] = val
                else:
                    extras.append((key, val))
        return parsed, extras

    def _display_date(val):
        """Normalize 'YYYY-MM-DDTHH:MM' → 'YYYY-MM-DD HH:MM' for readability;
        pass through anything else unchanged."""
        m = re.match(r'^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})', val)
        return f"{m.group(1)} {m.group(2)}" if m else val

    def _initials(name: str) -> str:
        """Extract up to 2 initials from a full name, or pass through short values."""
        name = name.strip()
        if len(name) <= 3:
            return name.upper()
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        return parts[0][0].upper() if parts else "?"

    def _build_strip(parsed, extras):
        html_parts = ['<div class="doc-header-strip">']

        # --- LEFT: WI + Status + Project + Assignee chips (identity cluster) ---
        chips = []
        wi = parsed.get("id")
        if wi:
            chips.append(render_chip("filled", wi, extra_class="doc-header-chip doc-header-chip-wi"))
        status = parsed.get("status")
        if status:
            status_lower = status.lower()
            is_active = ("progress" in status_lower) or ("discussion" in status_lower)
            status_variant = "filled" if is_active else "outlined-muted"
            status_specific = (
                "doc-header-chip doc-header-chip-status "
                + ("doc-header-chip-status-active" if is_active else "doc-header-chip-status-idle")
            )
            # data-writeback-key marks this chip as click-to-cycle in the desktop app
            chips.append(
                render_chip(
                    status_variant,
                    status,
                    extra_class=status_specific,
                    data_attrs={"writeback-key": "status"},
                )
            )
        assignee = parsed.get("assignee")
        if assignee:
            chips.append(
                render_chip(
                    "outlined-muted",
                    _initials(assignee),
                    extra_class="doc-header-chip doc-header-chip-assignee",
                    data_attrs={"writeback-key": "assignee", "full-value": assignee},
                )
            )
        horizon = parsed.get("horizon")
        if horizon and horizon.lower() != "backlog":
            horizon_variant = "filled" if horizon.lower() == "sprint" else "outlined-accent"
            chips.append(
                render_chip(
                    horizon_variant,
                    horizon,
                    extra_class="doc-header-chip doc-header-chip-horizon",
                )
            )
        # PR author - first-class identity chip for PR-review notes (initials,
        # matching the assignee chip vocabulary) rather than a generic extra row.
        pr_author = parsed.get("pr author")
        if pr_author:
            chips.append(
                render_chip(
                    "outlined-muted",
                    _initials(pr_author),
                    extra_class="doc-header-chip doc-header-chip-pr-author",
                    data_attrs={"full-value": pr_author},
                )
            )
        # PR link - a chip-styled anchor (render_chip only emits a span, so the
        # clickable PR link is built directly, composed on the same chip primitive).
        pr_link = parsed.get("pr link")
        if pr_link:
            m_num = re.search(r'/pullrequest/(\d+)', pr_link)
            pr_label = f"PR {m_num.group(1)}" if m_num else "PR"
            chips.append(
                f'<a class="status-chip status-chip-outlined-accent '
                f'doc-header-chip doc-header-chip-pr-link" href="{pr_link}">{pr_label}</a>'
            )
        html_parts.append('<div class="doc-header-chips">' + "".join(chips) + '</div>')

        # Tags are no longer rendered in the strip - they live in the title row
        # (see _build_tags / the title-row wrap in replace_meta). This keeps the
        # strip's horizontal budget to identity chips + dates, which reflow
        # cleanly on narrow screens instead of wrapping mid-cluster.

        # --- RIGHT: dates + type (Updated → Created → PR Created → Type) ---
        right_entries = []
        for key in ("updated", "created"):
            val = parsed.get(key)
            if val:
                right_entries.append(
                    f'<span class="doc-header-date">'
                    f'<span class="doc-header-date-label">{key.capitalize()}</span>'
                    f'<span class="doc-header-date-value">{_display_date(val)}</span>'
                    f'</span>'
                )
        # PR Created - first-class date entry for PR-review notes, in the date
        # cluster alongside the doc's own Created/Updated rather than a muted extra.
        pr_created = parsed.get("pr created")
        if pr_created:
            right_entries.append(
                f'<span class="doc-header-date doc-header-date-pr-created">'
                f'<span class="doc-header-date-label">PR Created</span>'
                f'<span class="doc-header-date-value">{_display_date(pr_created)}</span>'
                f'</span>'
            )
        type_val = parsed.get("type")
        if type_val:
            right_entries.append(
                f'<span class="doc-header-date doc-header-date-type">'
                f'<span class="doc-header-date-label">Type</span>'
                f'<span class="doc-header-date-value">{type_val}</span>'
                f'</span>'
            )
        html_parts.append('<div class="doc-header-dates">' + "".join(right_entries) + '</div>')

        # --- Non-standard fields (Severity, Affected, etc.) - small block below ---
        # Filter out 'related' (moved to the ## Related section at the bottom).
        if extras:
            html_parts.append('<div class="doc-header-extras">')
            for key, val in extras:
                html_parts.append(
                    f'<div class="doc-header-extra">'
                    f'<span class="doc-header-extra-key">{key}</span>'
                    f'<span class="doc-header-extra-val">{linkify_md_paths(val)}</span>'
                    f'</div>'
                )
            html_parts.append('</div>')

        html_parts.append('</div>')
        return "\n".join(html_parts)

    def _build_tags(parsed):
        """Render topic tags as a right-aligned cluster for the title row.

        All tags are emitted; the client-side overflow module
        (features/doc-tag-overflow.js) measures the available space and
        collapses them title-first: full chips while they fit, a +N chip for
        the remainder, or a single 'N TAGS' blurb when nothing fits. The full
        comma-joined list is stashed in data-doc-tags so the JS can build the
        count and the hover tooltip without re-reading the chips."""
        tags_val = parsed.get("tags")
        if not tags_val:
            return ""
        all_tags = [t.strip() for t in tags_val.split(",") if t.strip()]
        if not all_tags:
            return ""
        import html as _html
        data_attr = _html.escape(", ".join(all_tags), quote=True)
        spans = "".join(
            f'<span class="doc-title-tag">{tag}</span>' for tag in all_tags
        )
        return (
            f'<div class="doc-title-tags" data-doc-tags="{data_attr}">'
            f'{spans}</div>'
        )

    def replace_meta(m):
        h1_full = m.group(1)
        subtitle = m.group(2) or ""
        meta_ul = m.group(3)
        items = re.findall(r'<li>(.*?)</li>', meta_ul, re.DOTALL)
        parsed, extras = _parse_items(items)
        # Related is handled by the ## Related section - drop from header row
        parsed.pop("related", None)
        tags_html = _build_tags(parsed)
        if tags_html:
            title_row = f'<div class="doc-title-row">{h1_full}{tags_html}</div>'
        else:
            title_row = h1_full
        return title_row + subtitle + _build_strip(parsed, extras)

    result = pattern.sub(replace_meta, html, count=1)

    # Also handle "Created: ...\nTags: ..." as plain <p> lines after h1 (older docs)
    p_meta_pattern = re.compile(
        r'(<h1\b[^>]*>.*?</h1>)\s*'
        r'(<p>[^<]*?</p>\s*)?'
        r'((?:<p>[A-Z][a-z]+:\s*.+?</p>\s*)+)',
        re.DOTALL
    )

    def replace_p_meta(m):
        h1_full = m.group(1)
        subtitle = m.group(2) or ""
        meta_ps = m.group(3)
        raw_items = re.findall(r'<p>([A-Z][a-z]+:\s*.+?)</p>', meta_ps, re.DOTALL)
        if not raw_items:
            return m.group(0)
        parsed, extras = _parse_items(raw_items)
        parsed.pop("related", None)
        tags_html = _build_tags(parsed)
        if tags_html:
            title_row = f'<div class="doc-title-row">{h1_full}{tags_html}</div>'
        else:
            title_row = h1_full
        return title_row + subtitle + _build_strip(parsed, extras)

    result = p_meta_pattern.sub(replace_p_meta, result, count=1)

    # --- Inject WI-ID badge before H1 title text (if doc has a work item ID) ---
    wi_match = re.search(r'doc-header-chip-wi[^>]*>([^<]+)<', result)
    if wi_match:
        wi_id = wi_match.group(1)
        # Insert parenthesized ID right after the <h1 ...> opening tag
        result = re.sub(
            r'(<h1[^>]*>)',
            rf'\1<span class="doc-header-wi-label">({wi_id})</span> ',
            result,
            count=1,
        )

    return result


def wrap_h2_sections(html: str) -> str:
    """Wrap content between <h2> tags in collapsible <details> elements.

    Each H2 section becomes a <details> with the H2 text as the <summary>,
    allowing users to collapse/expand sections. Only the document's first
    H2 section defaults open (typically "Overview", but templates vary - "Problem", "Context", "Overall Assessment", etc.) - every other section
    starts collapsed, so a freshly opened document leads with its summary
    instead of a wall of expanded content.
    """
    # Section title → Lucide icon name mapping
    SECTION_ICONS = {
        "overview": "eye",
        "design": "drafting-compass",
        "design details": "drafting-compass",
        "tasks": "square-check-big",
        "acceptance criteria": "clipboard-check",
        "implementation notes": "wrench",
        "implementation": "wrench",
        "pr notes": "git-pull-request",
        "related": "link",
        "problem": "alert-triangle",
        "concept": "lightbulb",
        "open questions": "help-circle",
        "key questions": "help-circle",
        "summary": "file-text",
        "findings": "search",
        "risk summary": "shield-alert",
        "next steps": "arrow-right",
        "next": "arrow-right",
        "references": "book-open",
        "reference links": "book-open",
        "sources": "book-marked",
        "considerations": "scale",
        "examples in codebase": "code",
        "proposed approach": "route",
        "rough solution plan": "route",
        "purpose": "target",
        "best practices": "star",
        "overall assessment": "bar-chart-2",
        "review history": "history",
        "positive notes": "check-circle",
        "maintainability concerns": "activity",
        "suggestions": "sparkles",
        "reviewer status": "users",
        "pattern overview": "layers",
        "key patterns": "layers",
        "directory structure": "folder-tree",
        "information": "info",
        "what users will see": "eye",
        "deploy prerequisites": "clipboard-list",
        "shipping in this release": "package",
    }

    parts = re.split(r'(<h2[^>]*>)', html)

    if len(parts) <= 1:
        return html

    # First part is everything before the first h2 (intro content)
    output = [parts[0]]

    i = 1
    is_first_section = True
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
        # Resolve section icon from plain text of heading. Unmapped sections
        # fall back to a neutral "section" glyph (hash) rather than rendering
        # no icon - a bare, un-indented heading sitting next to icon-led ones
        # reads as out of place. hash is the codebase's existing "sections"
        # marker (skills-map), so it stays honest: it signals "a section",
        # never a borrowed category meaning.
        plain_title = re.sub(r'<[^>]+>', '', h2_inner).strip().lower()
        icon_name = SECTION_ICONS.get(plain_title, "hash")
        icon_html = f'<i data-lucide="{icon_name}" class="section-icon"></i>'
        # Only the document's first H2 section defaults open (typically
        # "Overview", but templates vary - Problem, Context, Overall
        # Assessment, etc.) - every other section starts collapsed, so a
        # freshly opened document leads with just its summary rather than
        # a wall of expanded sections.
        open_attr = " open" if is_first_section else ""
        is_first_section = False
        output.append(
            f'<details class="doc-section"{open_attr}{id_attr}>'
            f'<summary class="doc-section-summary">{icon_html}{h2_inner}</summary>'
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
          Model: `Name` in `file/path.py` - has `field1`, `field2`
          Component: `file/path.js` - description
          API: `file/path.js` - `funcName()` description
          Backend: `file/path.py` - `View1`, `View2` (description)
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

        # Split on em-dash ( - or &#8212;) to separate path from description
        dash_split = re.split(r'\s*(?:\u2014|&#8212;|&mdash;)\s*', text, maxsplit=1)

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
            f'<details class="doc-section" open id="{section_id}">'
            f'<summary class="doc-section-summary">{title}</summary>'
            f'<div class="doc-section-content related-section-content">'
            f'{list_html}'
            f'</div>'
            f'</details>'
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


def convert_bookmark_links(html: str) -> str:
    """Convert standalone links (a <p> containing only an <a>) into bookmark cards.

    Detects patterns like:
        <p><a href="https://example.com">https://example.com</a></p>
        <p><a href="https://example.com">Link Title</a></p>

    Wraps them in a styled bookmark-card container with the URL displayed
    separately from the link text. Only triggers when the <p> contains nothing
    but the link (no surrounding text).
    """
    import re
    from urllib.parse import urlparse

    BOOKMARK_PATTERN = re.compile(
        r'<p>\s*<a\s+href="(https?://[^"]+)"[^>]*>(.*?)</a>\s*</p>',
        re.IGNORECASE | re.DOTALL
    )

    def make_bookmark(m):
        url = m.group(1)
        link_text = m.group(2).strip()
        parsed = urlparse(url)
        domain = parsed.netloc

        # If the link text is just the URL itself, use the domain as the title
        if link_text == url or link_text.startswith("http"):
            title = domain
        else:
            title = link_text

        return (
            f'<a class="bookmark-card" href="{url}" target="_blank" rel="noopener">'
            f'<span class="bookmark-card-title">{title}</span>'
            f'<span class="bookmark-card-url">{domain}{parsed.path if parsed.path != "/" else ""}</span>'
            f'</a>'
        )

    return BOOKMARK_PATTERN.sub(make_bookmark, html)
