"""
CRUD tools: create_document, update_document, move_work_item.
"""

import os
import re
import time
from datetime import datetime
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import _extract_status_from_text

from .config import load_projects, next_work_id
from .helpers import (
    generate_slug, resolve_slug_collision,
    validate_tags, validate_project, validate_status_transition,
    rewrite_backlinks, trigger_site_build,
)
from .index import refresh_single, remove_from_index
from .index_file import regenerate_index_file
from .templates import (
    apply_work_item_template, apply_idea_template,
    apply_document_template, apply_adr_template, apply_bugfix_template,
)


def create_document(
    type: str,
    title: str,
    tags: list[str],
    description: str = "",
    project: str | None = None,
    doc_type: str = "Professional",
    directory: str | None = None,
    overview: str | None = None,
    design: str | None = None,
    acceptance_criteria: dict | None = None,
    tasks: list[str] | None = None,
    concept: str | None = None,
    key_questions: list[str] | None = None,
    content: str | None = None,
    related: list[str] | None = None,
    solution_plan: str | None = None,
    number: int | None = None,
    context_text: str | None = None,
    decision: str | None = None,
    rationale: str | None = None,
    consequences: str | None = None,
    severity: str | None = None,
    affected: str | None = None,
    problem: str | None = None,
    root_cause: str | None = None,
    fix: str | None = None,
    testing: str | None = None,
    recommendations: str | None = None,
) -> dict:
    """Create a new hyperspace document with full convention enforcement."""
    # Validate type
    valid_types = {"work-item", "idea", "document", "adr", "bugfix"}
    if type not in valid_types:
        return {"error": f"Invalid document type '{type}'. Must be one of: {sorted(valid_types)}"}

    # Validate tags
    valid_tags, tag_violations = validate_tags(tags)
    if tag_violations:
        return {
            "error": "Tag validation failed.",
            "violations": tag_violations,
            "valid_tags": valid_tags,
        }

    # Validate project
    if type == "work-item":
        if not project:
            return {"error": "Project is required for work-items."}
        project, proj_error = validate_project(project)
        if proj_error:
            return {"error": proj_error}

    # Generate content based on type
    if type == "work-item":
        if not overview:
            return {"error": "Overview is required for work-items."}
        if not description:
            description = overview[:120] + ("..." if len(overview) > 120 else "")
        work_id = next_work_id()
        md_content = apply_work_item_template(
            title=title, description=description, tags=valid_tags,
            project=project, doc_type=doc_type, overview=overview,
            design=design, acceptance_criteria=acceptance_criteria, tasks=tasks,
            work_id=work_id,
        )
        target_dir = HYPERSPACE_ROOT / "work" / "to-do"

    elif type == "idea":
        if not concept:
            return {"error": "Concept is required for ideas."}
        if not description:
            description = concept[:120] + ("..." if len(concept) > 120 else "")
        md_content = apply_idea_template(
            title=title, description=description, tags=valid_tags,
            doc_type=doc_type, concept=concept, key_questions=key_questions,
            related=related, solution_plan=solution_plan, problem=problem,
        )
        target_dir = HYPERSPACE_ROOT / "ideas"

    elif type == "document":
        if not content:
            return {"error": "Content is required for type='document'."}
        if not directory:
            return {"error": "Directory is required for type='document' (e.g., 'research/rbac', 'context', 'patterns/django')."}
        if not description:
            description = content[:120] + ("..." if len(content) > 120 else "")
        md_content = apply_document_template(
            title=title, description=description, tags=valid_tags,
            content=content, related=related,
        )
        target_dir = HYPERSPACE_ROOT / directory.replace("/", os.sep)

    elif type == "adr":
        if not all([number, context_text, decision, rationale]):
            return {"error": "ADR requires: number, context_text, decision, rationale."}
        md_content = apply_adr_template(
            title=title, tags=valid_tags, number=number,
            context=context_text, decision=decision, rationale=rationale,
            consequences=consequences, related=related,
        )
        topic_dir = directory or "research"
        target_dir = HYPERSPACE_ROOT / topic_dir.replace("/", os.sep)

    elif type == "bugfix":
        if not all([severity, affected, problem, root_cause, fix]):
            return {"error": "Bugfix requires: severity, affected, problem, root_cause, fix."}
        md_content = apply_bugfix_template(
            title=title, tags=valid_tags, severity=severity, affected=affected,
            problem=problem, root_cause=root_cause, fix=fix,
            testing=testing, recommendations=recommendations,
        )
        target_dir = HYPERSPACE_ROOT / "research" / "bugfixes"

    # Ensure target directory exists
    target_dir.mkdir(parents=True, exist_ok=True)

    # Generate slug
    slug_title = title if type != "adr" else f"adr-{number}-{title}"
    slug = generate_slug(slug_title)
    slug = resolve_slug_collision(target_dir, slug)

    # Write file
    final_path = target_dir / f"{slug}.md"
    try:
        final_path.write_text(md_content, encoding="utf-8")
    except OSError as e:
        return {"error": f"File write failed: {e}"}

    # Update index
    rel_path = str(final_path.relative_to(HYPERSPACE_ROOT)).replace("\\", "/")
    refresh_single(rel_path)
    regenerate_index_file()
    trigger_site_build(changed_path=rel_path)

    result = {
        "success": True,
        "path": rel_path,
        "title": title,
        "slug": slug,
        "tags": valid_tags,
    }
    if type == "work-item":
        result["id"] = work_id
    return result


