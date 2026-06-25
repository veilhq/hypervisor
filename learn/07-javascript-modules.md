# JavaScript Modules

How Hypervisor's interactivity works — the IIFE pattern, module structure, and DOM manipulation.

---

## The Module System

JavaScript is organized into three subdirectories that get concatenated in order:

```
assets/js/
├── core/                    ← Foundation (loads first, order matters)
│   ├── 00-core.js           ← IIFE open, shared utilities, DOM refs
│   ├── navigation.js        ← Search, menus, code copy
│   ├── toc.js               ← Table of contents sidebar
│   └── theme.js             ← Accent color picker
│
├── features/                ← Self-contained features (order-independent)
│   ├── content.js           ← Content interactions (copy, zoom)
│   ├── effects.js           ← Visual effects (glitch, clock)
│   ├── live-reload.js       ← Auto-reload on rebuild
│   ├── pins.js              ← Pinboard pin management
│   ├── shortcuts.js         ← Keyboard shortcuts
│   ├── writeback.js         ← Checkbox/metadata write-back
│   └── zz-accessibility.js  ← A11y panel + IIFE close (must be last)
│
└── screensaver/             ← Screensaver engine + modes
    ├── 00-engine-head.js    ← Engine open, helpers, overlay
    ├── particles.js         ← Mode: fluid particles
    ├── starfield.js         ← Mode: starfield fly-through
    ├── worm.js              ← Mode: wandering worm trails
    ├── dither.js            ← Mode: dithered gradients
    ├── bounce.js            ← Mode: bouncing text
    ├── life.js              ← Mode: Conway's Game of Life
    └── zz-engine-tail.js    ← Engine tail: API, idle timer
```

Build order: `core/` → `features/` → `screensaver/`. Within each directory, files sort alphabetically with `zz-*` files loading last. Concatenated into `site/app.js`.

**Naming conventions:**
- `00-` prefix = must load first in its directory
- `zz-` prefix = must load last in its directory
- No prefix = order-independent, sorts alphabetically

## The IIFE Pattern

All modules are wrapped in a single **Immediately Invoked Function Expression**:

```javascript
// core/00-core.js opens it:
(function() {
"use strict";

// ... all module code lives here ...

// features/zz-accessibility.js closes it:
})();
```

### What is an IIFE?

```javascript
(function() {
  // Everything in here is private
  var secret = "can't be accessed from outside";
})();

// secret is undefined here
```

An IIFE creates a **closure** — a private scope. Variables declared inside can't leak into the global scope or conflict with other scripts on the page.

### Why use it?

- **No global pollution** — all Hypervisor variables are private
- **No conflicts** — won't clash with Lucide, Mermaid, or any other library
- **Shared scope between modules** — since all modules are inside the same IIFE, they can share variables without `export`/`import`

### How modules share data

Because all modules are concatenated inside one IIFE, a variable declared in `core/00-core.js` is accessible in `features/pins.js`:

```javascript
// In core/00-core.js:
var searchInput = document.getElementById('search');

// In core/navigation.js (can use searchInput directly):
searchInput.addEventListener('focus', function() { ... });
```

No import/export needed. Order matters — a module can only reference variables from modules that come before it in the concatenation order (core → features → screensaver).

## Module: core/00-core.js

Sets up the foundation that all other modules depend on:

### PyWebView Bridge

```javascript
var isDesktop = window.pywebview && window.pywebview.api;
```

Detects whether the app is running in PyWebView (desktop) or a regular browser. Desktop-only features (write-back, file explorer button) check this flag.

### Preferences

```javascript
function savePreference(key, value) {
  if (isDesktop) {
    window.pywebview.api.save_preference(key, value);
  }
  localStorage.setItem('hv_' + key, value);
}
```

Preferences are saved to both `localStorage` (for browser mode) and the PyWebView bridge (for desktop mode, which persists to `preferences.json`).

### Shared DOM References

```javascript
var searchInput = document.getElementById('search');
var searchResults = document.getElementById('search-results');
var scrollTopBtn = document.getElementById('scroll-top');
```

Queried once at startup, reused everywhere. Avoids repeated `getElementById` calls.

### Toast Notifications

```javascript
function showToast(message, duration) {
  // Creates a temporary notification element
}
```

