# Design Decisions

Why Hypervisor is built the way it is — the reasoning behind key architectural choices.

---

## No Frontend Framework

**Decision:** Vanilla HTML + CSS + JavaScript. No React, Vue, Svelte, or any framework.

**Why:**

1. **Zero build tooling** — no webpack, no Vite, no npm. The "build" is Python concatenating files.
2. **Instant comprehension** — view source shows exactly what's running. No transpilation, no virtual DOM, no component tree to trace.
3. **No dependency rot** — frameworks release breaking changes yearly. Vanilla JS from 2020 still works in 2026.
4. **Performance** — no hydration step, no framework runtime. Pages load and become interactive immediately.
5. **Appropriate complexity** — Hypervisor's interactivity is modest (search, dropdowns, toggles). A framework would add 50KB+ of runtime for problems that don't exist here.

**Trade-off:** More verbose DOM manipulation code. No component reuse pattern. But for a tool this size, that's fine.

## No CSS Framework

**Decision:** Custom CSS from scratch. No Tailwind, Bootstrap, or utility framework.

**Why:**

1. **Total visual control** — the brutalist terminal aesthetic doesn't map to any framework's defaults
2. **Smaller output** — `style.css` is ~15KB. Tailwind's purged output would be similar but with less readable source.
3. **Custom properties as the system** — CSS variables provide theming without a framework's abstraction layer
4. **Learning value** — writing CSS teaches CSS. A utility framework teaches the framework.

## Static Generation Over SPA

**Decision:** Pre-render all pages as static HTML. No client-side routing.

**Why:**

1. **`file://` compatibility** — SPAs need a server for routing. Static files work from the filesystem.
2. **Instant page loads** — no JavaScript execution needed to see content
3. **SEO-irrelevant** — this is a personal tool, not a public website
4. **Simplicity** — each page is self-contained. No shared state between pages (except localStorage).

**Trade-off:** Page transitions aren't smooth (full reload). But with local files, reloads are near-instant anyway.

## Hub-and-Spoke Navigation (No Sidebar)

**Decision:** Site nav rail (in the topbar) is the always-available spoke into every top-level category; the homepage is reserved for status (Pulse + Pinned), not category navigation. No persistent sidebar or tree view.

**Why:**

1. **Content-first** — the document gets the full viewport width
2. **Scales cleanly** — a sidebar with 130+ documents would be overwhelming
3. **Search handles fast access** — press `/`, type a few characters, hit Enter
4. **Fewer decisions** — no "should this be expanded or collapsed?" state to manage

**Trade-off:** Navigating between sibling documents requires going back to the index. The breadcrumb and search mitigate this.

## SQLite-Free (Pure Filesystem)

**Decision:** No database. The filesystem IS the data store. The search index is rebuilt on every build.

**Why:**

1. **Your files are the source of truth** — not a database that could get out of sync
2. **Git-friendly** — markdown files diff cleanly, merge cleanly, have history
3. **Tool-agnostic** — your content works without Hypervisor. It's just a folder of `.md` files.
4. **Rebuild is cheap** — scanning 130 files takes <1 second. No need to cache.

**Trade-off:** No persistent state between builds (play counts, last-viewed, etc.). The desktop app uses `preferences.json` for the few things that need persistence.

## Concatenation Over Bundling

**Decision:** CSS and JS modules are concatenated with Python, not bundled with webpack/rollup.

**Why:**

1. **No Node.js dependency** — the entire toolchain is Python
2. **Transparent** — `sorted(glob("*.css"))` is the entire "build config"
3. **Debuggable** — the output is readable (not minified, not tree-shaken)
4. **Fast** — string concatenation is instant. No AST parsing, no dependency resolution.

**Trade-off:** No tree-shaking, no minification, no source maps. For a personal tool with <20KB of CSS and <30KB of JS, these don't matter.

## IIFE Over ES Modules

**Decision:** All JS in one IIFE closure, not ES module `import`/`export`.

**Why:**

1. **`file://` compatibility** — ES modules require a server (`type="module"` scripts can't load from `file://` in some browsers)
2. **Single file output** — one `<script>` tag, one HTTP request
3. **Shared scope is a feature** — modules can reference each other's variables without explicit imports
4. **No bundler needed** — ES modules in production typically need rollup/webpack to bundle anyway

**Trade-off:** All code shares one scope (potential naming collisions). Mitigated by the IIFE keeping everything private from the global scope, and by using descriptive variable names.

## Embedded Search Index

**Decision:** The search index is a JSON blob in every page, not a separate fetch.

**Why:**

1. **`file://` compatibility** — `fetch()` doesn't work reliably with local files in all browsers
2. **Instant search** — no network request, no loading state
3. **Offline by default** — works without any server

**Trade-off:** Every page is slightly larger (~50KB of embedded JSON for 130 docs). Acceptable for a local tool.

## PyWebView Over Electron

**Decision:** PyWebView for the desktop wrapper, not Electron.

**Why:**

1. **Python-native** — the backend is already Python. No need to bridge to Node.js.
2. **Tiny** — PyWebView is a pip package. Electron bundles an entire Chromium browser (~100MB).
3. **System web engine** — uses Edge WebView2 (Windows) or WebKit (macOS). Always up to date.
4. **Simple API** — `create_window()`, `evaluate_js()`, `js_api`. That's most of what you need.

**Trade-off:** Less control over the rendering engine. Can't guarantee exact browser behavior across platforms. But for a personal tool on one machine, this doesn't matter.

## Monospace Everything

**Decision:** All text — headings, body, code, metadata — uses monospace fonts.

**Why:**

1. **Terminal aesthetic** — the entire visual identity is "developer tool"
2. **Consistency** — no jarring font switches between prose and code
3. **Alignment** — tables, code, and text all align on the same grid
4. **The font IS the design** — Departure Mono's pixel character is the visual identity

**Trade-off:** Monospace is less readable for long prose than proportional fonts. Mitigated by generous line-height and max-width constraints.

## Reference Links

- [The Rule of Least Power](https://www.w3.org/2001/tag/doc/leastPower.html) — W3C principle: use the least powerful language suitable for the task
- [Resilient Web Design](https://resilientwebdesign.com/) — philosophy of building for longevity
- [No Build](https://world.hey.com/dhh/you-can-t-get-faster-than-no-build-step-97ce0c81) — DHH on skipping build tools

## Next

→ [The MCP Server](../10-mcp-server/index.html) — how AI assistants interact with hyperspace programmatically
