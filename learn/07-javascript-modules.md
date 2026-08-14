# JavaScript Modules

How Hypervisor's interactivity works — per-file IIFEs, per-module `<script>` loading, and cross-file state via `window.*`.

---

## The Module System

JavaScript is organized into four subdirectories inside `assets/js/`, plus a fifth source that lives outside Hypervisor entirely: `.hyperspace/.hyperkit/js/` (WI-142). Hyperkit supplies four ecosystem modules — `HvNoiseField`, `HvGreeting`, `HvCursorTrail`, `HvToast` — shared byte-for-byte with Hyperagent. The build copies them into `site/js/kit/` and loads them **before** everything below; app code assumes `window.HvNoiseField` etc. already exist by the time `core/00-core.js` runs.

```
.hyperspace/.hyperkit/js/    ← Loads first, before core/ — see below
├── noise-field.js            ← window.HvNoiseField
├── greeting.js                ← window.HvGreeting
├── cursor-trail.js           ← window.HvCursorTrail
└── toast.js                  ← window.HvToast + window.__hypervisorToast

assets/js/
├── core/                    ← Foundation (loads first among local modules, order matters)
│   ├── 00-core.js           ← Bridge, preferences, DOM refs (HvToast itself now lives in Hyperkit)
│   ├── 01-router.js         ← SPA shell + route transitions
│   ├── navigation.js        ← Search, menus, code copy
│   ├── theme.js              ← Accent color + palette modes
│   └── toc.js                ← Table of contents sidebar
│
├── features/                ← Self-contained features (order-independent within dir)
│   ├── actions-drawer.js
│   ├── command-palette.js
│   ├── content.js           ← Content interactions (copy, zoom)
│   ├── drop-import.js
│   ├── editor.js
│   ├── effects.js           ← Glitch, footer clock, cursor-box, cursor trail
│   ├── home-anchor.js       ← Homepage noise-field + greeting mount
│   ├── ideas-dismiss.js
│   ├── live-reload.js       ← Poll _build.json for rebuilds
│   ├── pins.js              ← Pinboard pin management
│   ├── scratch.js           ← Scratch pad
│   ├── shortcuts.js         ← Keyboard shortcuts overlay
│   ├── splash.js            ← Boot splash screen
│   ├── tabs.js              ← Tab bar
│   ├── writeback.js         ← Task/status writeback
│   └── zz-accessibility.js  ← A11y panel (loads last within features/)
│
├── webgl/                   ← WebGL2 integration layer
│   └── 00-hypergl.js        ← Shared HyperGL factory (ping-pong FBOs, transform feedback)
│
└── screensaver/             ← Screensaver engine + modes
    ├── 00-engine-head.js    ← DOM/state setup, promotes window.__ss + window.ss*
    ├── bounce.js            ← Mode: bouncing text
    ├── dither.js            ← Mode: 2D dithered gradients
    ├── gl-dither.js         ← Mode: WebGL dither (GPU)
    ├── gl-noise.js          ← Mode: WebGL FBM noise
    ├── gl-particles.js      ← Mode: WebGL fluid particles
    ├── gl-contour.js        ← Mode: WebGL topographic isolines
    ├── orbits.js            ← Mode: great-circle arc sphere (2D)
    ├── cubefold.js          ← Mode: wireframe cube <-> hex star (2D)
    ├── grid.js              ← Mode: perspective grid
    ├── life.js              ← Mode: Conway's Game of Life
    ├── particles.js         ← Mode: 2D SPH fluid
    ├── starfield.js         ← Mode: starfield fly-through
    ├── worm.js              ← Mode: wandering worms
    └── zz-engine-tail.js    ← API, activation, keydown handlers
```

**Load order** (from `site_utils/config.py`): Hyperkit's 4 modules → `core/` → `features/` (non-`zz-*`) → `webgl/` → `screensaver/` (non-`zz-*`) → `screensaver/zz-*` → `features/zz-*`. Within each local group, files sort alphabetically with `zz-*` last. Hyperkit modules load in a fixed order (noise-field, greeting, cursor-trail, toast) ahead of everything else — no alphabetical sort applies to them.

**Naming conventions:**
- `00-` prefix — must load first in its directory
- `zz-` prefix — must load last in its directory
- No prefix — order-independent, sorts alphabetically

## Per-Module `<script>` Loading

Every JS module is emitted as its own `<script defer>` tag in the page HTML:

```html
<script src="/js/core/00-core.js" defer></script>
<script src="/js/core/01-router.js" defer></script>
<script src="/js/core/navigation.js" defer></script>
...
<script src="/js/screensaver/zz-engine-tail.js" defer></script>
```

`defer` guarantees execution order (top-to-bottom, after HTML is parsed) while allowing parallel download.

