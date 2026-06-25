"""
Shared helpers: slug generation, validation, backlink rewriting, site build trigger.
"""

import importlib.util
import os
import re
import threading
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import collect_files

from .config import VALID_TRANSITIONS, load_tags, load_projects, HYPERVISOR_DIR


# ---------------------------------------------------------------------------
# Site Build Trigger
# ---------------------------------------------------------------------------

def trigger_site_build(changed_path: str | None = None):
    """Run a site build to regenerate HTML after write ops.

    Args:
        changed_path: Relative path to the primary file that changed (e.g.
                      "work/to-do/my-item.md"). When provided AND the desktop
                      app is running, triggers an incremental build for that
                      file instead of relying on the watcher (which can miss
                      the file due to debounce settling on a later _index.md
                      write). When None, triggers a full build.

    When the desktop app is running and a specific file is provided, the build
    runs synchronously to guarantee the fragment exists before the watcher fires
    a reload. Without this, the watcher's debounce can settle on _index.md,
    trigger a reload showing the new index card, but the document fragment
    hasn't been written yet — causing navigation to fail.

    When the app is NOT running (MCP-only mode), builds run in a background
    thread to avoid blocking the tool response.
    """
    app_lock = HYPERVISOR_DIR / ".app_running"
    app_is_running = app_lock.exists()

    if app_is_running and not changed_path:
        # No specific file — let the watcher handle it to avoid duplicates.
        return

    def _build():
        try:
            spec = importlib.util.spec_from_file_location("build", str(HYPERVISOR_DIR / "build.py"))
            build_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(build_mod)
            if changed_path:
                build_mod.build_single_file(changed_path)
            else:
                build_mod.full_build()
        except Exception:
            pass

    if app_is_running and changed_path:
        # Synchronous: fragment MUST exist before the watcher triggers reload
        _build()
    else:
        threading.Thread(target=_build, daemon=True).start()


# ---------------------------------------------------------------------------
# Slug Generation
# ---------------------------------------------------------------------------

def generate_slug(title: str, max_len: int = 60) -> str:
    """Generate a kebab-case slug from a title.

    Rules:
    - Lowercase
    - Replace spaces/non-alphanumeric with hyphens
    - Collapse consecutive hyphens
    - Strip leading/trailing hyphens
    - Max 60 chars, truncated at last word boundary
    """
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    slug = slug.strip('-')

    if len(slug) > max_len:
        truncated = slug[:max_len]
        last_hyphen = truncated.rfind('-')
        if last_hyphen > 20:
            slug = truncated[:last_hyphen]
        else:
            slug = truncated

    return slug


def resolve_slug_collision(directory: Path, slug: str) -> str:
    """If slug.md exists, append -2, -3, etc."""
    if not (directory / f"{slug}.md").exists():
        return slug
    counter = 2
    while (directory / f"{slug}-{counter}.md").exists():
        counter += 1
    return f"{slug}-{counter}"


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------

def validate_tags(tags: list[str]) -> tuple[list[str], list[dict]]:
    """Validate tags against registry. Returns (valid_tags, violations)."""
    registry = load_tags()
    tag_names = set(registry.keys())
    violations = []
    valid = []

    for tag in tags:
        tag = tag.lower().strip()
        if tag in tag_names:
            valid.append(tag)
        else:
            suggestions = get_close_matches(tag, list(tag_names), n=3, cutoff=0.6)
            violations.append({
                "tag": tag,
                "message": f"Tag '{tag}' is not in the canonical registry.",
                "suggestions": suggestions,
            })
    return valid, violations


def validate_project(project: str | None) -> tuple[str | None, str | None]:
    """Validate project against registry. Returns (project, error_message)."""
    if project is None:
        return None, None
    projects = load_projects()
    if not projects:
        return project, None
    if project in projects:
        return project, None
    suggestions = get_close_matches(project, projects, n=2, cutoff=0.5)
    suggestion_str = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
    return None, f"Project '{project}' is not in the registry.{suggestion_str}"


def validate_status_transition(current: str | None, new: str) -> str | None:
    """Validate a status transition. Returns error message or None."""
    if current is None:
        return None
    if current == new:
        return None
    allowed = VALID_TRANSITIONS.get(current, set())
    if new not in allowed:
        return (
            f"Cannot transition from '{current}' to '{new}'. "
            f"Valid transitions from '{current}': {sorted(allowed) if allowed else 'none (immutable)'}."
        )
    return None


# ---------------------------------------------------------------------------
# Backlink Rewriting
# ---------------------------------------------------------------------------

def rewrite_backlinks(old_rel: str, new_rel: str) -> list[str]:
    """Rewrite references from old_rel to new_rel in all hyperspace docs."""
    updated_files = []
    files = collect_files(HYPERSPACE_ROOT)

    for rel in files:
        full_path = HYPERSPACE_ROOT / rel
        try:
            content = full_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        if old_rel not in content and _slug_from_path(old_rel) not in content:
            continue

        new_content = _replace_outside_code_blocks(content, old_rel, new_rel)

        if new_content != content:
            full_path.write_text(new_content, encoding="utf-8")
            updated_files.append(str(rel).replace("\\", "/"))

    return updated_files


def _slug_from_path(path: str) -> str:
    """Extract filename from a path."""
    return path.split("/")[-1]


def _replace_outside_code_blocks(text: str, old: str, new: str) -> str:
    """Replace old with new, but skip fenced code blocks."""
    result = []
    in_code = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code = not in_code
        if not in_code:
            line = line.replace(old, new)
        result.append(line)
    return "\n".join(result)
