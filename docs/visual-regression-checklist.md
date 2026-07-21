# Hypervisor Visual Regression Checklist

Surface-by-surface pre/post comparison for the [Hypervisor Aesthetic Refresh (WI-112)](../../work/to-do/hypervisor-aesthetic-refresh.md). Each surface enumerated below is the Hypervisor-owned slice of the [WI-111](../../work/to-do/hyper-ecosystem-aesthetic-refresh.md) expanded verification list.

- Created: 2026-07-21T08:51
- Updated: 2026-07-21T08:51

---

## How to Use

1. **Baseline pass** — before Phase 1 begins, capture a screenshot of every surface in every listed state and save to `.hypervisor/docs/screenshots/baseline-pre-refresh/` using the filename convention `{surface-slug}--{state}.png`.
2. **Refresh pass** — after Phase 9 completes, capture a matching screenshot for every row and save to `.hypervisor/docs/screenshots/refresh-post/`.
3. **Compare** — for each row, tick the checkbox and note any intentional visual delta in the Notes column. Unintentional deltas open a bugfix before this WI closes.

Screenshot resolution: capture at the app's default window size (do not resize between pre and post). Include the topbar and page chrome so surrounding context is comparable.

---

## Filename Convention

`{surface-slug}--{state}.png`

- `surface-slug` — kebab-case, matches the row's slug column
- `state` — one of `rest`, `hover`, `focus`, `active`, `open` (as applicable)

Example: `homepage-pulse-row--hover.png`, `accent-picker--open.png`.

---

## Surface Checklist

### Homepage

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `homepage-hero` | Hero tagline (flag style) | rest | [ ] | [ ] | |
| `homepage-pulse-active` | Workspace Pulse — active row | rest, hover | [ ] | [ ] | |
| `homepage-pulse-recent` | Workspace Pulse — recent stream row | rest, hover | [ ] | [ ] | |
| `homepage-pinned` | Pinned dock cards | rest, hover | [ ] | [ ] | |
| `homepage-noise-field` | Bayer-dither noise field background | rest | [ ] | [ ] | |
| `homepage-emote` | Kaomoji greeting | rest | [ ] | [ ] | |

### Doc Pages

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `doc-header` | Doc header (title, description, metadata chips) | rest | [ ] | [ ] | |
| `doc-header-chips` | Work ID + Status + Project + Tag chips | rest, hover | [ ] | [ ] | |
| `doc-body-h1` | H1 heading style | rest | [ ] | [ ] | |
| `doc-body-h2` | H2 section panel wrapper | rest, hover | [ ] | [ ] | |
| `doc-body-h3` | H3 heading (amber) | rest | [ ] | [ ] | |
| `doc-body-h4` | H4 heading (cyan) | rest | [ ] | [ ] | |
| `doc-body-code` | Code block with language label + copy button | rest, hover | [ ] | [ ] | |
| `doc-body-table` | Markdown table with cell copy affordance | rest, hover | [ ] | [ ] | |
| `doc-body-callout` | GitHub-flavored callouts (NOTE, WARNING, TIP) | rest | [ ] | [ ] | |
| `doc-body-tasklist` | Task list checkboxes | rest, hover | [ ] | [ ] | |
| `doc-body-related` | Related section (category grouping) | rest, hover | [ ] | [ ] | |
| `doc-toc` | Floating TOC sidebar | rest, hover-active | [ ] | [ ] | |
| `doc-breadcrumb` | Breadcrumb trail | rest, hover | [ ] | [ ] | |
| `doc-metadata-block` | Metadata block after H1 | rest | [ ] | [ ] | |

### Directory Index Pages

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `dirindex-header` | Directory index header + description | rest | [ ] | [ ] | |
| `dirindex-subcat-cards` | Subcategory card grid | rest, hover | [ ] | [ ] | |
| `dirindex-doclist` | Doc list rows | rest, hover, recent-indicator | [ ] | [ ] | |
| `dirindex-work-todo` | work/to-do listing (with WI ID + status chips) | rest, hover | [ ] | [ ] | |
| `dirindex-work-done` | work/done listing | rest, hover | [ ] | [ ] | |

### Pinboard

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `pinboard-empty` | Pinboard empty state | rest | [ ] | [ ] | |
| `pinboard-card` | Pin card | rest, hover | [ ] | [ ] | |
| `pinboard-add-btn` | Pin button on doc pages | rest, hover, pinned | [ ] | [ ] | |
| `pinboard-badges` | Pin type badges | rest | [ ] | [ ] | |