**Why per-module `<script>` instead of one concatenated bundle?** Parse-error isolation. A syntax error in any one module fails only that module's `<script>` block — every other module still parses and runs. Under a single bundled `app.js`, one broken module kills the entire application.

The build also emits a concatenated `site/app.js` as a backward-compat fallback for utility pages that want a single-file include, but the main pages use per-module scripts.

## Per-File IIFE Pattern

Each module wraps its top-level code in a self-contained IIFE:

```javascript
/* === Hypervisor: Foo === */
(function () {
  "use strict";

  var localVar = "private to this file";
  function helper() { /* ... */ }

  // ... module body ...
})();
```

**What this gives us:**
- No global pollution — locals stay local
- No cross-file collisions on common names like `canvas`, `ctx`, `state`
- Strict mode per file, no leakage
- Runtime error containment — a throw inside one IIFE stops that IIFE, not others

### Cross-file symbols go on `window.*`

Because each file has its own closure, modules can't see each other's locals. When a symbol needs to be visible across files, promote it to `window.*`:

```javascript
// core/00-core.js
(function () {
  "use strict";
  window.savePreference = function (key, value) {
    try { localStorage.setItem(key, value); } catch (e) {}
    if (window.isDesktopApp && window.pywebview) {
      window.pywebview.api.save_preference(key, value);
    }
  };
})();
```

```javascript
// features/pins.js
(function () {
  "use strict";
  // Bare `savePreference` resolves through the global object.
  savePreference("hypervisor-pins", JSON.stringify(pins));
})();
```

**Convention**: bare `window.savePreference`, `window.isDesktopApp`, `window.paletteMode` etc. for utilities; `window.HvNoiseField`, `window.HvGreeting`, `window.HvCursorTrail`, `window.HvToast` for larger public-API objects that ship as ecosystem modules. Post-WI-142, these four live in `.hyperspace/.hyperkit/js/` (not app-local `assets/js/`) and load before every local module.

**Reads via bare identifier** — safe. `savePreference(...)` in a strict-mode IIFE resolves through the global scope to `window.savePreference`.

**Writes via bare identifier** — unsafe. In strict mode, `foo = 5` without prior declaration throws `ReferenceError`. Always assign via `window.foo = 5` when updating cross-file state.

## The File-Sort Trap

Within a subdirectory, files load in alphabetical order (with `zz-*` last). Two hazards to avoid:

**1. Cross-file dependencies must respect sort order.** If `features/foo.js` calls `bar()` defined in `features/init-bar.js`, that only works if `foo.js` sorts *after* `init-bar.js`. Renaming can silently reorder execution. Prefer `window.*` promotion for anything called across files — bare `bar` succeeds regardless of load order as long as `init-bar.js` runs first, and even that constraint disappears with `defer` script tags because `bar` is set by the time other scripts execute.

**2. The `zz-` tail matters.** `features/zz-accessibility.js` runs last in `features/` intentionally — it depends on DOM shapes that earlier modules set up (accent picker, palette buttons, dropdown panels). If you add a new file that names itself `zz-something-else.js`, be aware that alphabetical ordering among `zz-*` files still applies (`zz-accessibility.js` < `zz-something-else.js`).

## The Screensaver's Cross-File State Namespace

The screensaver directory has enough shared state that it uses a dedicated namespace object. `00-engine-head.js` builds the overlay + state and promotes everything to `window`:

```javascript
// screensaver/00-engine-head.js
(function () {
  "use strict";
  var overlay = document.createElement("div");
  overlay.className = "screensaver-overlay";
  // ... build canvas, ctx, helpers ...

  // Stable refs + helpers
  window.ssCanvas = canvas;
  window.ssCtx = ctx;
  window.ssModes = {};
  window.ssGetAccent = getAccentColor;
  window.ssHexToRgba = hexToRgba;
  // ...

  // Mutable config primitives (readers must see updates)
  window.__ss = {
    currentMode: "particles",
    ditherPattern: "trig",
    isActive: false,
    overlay: overlay,
    canvas: canvas,
    // ... plus all the localStorage keys
  };
})();
```

Mode files each self-wrap and reference the namespace:

```javascript
// screensaver/particles.js
(function () {
  "use strict";
  function particleDraw() {
    var w = ssCanvas.width;              // bare read → window.ssCanvas
    ssCtx.fillStyle = ssGetAccent();     // same
    // ...
  }
  ssModes.particles = { init: particleInit, draw: particleDraw, resize: particleResize };
  window.ssParticleState = particleState;  // explicit write — cross-file
})();
```

`zz-engine-tail.js` registers the API and event handlers, reading and writing via `window.__ss` for mutable primitives:

```javascript
// screensaver/zz-engine-tail.js
(function () {
  "use strict";
  var $ = window.__ss;
  document.addEventListener("keydown", function (e) {
    if (e.key === "s" && document.activeElement.tagName !== "INPUT") {
      // ...activate...
      $.isActive = true;
      window.ssCtx.fillRect(0, 0, window.ssCanvas.width, window.ssCanvas.height);
      window.ssModes[$.currentMode].init();
    }
  });
})();
```

