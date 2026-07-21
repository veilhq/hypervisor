# HV-SETUP

How to add Hypervisor to a new workspace that doesn't already have a `.hyperspace` directory.

- Created: 2026-04-22T00:00
- Updated: 2026-04-23T00:00

## Prerequisites

- Python 3.x
- `pip install markdown pygments`

## Steps

### 1. Create the directory structure

At the root of your workspace:

```
your-workspace/
└── .hyperspace/
    └── .hypervisor/
        ├── build.py
        ├── site_utils/       # build modules package
        ├── assets/
        │   ├── css/          # modular CSS (concatenated during build)
        │   └── app.js
        └── docs/             # optional — hypervisor's own docs
```

Copy the entire `.hypervisor/` directory from an existing workspace. The essential pieces are `build.py`, the `site_utils/` package, and `assets/`.

### 2. Add your content directories

Create whatever top-level directories make sense for your project. There are no required directories — Hypervisor will render whatever it finds.

```
.hyperspace/
├── .hypervisor/          # the generator (copied in step 1)
├── context/              # example: project overviews
├── patterns/             # example: reusable solutions
├── research/             # example: investigations, ADRs
└── any-name-you-want/    # directories are auto-discovered
```

### 3. Customize categories

Open `site_utils/config.py` and edit the three dictionaries to match your directories:

```python
CATEGORY_LABELS = {
    "context": "Context",
    "patterns": "Patterns",
    "your-dir": "Your Label",
}

CATEGORY_DESCRIPTIONS = {
    "context": "Project overviews and architecture docs",
    "patterns": "Reusable solutions and code templates",
    "your-dir": "Description shown on the directory index page",
}

CATEGORY_ICONS = {
    "context": "book-open",
    "patterns": "puzzle",
    "your-dir": "folder",       # any Lucide icon name
}
```

Directories not listed in these dictionaries still appear — they just get auto-generated labels (kebab-case converted to Title Case) and a generic folder icon.

### 4. Review skip directories

The `SKIP_DIRS` set in `site_utils/config.py` controls which directories are excluded from scanning:

```python
SKIP_DIRS = {"__pycache__", "site"}
```

Add any directories you want hidden from the generated site. The `site` entry prevents the output directory from being scanned recursively.

### 5. Add markdown documents

Drop `.md` documents into your content directories. Hypervisor picks up any document ending in `.md` anywhere under `.hyperspace/` (except skipped dirs).

For best results, each document should have:
- An H1 title as the first line
- Optional metadata lines after the title (`Created:`, `Updated:`, `Tags:`, etc.)
- Dates use datetime format: `YYYY-MM-DDTHH:MM`

```markdown
# My Document Title

- Created: 2026-04-22T14:30
- Tags: setup, example

## Content starts here
```

### 6. Build

```bash
cd .hyperspace/.hypervisor
python build.py
```

The site generates into `.hypervisor/site/` and opens in your default browser.

## What's auto-detected

- **HYPERSPACE_ROOT** — resolved relative to `config.py`'s location in the `site_utils` package, so it always points to `.hyperspace/` regardless of where the workspace lives
- **OUTPUT_DIR** — always `.hypervisor/site/`
- **Directory indexes** — auto-generated for every directory containing documents
- **Search index** — built from all discovered markdown documents, embedded in every page
- **Date sorting** — document listings sort by `Updated` or `Created` metadata if present

No paths are hardcoded to a specific workspace. Copy the `.hypervisor/` directory, customize the category dictionaries in `site_utils/config.py`, and it works.

## Gitignore

Add to your `.gitignore`:

```
.hyperspace/.hypervisor/site/
```

The `site/` directory is ephemeral output — never edit or commit generated files.

## Minimal example

A workspace with just two documents:

```
my-project/
└── .hyperspace/
    ├── .hypervisor/        # copied from existing workspace
    ├── notes/
    │   └── setup-log.md
    └── decisions/
        └── why-postgres.md
```

Run `python build.py` and you get a browsable site: the homepage shows a Workspace Pulse (recent activity) and Pinned panel; the topbar nav rail exposes the two categories ("Notes" and "Decisions"), and each category page lists its document.