A simple notification system used by copy buttons, write-back confirmations, etc.

## Module 01: Navigation & Search

### Client-Side Search

The search index is embedded in every page as JSON:

```html
<script>window.SEARCH_INDEX = [{"title":"...", "path":"...", "tags":["..."], "snippet":"..."}];</script>
```

When you type in the search box, JavaScript filters this array in real-time:

```javascript
searchInput.addEventListener('input', function() {
  var query = this.value.toLowerCase();
  var results = window.SEARCH_INDEX.filter(function(doc) {
    return doc.title.toLowerCase().includes(query)
        || doc.path.toLowerCase().includes(query)
        || doc.tags.some(function(t) { return t.includes(query); });
  });
  renderResults(results);
});
```

No server needed — the entire index is in memory. Fast for hundreds of documents.

### Code Block Copy

```javascript
// For each code block, add a copy button
document.querySelectorAll('.highlight pre').forEach(function(pre) {
  var btn = document.createElement('button');
  btn.textContent = 'copy';
  btn.addEventListener('click', function() {
    navigator.clipboard.writeText(pre.textContent);
    showToast('Copied');
  });
  pre.parentElement.appendChild(btn);
});
```

Uses the [Clipboard API](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API) to copy code block contents.

## Module 03: Theme (Accent Color)

The color picker updates CSS custom properties in real-time:

```javascript
var picker = document.getElementById('accent-color');
picker.addEventListener('input', function() {
  applyAccent(this.value);
});

function applyAccent(hex) {
  var root = document.documentElement.style;
  root.setProperty('--accent', hex);
  root.setProperty('--accent-dim', hex + '26');      // 15% opacity
  root.setProperty('--accent-glow', hex + '4d');     // 30% opacity
  root.setProperty('--accent-border', hex + '66');   // 40% opacity
  savePreference('accent', hex);
}
```

### Color math

The palette mode feature generates complementary colors from the accent. This involves converting hex → HSL, rotating the hue, and converting back:

```javascript
function hexToHsl(hex) {
  // Convert #rrggbb to {h, s, l}
}
function hslToHex(h, s, l) {
  // Convert {h, s, l} back to #rrggbb
}
// Complementary = rotate hue by 180°
var comp = hslToHex((h + 180) % 360, s, l);
```

## Module 07: Live Reload

Polls `_build.json` every 2 seconds to detect new builds:

```javascript
var currentBuildId = document.querySelector('meta[name="build-id"]').content;

setInterval(function() {
  fetch(rootPrefix + '_build.json')
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.buildId !== currentBuildId) {
        location.reload();
      }
    })
    .catch(function() {}); // Ignore fetch errors (file:// mode)
}, 2000);
```

When the build ID changes, the page reloads itself. Simple, no WebSocket needed.

## Key Patterns

### Event Delegation

Instead of attaching listeners to every element:

```javascript
// Bad: listener per card (100 cards = 100 listeners)
document.querySelectorAll('.card').forEach(function(card) {
  card.addEventListener('click', handler);
});

// Good: one listener on the parent
document.querySelector('.card-grid').addEventListener('click', function(e) {
  var card = e.target.closest('.card');
  if (card) handler(card);
});
```

### `DOMContentLoaded` vs inline `<script>`

Hypervisor's `app.js` loads at the bottom of `<body>`, so the DOM is already parsed when it runs. No need for `DOMContentLoaded` wrapper — the elements exist by the time the script executes.

### Feature Detection

```javascript
if (navigator.clipboard) {
  // Use modern clipboard API
} else {
  // Fallback: create a textarea, select, execCommand('copy')
}
```

Always check if an API exists before using it. Not all browsers support everything.

## Reference Links

- [IIFE (MDN)](https://developer.mozilla.org/en-US/docs/Glossary/IIFE) — the pattern explained
- [DOM manipulation (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model) — working with HTML elements in JS
- [addEventListener (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/EventTarget/addEventListener) — how event handling works
- [Clipboard API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API) — copying text programmatically
- [CSS Custom Properties + JS (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties#values_in_javascript) — reading/writing CSS variables from JS
- [localStorage (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage) — persisting data in the browser

## Next

→ [The Desktop App](../08-desktop-app/index.html) — PyWebView, file watching, and write-back
