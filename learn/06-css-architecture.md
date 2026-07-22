# CSS Architecture

How Hypervisor's styling is organized — modular files, CSS custom properties, and the concatenation pipeline.

---

## The Modular Approach

Instead of one massive CSS file, Hypervisor splits styles into numbered modules:

```
assets/css/
├── 00-primitives.css        ← Ecosystem primitive classes (hv-chip, hv-row, hv-button, etc.)
├── 00-variables.css         ← Custom properties, tokens, resets, base classes
├── 01-layout.css            ← Page structure, topbar, footer
├── 02-search.css            ← Search input and results
├── 03-menus.css             ← Dropdown menus, accent picker
├── 04-content.css           ← Markdown body, code blocks, tables
├── 05-cards.css             ← Card grid, document lists
├── 06-pinboard.css          ← Pin cards, pin button, pinboard page
├── 07-toc.css               ← Table of contents sidebar
├── 08-utilities.css         ← Utility page styles
├── 09-effects.css           ← Animations, cursor effects, toast system
└── zz-accessibility.css     ← A11y overrides (always loads last)
```

Both `00-*` files load before all numbered specifics. Load order between them (alphabetical: `00-primitives.css` before `00-variables.css`) doesn't matter for token resolution — CSS custom properties are resolved after all rules are parsed.

During build, numbered files are **concatenated in sorted order**, then `zz-*` files are appended last:

```python
css_parts = []
for css_file in sorted(CSS_DIR.glob("*.css")):
    if css_file.name.startswith("zz-"):
        continue
    css_parts.append(css_file.read_text(encoding="utf-8"))
for css_file in sorted(CSS_DIR.glob("zz-*.css")):
    css_parts.append(css_file.read_text(encoding="utf-8"))
(OUTPUT_DIR / "style.css").write_text("\n".join(css_parts), encoding="utf-8")
```

### Why numbered prefixes?

CSS is order-dependent — later rules override earlier ones. The numeric prefixes (`00-`, `01-`, ...) guarantee a consistent load order. Variables must come first (so other files can reference them), and accessibility overrides come last (so they can override anything). The `zz-` prefix convention ensures a file always sorts after all numbered files regardless of what numbers are in use.

### Why concatenation instead of `@import`?

- **One HTTP request** — the browser loads a single file instead of 10
- **No build tools** — no webpack, no PostCSS, just Python string joining
- **Works with `file://`** — some browsers restrict `@import` from local files

## CSS Custom Properties (Variables)

The entire color system and spacing is defined as CSS custom properties in `00-variables.css`:

```css
:root {
  /* Colors */
  --bg: #000000;
  --bg-card: #0a0a0a;
  --bg-card-hover: #111111;
  --border: #1a1a1a;
  --border-strong: #2a2a2a;

  /* Text hierarchy */
  --text-bright: #ffffff;
  --text: #d0d0d0;
  --text-muted: #808080;
  --text-dim: #505050;

  /* Accent (dynamic — updated by JS) */
  --accent: #00ff41;
  --accent-dim: rgba(0, 255, 65, 0.15);
  --accent-glow: rgba(0, 255, 65, 0.3);
  --accent-border: rgba(0, 255, 65, 0.4);

  /* Palette colors */
  --warm: #ffb000;
  --cool: #00cccc;
  --comp: #ff0041;
}
```

### Why custom properties?

1. **Single source of truth** — change `--accent` in one place, everything updates
2. **Dynamic theming** — JavaScript can update `--accent` at runtime (the color picker does this)
3. **Readable code** — `color: var(--text-muted)` is clearer than `color: #808080`

### The accent color system

The accent color is user-configurable via the color picker in the topbar. When changed, JavaScript updates the CSS variables:

```javascript
document.documentElement.style.setProperty('--accent', newColor);
document.documentElement.style.setProperty('--accent-dim', `${newColor}26`);
// ... etc
```

This instantly recolors every element that uses `var(--accent)` — no page reload needed.

## Module Responsibilities

### `00-variables.css` — Foundation

Defines all custom properties, resets (`* { box-sizing: border-box }`), and reusable base classes:

- `.hv-badge` — small inline labels
- `.hv-icon-btn` — topbar icon buttons
- `.hv-dropdown` — animated dropdown panels
- `.hv-section` — bordered content sections

These base classes are composed with specific classes in HTML:
```html
<button class="hv-icon-btn ref-menu-btn">...</button>
```

### `01-layout.css` — Page Structure

The overall page layout uses a simple structure:

```css
.page {
  max-width: 100%;      /* or 1280px in condensed mode */
  margin: 0 auto;
  padding: 2rem;
  padding-top: 4rem;    /* space for fixed topbar */
}
```

The topbar is `position: fixed` at the top. The footer is at the bottom of the page content.

### `04-content.css` — Markdown Body

This is the largest module. It styles everything that comes from rendered markdown:

- Headings (H1–H6) with distinct colors and sizes
- Code blocks with dark background and language labels
- Tables with header styling and hover effects
- Blockquotes with left border accent
- Lists, links, images, horizontal rules

### `09-accessibility.css` — Override Layer

Accessibility toggles add classes to `<body>` that override base styles:

```css
body.a11y-high-contrast .markdown-body {
  color: #ffffff;  /* override --text */
}
body.a11y-large-text .markdown-body {
  font-size: 18px;  /* override base 14px */
}
body.a11y-reduce-motion * {
  animation: none !important;
  transition: none !important;
}
```

These come last in the concatenation order so they always win.

## Key CSS Patterns

### The card hover effect

```css
.card {
  transition: transform 0.2s, border-color 0.2s, box-shadow 0.25s;
}
.card:hover {
  transform: translateY(-2px);
  border-color: var(--accent-border);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}
.card::after {
  /* Accent line that sweeps in from the left on hover */
  transform: scaleX(0);
  transition: transform 0.3s;
}
.card:hover::after {
  transform: scaleX(1);
}
```

### Staggered animations

Cards fade in with increasing delays:
```css
.card:nth-child(1) { animation-delay: 0.05s; }
.card:nth-child(2) { animation-delay: 0.1s; }
.card:nth-child(3) { animation-delay: 0.15s; }
```

### The glass topbar

```css
.topbar {
  backdrop-filter: blur(12px);
  background: rgba(0, 0, 0, 0.85);
}
```

`backdrop-filter: blur()` creates the frosted glass effect — content behind the topbar is blurred.

## Adding New Styles

1. Identify which module owns the feature area
2. Add styles to that module
3. If a new module is needed, use the next number (`10-newfeature.css`)
4. Rebuild — the concatenation picks it up automatically

## Reference Links

- [CSS Custom Properties (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties) — the `var()` system
- [CSS Transitions (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_transitions/Using_CSS_transitions) — how hover effects animate
- [backdrop-filter (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/backdrop-filter) — the glass blur effect
- [CSS Specificity (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/Specificity) — why order and selectors matter

## Next

→ [JavaScript Modules](../07-javascript-modules/index.html) — how interactivity is structured
