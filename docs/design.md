# HV-DESIGN

Visual style, color system, and interaction patterns for the Hypervisor site.

- Created: 2026-04-22T00:00
- Updated: 2026-04-22T00:00

## Visual Style

Brutalist terminal aesthetic:
- **Font**: Departure Mono (CDN), falling back to JetBrains Mono → Cascadia Code → Fira Code → Courier New → monospace
- **Background**: Pure black (`#000000`)
- **No border-radius** anywhere
- **Monospace everything**
- **Icons**: Lucide icons loaded from CDN (`lucide@0.468.0`)

## Color System

- **Accent** (`#00ff41` default) — user-configurable, drives `--accent`, `--accent-dim`, `--accent-glow`, `--accent-border`
- **Warm** (`#ffb000` default) — H3 headings, table headers, syntax keywords. CSS var: `--warm`
- **Cool** (`#00cccc` default) — H4 headings, function names in syntax highlighting. CSS var: `--cool`
- **Comp** (`#ff3333` default) — available for emphasis. CSS var: `--comp`
- **Text hierarchy**: `--text-bright` > `--text` > `--text-muted` > `--text-dim`

When adding new elements, use existing CSS variables. Do not introduce new colors.

## Palette Harmony Modes

The accent color picker includes a mode button that cycles through five color harmony algorithms. Each mode generates four swatches (accent, warm, cool, comp) that drive `--accent`, `--warm`, `--cool`, and `--comp` across the entire site.

| Mode | Label | Hue Logic |
|------|-------|-----------|
| Split-complementary | `SPL` | ±150° / 210° from accent |
| Triadic | `TRI` | 120° intervals |
| Analogous | `ANA` | +30° / +60° / -30° — tight, cohesive cluster |
| Tetradic (square) | `SQR` | 90° intervals — four evenly spaced |
| Complementary | `CMP` | 180° + saturation/lightness shifts |

Accent color persists in `localStorage` under `hypervisor-accent`. Palette mode persists under `hypervisor-palette-mode`.

## Component-Feel Polish (Pure CSS/JS)

The site simulates a component library experience without any framework:

- **Cards**: staggered fade-in animation, hover lift + shadow, accent bottom-line sweep
- **Top bar**: glass blur effect (`backdrop-filter`), scroll shadow
- **Search dropdown**: animated slide-in, results indent on hover
- **Code blocks**: language label badge, copy-to-clipboard button on hover
- **Section panels**: left accent border highlights on hover
- **Scroll-to-top**: slides into view, lifts on hover
- **Page load**: fade + slide-up animation
- **Focus rings**: green outline for keyboard accessibility
- **Terminal glitch**: periodic random text scramble using box-drawing/block unicode glyphs
- **Brand hover**: palette color cycling on the header icon and text
- **Width toggle**: switches between full-width and condensed (1280px) reading mode, persisted to `localStorage`. In condensed mode with TOC, uses flex layout so the TOC sits beside content without overlapping.
- **Related section grouping**: categorized items (Model, Component, API, Backend, etc.) are grouped under sub-headers with path/description split layout