**Why this pattern for screensaver but not everywhere?** The screensaver has ~20 shared symbols across 12 files that all need to touch the same overlay + canvas + mode registry. A namespace object keeps that visible in one place. Most features share only a handful of symbols — `window.savePreference`, `window.HvToast` — and don't need a namespace.

## Module: core/00-core.js (+ Hyperkit's toast.js)

`core/00-core.js` sets up the foundation:

### PyWebView Bridge

```javascript
window.isDesktopApp = false;   // flipped to true by the pywebviewready event
```

Desktop-only features (write-back, file explorer button) check `window.isDesktopApp`.

### Preferences

```javascript
window.savePreference = function (key, value) {
  try { localStorage.setItem(key, value); } catch (e) {}
  if (window.isDesktopApp && window.pywebview && window.pywebview.api) {
    window.pywebview.api.save_preference(key, value);
  }
};
```

Preferences persist to `localStorage` (browser-mode cache) and, in desktop mode, to `preferences.json` via the PyWebView bridge. The JSON file is the source of truth.

### Toast Notifications

`window.HvToast.show({ variant, title, message, icon, duration, action, dedupeKey })`. Variants map to accent/cool/warm/comp rails (see `00-primitives.css`). Legacy string form (`HvToast.show('Copied')`) still works. Defined in `.hyperspace/.hyperkit/js/toast.js` (WI-142) — shared verbatim with Hyperagent, loaded before this file.

## Module: core/navigation.js — Client-Side Search

The search index is fetched once at load and filtered in memory:

```javascript
(function () {
  "use strict";
  var searchInput = document.getElementById("search");
  var index = [];
  fetch("/search-index.json").then(function (res) { return res.json(); }).then(function (data) {
    index = data;
  });

  searchInput.addEventListener("input", function () {
    var query = this.value.toLowerCase();
    var results = index.filter(function (doc) {
      return doc.title.toLowerCase().includes(query)
          || doc.tags.some(function (t) { return t.includes(query); });
    });
    renderResults(results);
  });
})();
```

No server needed — the entire index is in memory. Fast for hundreds of documents.

## Module: core/theme.js — Accent Color

The color picker updates CSS custom properties in real time:

```javascript
window.applyAccent = function (hex) {
  var root = document.documentElement.style;
  root.setProperty("--accent", hex);
  root.setProperty("--accent-dim", hex + "26");      // 15% opacity
  root.setProperty("--accent-glow", hex + "4d");     // 30% opacity
  root.setProperty("--accent-border", hex + "66");   // 40% opacity
  window.savePreference("hypervisor-accent", hex);
};
```

`applyAccent`, `applyGradientMap`, `populatePresetSelect`, `updateModeButton`, `updatePresetSelector`, `hexToRgb`, `colorPicker`, and `paletteMode` are all promoted to `window` so other modules (screensaver GL modes, the a11y panel) can read them.

## Module: features/live-reload.js

Polls `_build.json` every 2 seconds:

```javascript
(function () {
  "use strict";
  var currentBuildId = document.querySelector('meta[name="build-id"]').content;
  setInterval(function () {
    fetch(rootPrefix + "_build.json")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.buildId !== currentBuildId) location.reload();
      })
      .catch(function () {});  // silently ignore fetch errors (file:// mode)
  }, 2000);
})();
```

When the build ID changes, the page reloads. No WebSocket needed.

## Key Patterns

### Event Delegation

Instead of a listener per element, one listener on the parent:

```javascript
document.querySelector(".card-grid").addEventListener("click", function (e) {
  var card = e.target.closest(".card");
  if (card) handler(card);
});
```

### Feature Detection

```javascript
if (navigator.clipboard) { /* modern API */ } else { /* legacy fallback */ }
```

### Deferred vs. inline `<script>`

All Hypervisor modules use `defer`. That means (a) they load in parallel with parsing, (b) they execute in document order after DOM is ready. No need for a `DOMContentLoaded` wrapper.

## Reference Links

- [IIFE (MDN)](https://developer.mozilla.org/en-US/docs/Glossary/IIFE) — the pattern explained
- [defer attribute (MDN)](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/script#defer) — how deferred script loading works
- [strict mode (MDN)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Strict_mode) — what `"use strict"` enforces
- [globalThis / window (MDN)](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/globalThis) — the global object
- [DOM manipulation (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Document_Object_Model)
- [Clipboard API (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Clipboard_API)
- [localStorage (MDN)](https://developer.mozilla.org/en-US/docs/Web/API/Window/localStorage)

## Next

→ [The Desktop App](../08-desktop-app/index.html) — PyWebView, file watching, and write-back
