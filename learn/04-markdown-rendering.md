# Markdown Rendering

How markdown text becomes styled HTML — the rendering engine and its configuration.

---

## The Markdown Library

Hypervisor uses Python's [`markdown`](https://python-markdown.github.io/) library to convert `.md` files to HTML. It's configured once in `config.py` and reused for every document:

```python
import markdown

MD = markdown.Markdown(
    extensions=["fenced_code", "codehilite", "tables", "toc", "meta", "sane_lists"],
    extension_configs={
        "codehilite": {"css_class": "highlight", "guess_lang": False},
        "toc": {"permalink": False},
    },
)
```

### What each extension does

| Extension | Purpose |
|---|---|
| `fenced_code` | Enables triple-backtick code blocks (` ```python `) |
| `codehilite` | Syntax highlighting via [Pygments](https://pygments.org/) |
| `tables` | Pipe-delimited tables (`| col | col |`) |
| `toc` | Generates a table of contents from headings |
| `meta` | Parses YAML-like metadata at the top of documents |
| `sane_lists` | Prevents mixing ordered/unordered list items |

### Extension configs

- **`css_class: "highlight"`** — wraps code blocks in `<div class="highlight">` so CSS can target them
- **`guess_lang: False`** — don't try to auto-detect the language of code blocks (only highlight when explicitly specified)
- **`permalink: False`** — don't add anchor links to headings (Hypervisor handles navigation differently)

## The `render_markdown()` Function

```python
def render_markdown(md_text, source_path=""):
    MD.reset()
    html = MD.convert(md_text)
    toc_html = getattr(MD, 'toc', '')
    html = post_process(html, source_path)
    return html, toc_html
```

### Why `MD.reset()`?

The markdown library is stateful — it accumulates data between conversions (like TOC entries). Calling `.reset()` before each document ensures clean state.

### The return values

- **`html`** — the rendered HTML content (after post-processing)
- **`toc_html`** — a nested `<ul>` of headings, used for the floating table of contents sidebar

## From Markdown to HTML

Here's what the library does with your markdown:

### Headings

```markdown
## Section Title
```
becomes:
```html
<h2>Section Title</h2>
```

### Code blocks

````markdown
```python
def hello():
    print("world")
```
````
becomes:
```html
<div class="highlight"><pre><span class="k">def</span> <span class="nf">hello</span><span class="p">():</span>
    <span class="nb">print</span><span class="p">(</span><span class="s2">"world"</span><span class="p">)</span></pre></div>
```

The `<span>` elements with classes like `k` (keyword), `nf` (function name), `s2` (string) are added by Pygments for syntax highlighting. CSS then colors them.

### Tables

```markdown
| Name | Value |
|------|-------|
| foo  | 42    |
```
becomes:
```html
<table>
  <thead><tr><th>Name</th><th>Value</th></tr></thead>
  <tbody><tr><td>foo</td><td>42</td></tr></tbody>
</table>
```

### Links

```markdown
[Link text](path/to/file.md)
```
becomes:
```html
<a href="path/to/file.md">Link text</a>
```

Note: at this stage the link still points to `.md`. The post-processing step rewrites it to point to the generated HTML.

## Pygments: Syntax Highlighting

[Pygments](https://pygments.org/) is a Python library that understands the syntax of hundreds of programming languages. When you write a fenced code block with a language tag:

````markdown
```javascript
const x = 42;
```
````

Pygments parses the code and wraps each token in a `<span>` with a class indicating its type:
- `.k` — keyword (`const`, `if`, `return`)
- `.nf` — function name
- `.s2` — double-quoted string
- `.mi` — integer
- `.c1` — single-line comment

Hypervisor's CSS (`04-content.css`) then assigns colors to each class. This is how code blocks get colored without any JavaScript.

## The Rendering Pipeline

```
Markdown text
    ↓ markdown.convert()
Raw HTML (basic structure, syntax-highlighted code)
    ↓ post_process()
Final HTML (sections wrapped, links fixed, labels added, tasks styled)
    ↓ build_page()
Complete HTML page (template, topbar, search, footer)
```

The post-processing step is covered in the next topic.

## Reference Links

- [Python-Markdown documentation](https://python-markdown.github.io/) — the library's full docs
- [Python-Markdown extensions](https://python-markdown.github.io/extensions/) — all built-in extensions
- [Pygments](https://pygments.org/) — the syntax highlighting engine
- [Pygments token types](https://pygments.org/docs/tokens/) — what each CSS class means
- [Markdown syntax reference](https://daringfireball.net/projects/markdown/syntax) — the original spec

## Next

→ [Post-Processing](../05-post-processing/index.html) — the transforms that turn raw HTML into polished output