def update_document(
    path: str,
    status: str | None = None,
    tags: list[str] | None = None,
    project: str | None = None,
    doc_type: str | None = None,
) -> dict:
    """Update metadata fields on an existing document."""
    full_path = HYPERSPACE_ROOT / path.replace("/", os.sep)
    if not full_path.exists():
        return {"error": f"File not found: {path}"}

    md_text = full_path.read_text(encoding="utf-8")
    lines = md_text.splitlines()
    updated_fields = []
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")

    # Validate status transition
    if status:
        current_status = _extract_status_from_text(md_text)
        error = validate_status_transition(current_status, status)
        if error:
            return {"error": error}
        # Block setting Complete via update_document for work items —
        # callers must use move_work_item() which also relocates the file.
        if status == "Complete" and "work/" in path:
            return {
                "error": "Cannot set status to 'Complete' via update_document for work items. "
                         "Use move_work_item(slug) instead, which moves the file to done/."
            }

    # Validate tags
    if tags is not None:
        valid_tags, tag_violations = validate_tags(tags)
        if tag_violations:
            return {"error": "Tag validation failed.", "violations": tag_violations}

    # Validate project
    if project:
        project, proj_error = validate_project(project)
        if proj_error:
            return {"error": proj_error}

    # Apply updates line by line
    updated_line = False
    new_lines = []
    for i, line in enumerate(lines):
        stripped = line.strip().lstrip("- ")

        if status and re.match(r'Status\s*:', stripped, re.IGNORECASE):
            new_lines.append(f"- Status: {status}")
            updated_fields.append(f"status: {status}")
            continue

        if tags is not None and re.match(r'Tags\s*:', stripped, re.IGNORECASE):
            new_lines.append(f"- Tags: {', '.join(valid_tags)}")
            updated_fields.append(f"tags: {', '.join(valid_tags)}")
            continue

        if project and re.match(r'Project\s*:', stripped, re.IGNORECASE):
            new_lines.append(f"- Project: {project}")
            updated_fields.append(f"project: {project}")
            continue

        if doc_type and re.match(r'Type\s*:', stripped, re.IGNORECASE):
            new_lines.append(f"- Type: {doc_type}")
            updated_fields.append(f"doc_type: {doc_type}")
            continue

        if re.match(r'(?:Last\s+)?Updated\s*:', stripped, re.IGNORECASE):
            new_lines.append(f"- Updated: {now}")
            updated_line = True
            continue

        new_lines.append(line)

    # If no Updated line found, insert after Created
    if not updated_line:
        for i, line in enumerate(new_lines):
            if re.match(r'^- Created:', line.strip(), re.IGNORECASE):
                new_lines.insert(i + 1, f"- Updated: {now}")
                break

    # Write back
    final_content = "\n".join(new_lines)
    if not final_content.endswith("\n"):
        final_content += "\n"
    full_path.write_text(final_content, encoding="utf-8")

    # Refresh index
    refresh_single(path)
    regenerate_index_file()
    trigger_site_build(changed_path=path)

    return {
        "success": True,
        "path": path,
        "updated_fields": updated_fields,
        "updated_timestamp": now,
    }


def move_work_item(slug: str) -> dict:
    """Move a work item from to-do to done (mark as complete)."""
    # Support WI-N ID format — resolve to slug
    if slug.upper().startswith("WI-"):
        from .index import get_index_lock, _index
        with get_index_lock():
            match = next((e for e in _index if e.get("work_id") and e["work_id"].upper() == slug.upper()), None)
        if not match:
            return {"error": f"No work item found with ID '{slug}'."}
        # Extract slug from path (e.g., "work/to-do/my-item.md" → "my-item")
        from pathlib import PurePosixPath
        slug = PurePosixPath(match["path"]).stem

    source_path = HYPERSPACE_ROOT / "work" / "to-do" / f"{slug}.md"
    if not source_path.exists():
        return {"error": f"Work item not found: work/to-do/{slug}.md"}

    dest_dir = HYPERSPACE_ROOT / "work" / "done"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / f"{slug}.md"

    if dest_path.exists():
        return {"error": f"Destination already exists: work/done/{slug}.md"}

    # Read and update metadata
    md_text = source_path.read_text(encoding="utf-8")
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    lines = md_text.splitlines()
    new_lines = []
    for line in lines:
        stripped = line.strip().lstrip("- ")
        if re.match(r'Status\s*:', stripped, re.IGNORECASE):
            new_lines.append("- Status: Complete")
        elif re.match(r'(?:Last\s+)?Updated\s*:', stripped, re.IGNORECASE):
            new_lines.append(f"- Updated: {now}")
        else:
            new_lines.append(line)

    # Write to destination
    try:
        dest_content = "\n".join(new_lines)
        if not dest_content.endswith("\n"):
            dest_content += "\n"
        dest_path.write_text(dest_content, encoding="utf-8")
    except OSError as e:
        return {"error": f"Failed to write destination: {e}"}

    # Update backlinks
    old_rel = f"work/to-do/{slug}.md"
    new_rel = f"work/done/{slug}.md"
    updated_backlinks = rewrite_backlinks(old_rel, new_rel)

    # Delete source — retry on Windows file-locking errors from concurrent builds
    deleted = False
    for attempt in range(5):
        try:
            source_path.unlink()
            deleted = True
            break
        except PermissionError:
            # File likely locked by background build thread; wait and retry
            time.sleep(0.2 * (attempt + 1))
        except OSError:
            break

    if not deleted and source_path.exists():
        # Non-fatal: destination is already written correctly.
        # Log the issue but don't fail the operation.
        pass

    # Update index
    remove_from_index(old_rel)
    refresh_single(new_rel)
    regenerate_index_file()
    trigger_site_build(changed_path=new_rel)

    return {
        "success": True,
        "old_path": old_rel,
        "new_path": new_rel,
        "updated_backlinks": updated_backlinks,
        "source_deleted": deleted,
    }
