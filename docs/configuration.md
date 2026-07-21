# HV-CONFIGURATION

Dependencies, build constants, and how to extend Hypervisor.

- Created: 2026-04-22T00:00
- Updated: 2026-04-23T00:00

## Dependencies

- **Python 3.x**
- **markdown** (`pip install markdown`) — markdown-to-HTML conversion with extensions: `fenced_code`, `codehilite`, `tables`, `toc`, `meta`, `sane_lists`
- **pygments** (`pip install pygments`) — syntax highlighting for code blocks

No Node.js, no npm, no build tools.

### CDN Resources

- **Departure Mono** — primary font (loaded via CSS `@font-face` or CDN)
- **Lucide 0.468.0** — icon library (`unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js`)

## Build Constants

Constants live in `site_utils/config.py`:

| Variable | Purpose |
|----------|---------|
| `HYPERSPACE_ROOT` | Auto-detected relative to `config.py`'s location in the package |
| `OUTPUT_DIR` | `.hypervisor/site/` |
| `ASSETS_DIR` | `.hypervisor/assets/` |
| `SKIP_DIRS` | Directories to exclude: `__pycache__`, `site` |
| `SKIP_FILES` | Files to exclude: `.gitkeep` |
| `CATEGORY_LABELS` | Display names for directories (e.g. `.hypervisor` → `HV-META`) |
| `CATEGORY_DESCRIPTIONS` | Descriptions shown on directory index pages and in the nav rail |
| `CATEGORY_ICONS` | Lucide icon names for directory index cards and nav rail entries |

## Extending

### Adding a new category

1. Create the directory in `.hyperspace/` (e.g. `.hyperspace/workflows/`)
2. Add entries in `CATEGORY_LABELS`, `CATEGORY_DESCRIPTIONS`, and `CATEGORY_ICONS`
3. Rebuild

### Changing the accent color

Click the color swatch in the top bar. Choice persists in `localStorage` under key `hypervisor-accent`. Click the mode button to cycle through five palette harmonies (`SPL → TRI → ANA → SQR → CMP`). Mode persists under `hypervisor-palette-mode`.

### Adding new post-processing

Add a function to `site_utils/markdown_processing.py` and call it from `post_process()`. The function receives and returns an HTML string. Insert it in the correct position per the pipeline order documented in `architecture.md`.