# Post-Processing

The transforms that turn raw HTML into polished, interactive output.

---

## Why Post-Process?

The markdown library produces valid HTML, but it's basic. Post-processing adds the features that make Hypervisor feel like an application rather than a plain document viewer:

- Cross-document links that actually work
- Metadata displayed as a styled bar
- Sections wrapped in visual panels
- Code blocks with language labels
- Task lists with interactive checkboxes

## The Transform Pipeline

`post_process()` runs seven transforms in a fixed order. Order matters — some transforms depend on the output of earlier ones.

```python
def post_process(html, source_path=""):
    html = rewrite_md_links(html, source_path)      # 1. Fix links first
    html = extract_metadata_block(html)              # 2. Style metadata
    html = wrap_h2_sections(html)                    # 3. Add section panels
    html = style_related_section(html)               # 4. Restructure Related sections
    html = convert_mermaid_blocks(html)              # 5. Enable diagrams
    html = label_code_blocks(html)                   # 6. Add language labels
    html = style_task_lists(html)                    # 7. Style checkboxes
    return html
```

## Transform 1: `rewrite_md_links`

**Problem:** Markdown links point to `.md` files (`[text](other-doc.md)`), but the generated site uses `/index.html` paths.

**Solution:** Find every `href` that ends in `.md` and rewrite it to the correct HTML path.

```python
# Before: href="context/cms-architecture.md"
# After:  href="../context/cms-architecture/index.html"
```

This runs first because other transforms may parse the HTML and would break if links pointed to non-existent paths.

### How it calculates relative paths

If you're in `patterns/django/soft-delete.md` and link to `context/cms.md`, the transform needs to figure out the relative path from the current page's output location to the target's output location:

```
Current page: site/patterns/django/soft-delete/index.html
Target page:  site/context/cms/index.html
Relative:     ../../../context/cms/index.html
```

It uses `PurePosixPath` (POSIX paths work in URLs regardless of OS) to calculate the correct number of `../` segments.

## Transform 2: `extract_metadata_block`

**Problem:** Document metadata (Created, Tags, Related, etc.) is just plain text after the H1 heading.

**Solution:** Detect the metadata pattern and render it as a styled key-value bar.

```markdown
# Document Title

- Created: 2026-02-17
- Tags: django, python
- Related: [Other Doc](other.md)
```

becomes a horizontal bar with styled labels and values. Tags become clickable, Related links are rendered as proper anchors.

### Detection logic

The transform looks for consecutive lines starting with `- ` immediately after the first `<h1>`. It stops at the first blank line or non-metadata content.

## Transform 3: `wrap_h2_sections`

**Problem:** Long documents are a wall of text with no visual structure.

**Solution:** Wrap content between H2 headings in collapsible `<details class="doc-section" open>` panels. Each section is open by default but can be collapsed by clicking the summary header.

```html
<!-- Before -->
<h2 id="section-title">Section Title</h2>
<p>Content here...</p>

<!-- After -->
<details class="doc-section" open id="section-title">
  <summary class="doc-section-summary">Section Title</summary>
  <div class="doc-section-content">
    <p>Content here...</p>
  </div>
</details>
```

The CSS adds a left border, subtle background, hover highlight, and a rotating arrow indicator. Sections use native `<details>/<summary>` behavior — no JS required for collapse/expand.

## Transform 4: `style_related_section`

**Problem:** "Related" sections at the bottom of documents are just flat bullet lists.

**Solution:** Detect sections titled "Related" or "See Also" and restructure them with category grouping. Items are grouped by prefix (Model, Component, API, etc.) under sub-headers.

## Transform 5: `convert_mermaid_blocks`

**Problem:** Mermaid diagram syntax in code blocks needs special handling for client-side rendering.

**Solution:** Detect code blocks containing mermaid syntax and convert them from `<code class="language-mermaid">` to `<pre class="mermaid">`, which the Mermaid.js library picks up and renders as SVG diagrams.

## Transform 6: `label_code_blocks`

**Problem:** Code blocks don't indicate what language they contain.

**Solution:** Add a small label in the top-right corner of each code block showing the language.

```html
<div class="highlight">
  <span class="code-label">python</span>
  <pre>...</pre>
</div>
```

The language is detected from the CSS class that Pygments adds (e.g., `language-python`, `language-javascript`).

## Transform 7: `style_task_lists`

**Problem:** Markdown checkboxes (`- [ ]` and `- [x]`) render as plain text.

**Solution:** Convert them into styled, interactive checkboxes. In the desktop app, clicking a checkbox writes the change back to the source `.md` file.

```markdown
- [ ] Incomplete task
- [x] Completed task
```

becomes interactive checkbox elements with custom styling.

## How Transforms Use HTML Parsing

Most transforms work with string operations (regex, `.replace()`, `.split()`) rather than a full HTML parser. This is intentional:

- **Speed** — string operations are faster than DOM parsing for simple patterns
- **Simplicity** — no dependency on BeautifulSoup or lxml
- **Predictability** — the markdown library produces consistent HTML structure

The trade-off is that transforms are somewhat fragile — they assume specific HTML patterns from the markdown library. But since Hypervisor controls both the input (markdown conventions) and the rendering (fixed library config), this works reliably.

## Reference Links

- [Regular expressions in Python](https://docs.python.org/3/library/re.html) — used heavily in transforms
- [PurePosixPath](https://docs.python.org/3/library/pathlib.html#pathlib.PurePosixPath) — URL-safe path manipulation
- [Mermaid.js](https://mermaid.js.org/) — the diagram rendering library

## Next

→ [CSS Architecture](../06-css-architecture/index.html) — how the modular CSS system works