### Topbar & Navigation

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `topbar-rest` | Topbar at rest | rest | [ ] | [ ] | |
| `topbar-scrolled` | Topbar with scroll shadow | scrolled | [ ] | [ ] | |
| `topbar-brand` | Brand mark with hover effect | rest, hover | [ ] | [ ] | |
| `topbar-nav-rail` | Site nav rail items | rest, hover, active, recent-indicator | [ ] | [ ] | |
| `topbar-search` | Search input | rest, focus | [ ] | [ ] | |

### Dropdowns

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `search-results` | Search results dropdown | open, hover-row | [ ] | [ ] | |
| `search-tag-filter` | Tag filter indicator | rest | [ ] | [ ] | |
| `accent-picker` | Accent color picker | open, hover-swatch | [ ] | [ ] | |
| `ref-menu` | Reference menu dropdown | open, hover-item | [ ] | [ ] | |
| `util-menu` | Utilities menu dropdown | open, hover-item | [ ] | [ ] | |
| `width-toggle` | Condensed width toggle | rest, active | [ ] | [ ] | |

### Panels & Overlays

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `a11y-panel` | Accessibility panel | open | [ ] | [ ] | |
| `a11y-toggles` | Accessibility toggles | rest, on/off | [ ] | [ ] | |
| `shortcuts-overlay` | Keyboard shortcuts overlay | open | [ ] | [ ] | |
| `confirm-dialog` | Confirm dialog (hv-confirm-overlay) | open | [ ] | [ ] | |
| `toast` | Toast notification | visible | [ ] | [ ] | |

### Footer & Overlays

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `footer-clock` | Footer clock | rest | [ ] | [ ] | |
| `scroll-to-top` | Scroll-to-top button | visible, hover | [ ] | [ ] | |
| `cursor-companion` | Cursor companion box | rest, blink | [ ] | [ ] | |

### Screensaver Modes

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `screensaver-particles` | SPH fluid particles | active | [ ] | [ ] | |
| `screensaver-starfield` | Starfield fly-through | active | [ ] | [ ] | |
| `screensaver-worm` | Wandering worm | active | [ ] | [ ] | |
| `screensaver-dither` | Bayer-dithered morphing gradients | active | [ ] | [ ] | |
| `screensaver-bounce` | Bouncing text | active | [ ] | [ ] | |
| `screensaver-life` | Conway's Game of Life | active | [ ] | [ ] | |

### Utility Pages

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `util-password-gen` | Password generator | rest, generated | [ ] | [ ] | |
| `util-palette-gen` | Palette generator | rest, hover-swatch | [ ] | [ ] | |
| `util-log-viewer` | Log viewer | rest | [ ] | [ ] | |
| `util-health-dashboard` | Health dashboard | rest | [ ] | [ ] | |
| `util-ado-dashboard` | ADO dashboard | rest | [ ] | [ ] | |
| `util-regex-editor` | Regex editor | rest | [ ] | [ ] | |
| `util-assessment` | Assessment engine | rest, mid-question | [ ] | [ ] | |

### Fallback / Error

| Slug | Surface | States | Baseline | Refresh | Notes |
|------|---------|--------|----------|---------|-------|
| `fallback-404` | 404 / missing page | rest | [ ] | [ ] | |

---

## Accessibility Toggle States

Capture the following surfaces with **each** a11y toggle applied to verify parity:

| Surface | High Contrast | Reduced Motion | Hide Indicators | System Cursors |
|---------|:-------------:|:--------------:|:---------------:|:--------------:|
| Homepage Pulse row | [ ] | [ ] | [ ] | [ ] |
| Doc header chips | [ ] | [ ] | [ ] | [ ] |
| Nav rail with recent-indicator | [ ] | [ ] | [ ] | [ ] |
| Card hover | [ ] | [ ] | [ ] | [ ] |
| Focus outline on primary button | [ ] | [ ] | [ ] | [ ] |

---

## Accent Color Cascade

Verify accent cascade on the following surfaces using at least three distinct accent hues (terminal green default, warm hue e.g. `#ffb000`, cool hue e.g. `#00cccc`):

- [ ] Chip variants (filled, outlined-accent, outlined-muted)
- [ ] Row hover accent-line sweep
- [ ] Focus outlines
- [ ] Selection background
- [ ] Scrollbar thumb hover
- [ ] Cursor SVG stroke color
- [ ] Search input focus border
- [ ] TOC active heading
- [ ] Screensaver primary color

---

## Sign-off

- [ ] Baseline pass complete — all screenshots captured to `screenshots/baseline-pre-refresh/`
- [ ] Refresh pass complete — all screenshots captured to `screenshots/refresh-post/`
- [ ] All rows compared, unintentional deltas resolved
- [ ] Accent cascade verified on every listed surface
- [ ] Accessibility toggle grid verified
