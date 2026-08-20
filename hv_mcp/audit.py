"""
Work item audit — comprehensive reality check against the codebase and
steering conventions.

Replaces validate_work_item_claims with a broader tool that runs:
1. Claim verification (file/line references still valid) — delegated to claims.py
2. Pattern conformance (does the WI propose new infra when existing patterns serve?)
3. Steering compliance (are design decisions justified per conventions?)
4. Open questions resolution (searches codebase for evidence that answers unresolved questions)

All findings are advisory — this tool never modifies work items or marks tasks.
It surfaces open questions for human review.
"""

import re
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import read_md

from .claims import (
    _resolve_work_item,
    _extract_section,
    _extract_claims,
    _extract_unchecked_tasks,
    _verify_claim,
    MAX_FILE_READS,
    WORKSPACE_ROOT,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Steering directory — convention rules live here
STEERING_DIR = WORKSPACE_ROOT / ".kiro" / "steering"

# Keywords that signal new infrastructure proposals in a Design section.
# Each entry is (regex_pattern, category_label, what_to_check).
_NEW_INFRA_SIGNALS = [
    (re.compile(r'\bnew\s+model\b', re.IGNORECASE), "new-model",
     "Check if an existing model or table already captures this data."),
    (re.compile(r'\bnew\s+table\b', re.IGNORECASE), "new-table",
     "Check if an existing table with added columns/indexes could serve."),
    (re.compile(r'\bnew\s+migration\b', re.IGNORECASE), "new-migration",
     "Verify this migration adds genuinely new schema, not something already tracked."),
    (re.compile(r'\bnew\s+signal\b', re.IGNORECASE), "new-signal",
     "Check if an existing signal in the same app already fires on the relevant event."),
    (re.compile(r'\bnew\s+service\b', re.IGNORECASE), "new-service",
     "Check if existing utilities or services already handle this concern."),
    (re.compile(r'\bnew\s+app\b', re.IGNORECASE), "new-app",
     "Verify no existing app covers this domain before creating a new one."),
    (re.compile(r'\bnew\s+endpoint\b', re.IGNORECASE), "new-endpoint",
     "Check if an existing endpoint could be extended with a parameter or action."),
]

# Patterns that indicate a WI is proposing code in a specific location.
# Used to check whether nearby existing patterns are being followed.
_APP_PATH_RE = re.compile(
    r'`(?:cyber-portal|portal-cms)/(?:api|app)/(\w+)/',
)

# Model class definition pattern — for checking what already exists in an app
_MODEL_CLASS_RE = re.compile(r'^class\s+(\w+)\(.*models\.Model\)', re.MULTILINE)

# Signal registration pattern
_SIGNAL_RE = re.compile(r'@receiver\(\w+,\s*sender=(\w+)\)')

# Known audit/history patterns to check against
_HISTORY_PATTERNS = {
    "historic_logs": "Full-snapshot signal-driven audit logs (post_save/pre_delete → *_Log table)",
    "Organization_Log": "Organization snapshots including NCES fields — already captures all changes",
}


# ---------------------------------------------------------------------------
# Pattern Conformance Checks
# ---------------------------------------------------------------------------

def _check_new_infrastructure(design_text: str, impl_notes: str) -> list[dict]:
    """Scan Design and Implementation Notes for new infrastructure proposals.

    Returns findings when new infra is proposed without evident justification.
    Justification is checked across the ENTIRE Design section — it doesn't need
    to be adjacent to the specific mention. Design sections commonly justify
    new infrastructure in a separate "Pivots" or "Decisions" subsection, not
    inline with the table row that names the new file.
    """
    findings = []
    combined = design_text + "\n" + impl_notes

    # Check the full design section for justification language once
    design_lower = design_text.lower()
    has_global_justification = any(kw in design_lower for kw in [
        "existing", "already", "can't", "cannot", "doesn't support",
        "insufficient", "won't work", "doesn't handle", "no existing",
        "diverge", "not supported", "falls short", "reconsidered",
        "would violate", "overload", "locked", "not modified",
        "untouched", "belongs elsewhere",
    ])

    if has_global_justification:
        # The Design section contains justification language — new infra
        # proposals are likely addressed. Skip flagging.
        return findings

    for pattern, category, guidance in _NEW_INFRA_SIGNALS:
        matches = list(pattern.finditer(combined))
        if not matches:
            continue

        lines = combined.splitlines()
        for m in matches:
            char_pos = m.start()
            line_idx = combined[:char_pos].count('\n')

            findings.append({
                "category": "pattern_conformance",
                "subcategory": category,
                "severity": "advisory",
                "message": (
                    f"Design proposes {category.replace('-', ' ')} without evident "
                    f"justification for why existing infrastructure can't serve. "
                    f"{guidance}"
                    ),
                    "context": lines[line_idx].strip() if line_idx < len(lines) else "",
                    "line_in_section": line_idx + 1,
                })

    return findings


def _check_existing_patterns(design_text: str, md_text: str) -> list[dict]:
    """Check if the WI targets an app that has established patterns the design
    should align with.

    Looks for:
    - App has signals.py → design should use signals, not inline writes
    - App has a *_Log model in historic_logs → design should use it, not a new history table
    - App has existing services.py → business logic should go there, not in views
    """
    findings = []

    # Find which app(s) the WI targets
    app_matches = _APP_PATH_RE.findall(design_text)
    if not app_matches:
        return findings

    target_apps = set(app_matches)

    for app_name in target_apps:
        # Check if this app has a signals.py
        for repo in ("cyber-portal", "portal-cms"):
            signals_path = WORKSPACE_ROOT / repo / "api" / app_name / "signals.py"
            if signals_path.exists():
                # The app uses signals — check if the design mentions inline writes
                # for audit/history/logging
                design_lower = design_text.lower()
                inline_audit_signals = [
                    "write.*history.*in.*view",
                    "write.*log.*in.*partial_update",
                    "write.*log.*in.*create",
                    "write.*audit.*inline",
                    "history.*record.*in.*view",
                ]
                for pat_str in inline_audit_signals:
                    if re.search(pat_str, design_lower):
                        findings.append({
                            "category": "pattern_conformance",
                            "subcategory": "signal-vs-inline",
                            "severity": "advisory",
                            "message": (
                                f"The '{app_name}' app has an established signals.py with "
                                f"post_save/pre_delete handlers for audit logging. "
                                f"The design appears to propose inline writes instead. "
                                f"Verify this aligns with the existing pattern or document "
                                f"why the signal pattern doesn't fit."
                            ),
                            "context": f"{repo}/api/{app_name}/signals.py exists",
                        })
                        break

            # Check for existing *_Log models in historic_logs
            historic_logs_path = WORKSPACE_ROOT / repo / "api" / "historic_logs" / "models.py"
            if historic_logs_path.exists() and app_name in ("logs", "autho"):
                # This repo has historic_logs — check if design proposes a new
                # history/audit model in the main app instead
                new_history_model = re.search(
                    r'class\s+\w*(?:History|Audit|Log)\w*\(.*Model',
                    design_text,
                )
                if new_history_model:
                    findings.append({
                        "category": "pattern_conformance",
                        "subcategory": "history-model-placement",
                        "severity": "advisory",
                        "message": (
                            f"The codebase has a 'historic_logs' app with established "
                            f"*_Log models for audit trails (signal-driven full snapshots). "
                            f"The design proposes a new history/audit model outside that app. "
                            f"Verify the existing Organization_Log (or similar) can't serve "
                            f"this need with an added index or query."
                        ),
                        "context": new_history_model.group(0),
                    })

            # Check for existing services.py
            services_path = WORKSPACE_ROOT / repo / "api" / app_name / "services.py"
            if services_path.exists():
                # Check if design puts business logic in views
                if re.search(r'in.*views?\.py', design_text, re.IGNORECASE):
                    # Only flag if it sounds like business logic, not just a reference
                    if re.search(
                        r'(?:write|create|update|delete|process|handle).*in.*views?\.py',
                        design_text, re.IGNORECASE
                    ):
                        findings.append({
                            "category": "pattern_conformance",
                            "subcategory": "logic-in-views",
                            "severity": "info",
                            "message": (
                                f"The '{app_name}' app has services.py for business logic. "
                                f"The design references writing logic in views.py. "
                                f"Confirm this is appropriate (e.g., thin view delegation) "
                                f"rather than business logic that should live in services."
                            ),
                            "context": f"{repo}/api/{app_name}/services.py exists",
                        })

    return findings


def _check_design_justification(design_text: str) -> list[dict]:
    """Check if the Design section documents decisions about why existing
    patterns were or weren't used.

    A well-formed design section should reference what already exists when
    proposing something new. This check flags designs that propose new
    infrastructure with zero mention of existing alternatives.
    """
    findings = []

    if not design_text.strip():
        return findings

    # Check for new model/table proposals with no mention of existing infrastructure
    proposes_new = any(
        pat.search(design_text) for pat, _, _ in _NEW_INFRA_SIGNALS
    )

    if proposes_new:
        mentions_existing = any(kw in design_text.lower() for kw in [
            "existing", "current", "already", "currently",
            "organization_log", "historic_logs", "signals.py",
            "established pattern", "existing pattern",
        ])
        if not mentions_existing:
            findings.append({
                "category": "steering_compliance",
                "subcategory": "missing-existing-pattern-reference",
                "severity": "advisory",
                "message": (
                    "Design proposes new infrastructure but doesn't reference what "
                    "already exists in the codebase. Per steering ('Existing Patterns "
                    "First'), the Design section should document what was considered "
                    "and why existing infra falls short — or confirm it's being used."
                ),
                "context": "No mention of 'existing', 'current', or known pattern names found in Design.",
            })

    return findings


# ---------------------------------------------------------------------------
# Claims Check (delegated to claims.py)
# ---------------------------------------------------------------------------

def _run_claims_check(md_text: str) -> dict:
    """Run the file/line claim verification against the codebase.

    Returns structured findings matching the claims.py output format.
    """
    design_text = _extract_section(md_text, "design")
    impl_notes = _extract_section(md_text, "implementation notes")
    tasks_text = _extract_section(md_text, "tasks")
    ac_text = _extract_section(md_text, "acceptance criteria")

    all_claims = (
        _extract_claims(design_text, "Design")
        + _extract_claims(impl_notes, "Implementation Notes")
        + _extract_claims(tasks_text, "Tasks")
        + _extract_claims(ac_text, "Acceptance Criteria")
    )

    # De-dupe
    seen = set()
    deduped = []
    for c in all_claims:
        key = (c["path"], c["line_start"], c["line_end"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)

    truncated = False
    if len(deduped) > MAX_FILE_READS:
        deduped = deduped[:MAX_FILE_READS]
        truncated = True

    verified_claims = [_verify_claim(c) for c in deduped]

    # Possibly-done tasks heuristic
    unchecked = _extract_unchecked_tasks(md_text)
    possibly_done = []
    for task in unchecked:
        task_claims = _extract_claims(task, "Tasks")
        for tc in task_claims:
            verified = _verify_claim(tc)
            if verified["result"] in ("verified", "line_moved"):
                possibly_done.append(task)
                break

    return {
        "file_missing": [c for c in verified_claims if c["result"] == "file_missing"],
        "gaps": [c for c in verified_claims if c["result"] == "gap"],
        "line_moved": [c for c in verified_claims if c["result"] == "line_moved"],
        "verified": [c for c in verified_claims if c["result"] == "verified"],
        "unverifiable": [c for c in verified_claims if c["result"] == "unverifiable"],
        "possibly_done_tasks": possibly_done,
        "claims_checked": len(verified_claims),
        "truncated": truncated,
    }


# ---------------------------------------------------------------------------
# Open Questions Resolution
# ---------------------------------------------------------------------------

# Patterns for extracting searchable terms from question text.
# Backticked identifiers (class names, function names, file paths, field names).
_BACKTICK_RE = re.compile(r'`([^`]+)`')
# CamelCase or PascalCase identifiers (model/class names in prose).
_CAMELCASE_RE = re.compile(r'\b([A-Z][a-z]+(?:[A-Z][a-z]+)+)\b')
# snake_case identifiers that look like code (min 2 segments).
_SNAKE_RE = re.compile(r'\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\b')

# Max lines to read when scanning a file for evidence.
_EVIDENCE_MAX_LINES = 500
# Max files to scan per question to keep runtime bounded.
_EVIDENCE_MAX_FILES = 15


def _extract_open_questions(md_text: str) -> list[str]:
    """Parse bullet points from the ## Open Questions section."""
    section = _extract_section(md_text, "open questions")
    if not section.strip():
        return []
    questions = []
    current_lines = []
    for line in section.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            if current_lines:
                questions.append(" ".join(current_lines))
            current_lines = [stripped[2:].strip()]
        elif stripped and current_lines:
            # Continuation line of a multi-line bullet
            current_lines.append(stripped)
        elif not stripped and current_lines:
            questions.append(" ".join(current_lines))
            current_lines = []
    if current_lines:
        questions.append(" ".join(current_lines))
    return questions


def _extract_search_terms(question: str) -> list[str]:
    """Extract searchable code identifiers from a question string.

    Returns a deduplicated list of terms ordered by specificity:
    backticked terms first (most specific), then CamelCase, then snake_case.
    """
    terms = []
    seen = set()

    # Backticked terms are highest signal
    for m in _BACKTICK_RE.finditer(question):
        term = m.group(1).strip()
        # Skip full paths (handled by claims layer) and very short terms
        if len(term) >= 3 and term not in seen:
            terms.append(term)
            seen.add(term)

    # CamelCase identifiers
    for m in _CAMELCASE_RE.finditer(question):
        term = m.group(1)
        if term not in seen:
            terms.append(term)
            seen.add(term)

    # snake_case identifiers
    for m in _SNAKE_RE.finditer(question):
        term = m.group(1)
        if term not in seen:
            terms.append(term)
            seen.add(term)

    return terms


def _search_codebase_for_term(term: str) -> list[dict]:
    """Search the workspace for a term in Python and JS source files.

    Returns a list of evidence dicts: {path, line_num, snippet}.
    Uses subprocess grep for speed across large codebases, with a fallback
    to pure-Python scanning if grep is unavailable.
    """
    import subprocess

    evidence = []

    # If term looks like a file path, check if it exists directly
    term_as_path = WORKSPACE_ROOT / term.replace("/", "\\")
    if term_as_path.exists() and term_as_path.is_file():
        evidence.append({
            "path": term,
            "line_num": None,
            "snippet": "File exists at workspace root",
        })
        return evidence

    search_dirs = [
        WORKSPACE_ROOT / "cyber-portal" / "api",
        WORKSPACE_ROOT / "cyber-portal" / "app",
        WORKSPACE_ROOT / "portal-cms" / "api",
    ]

    skip_patterns = ["node_modules", "migrations", "__pycache__", ".git", "dist", "build", ".venv", "venv"]
    include_globs = ["*.py", "*.js", "*.jsx", "*.ts", "*.tsx"]

    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        if len(evidence) >= 3:
            break

        # Try grep (available on Windows via Git for Windows / Git Bash)
        try:
            cmd = [
                "grep", "-rn", "--include=*.py", "--include=*.js",
                "--include=*.jsx", "--include=*.ts", "--include=*.tsx",
                "-l",  # files-with-matches only (fast)
                term,
                str(search_dir),
            ]
            # Add excludes
            for skip in skip_patterns:
                cmd.insert(-2, f"--exclude-dir={skip}")

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=5,
                cwd=str(WORKSPACE_ROOT),
            )
            matching_files = [
                f.strip() for f in result.stdout.splitlines() if f.strip()
            ]
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # grep not available — fall back to Python scan
            matching_files = _python_find_files(search_dir, term, skip_patterns)

        # Read the first few matching files for line-level evidence
        for fpath_str in matching_files[:5]:
            if len(evidence) >= 3:
                break
            fpath = Path(fpath_str)
            if not fpath.is_file():
                continue
            try:
                lines = fpath.read_text(encoding="utf-8", errors="ignore").splitlines()
            except OSError:
                continue
            for i, line in enumerate(lines[:_EVIDENCE_MAX_LINES], 1):
                if term in line:
                    evidence.append({
                        "path": str(fpath.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
                        "line_num": i,
                        "snippet": line.strip()[:120],
                    })
                    break  # One hit per file

    return evidence


def _python_find_files(search_dir: Path, term: str, skip_dirs: list) -> list[str]:
    """Fallback: find files containing term via pure Python (slower)."""
    suffixes = (".py", ".js", ".jsx", ".ts", ".tsx")
    matching = []
    files_checked = 0
    for fpath in search_dir.rglob("*"):
        if files_checked >= 80:  # Higher budget for fallback
            break
        if not fpath.is_file():
            continue
        if fpath.suffix not in suffixes:
            continue
        if any(skip in fpath.parts for skip in skip_dirs):
            continue
        files_checked += 1
        try:
            content = fpath.read_text(encoding="utf-8", errors="ignore")
            if term in content:
                matching.append(str(fpath))
                if len(matching) >= 5:
                    break
        except OSError:
            continue
    return matching


def _resolve_open_questions(md_text: str) -> list[dict]:
    """Attempt to answer open questions by searching the codebase.

    For each question, extracts code identifiers and searches for them.
    Returns a list of dicts: {question, terms_searched, evidence, resolution_hint}.

    `resolution_hint` is one of:
    - "evidence_found" — codebase contains relevant code that may answer the question
    - "no_evidence" — nothing found (question may require human judgment or external info)
    """
    questions = _extract_open_questions(md_text)
    if not questions:
        return []

    results = []
    for question in questions:
        terms = _extract_search_terms(question)
        if not terms:
            results.append({
                "question": question,
                "terms_searched": [],
                "evidence": [],
                "resolution_hint": "no_searchable_terms",
            })
            continue

        all_evidence = []
        terms_that_hit = []

        for term in terms[:5]:  # Cap at 5 terms per question to bound runtime
            hits = _search_codebase_for_term(term)
            if hits:
                all_evidence.extend(hits)
                terms_that_hit.append(term)

        # Deduplicate evidence by (path, line_num)
        seen_evidence = set()
        deduped = []
        for ev in all_evidence:
            key = (ev["path"], ev["line_num"])
            if key not in seen_evidence:
                seen_evidence.add(key)
                deduped.append(ev)

        results.append({
            "question": question,
            "terms_searched": terms[:5],
            "terms_with_hits": terms_that_hit,
            "evidence": deduped[:6],  # Cap at 6 evidence items per question
            "resolution_hint": "evidence_found" if deduped else "no_evidence",
        })

    return results


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------

def audit_work_item(slug: str) -> dict:
    """Comprehensive reality check for a work item.

    Runs four layers of checks:
    1. Claim verification — file/line references against the actual codebase
    2. Pattern conformance — does the design align with established codebase patterns?
    3. Steering compliance — are conventions being followed (justification, existing patterns)?
    4. Open questions resolution — searches the codebase for evidence that may answer
       unresolved questions in the ## Open Questions section

    All findings are advisory. This tool never modifies documents.

    Args:
        slug: Work item filename (without .md) or WI-N id.

    Returns:
        Structured audit results with findings grouped by category.
    """
    rel_path, error = _resolve_work_item(slug)
    if error:
        return {"error": error}

    full_path = HYPERSPACE_ROOT / rel_path.replace("/", "\\")
    try:
        md_text = read_md(full_path)
    except OSError as e:
        return {"error": f"Could not read {rel_path}: {e}"}

    # --- Extract key sections ---
    design_text = _extract_section(md_text, "design")
    impl_notes = _extract_section(md_text, "implementation notes")

    # --- Layer 1: Claim verification ---
    claims_result = _run_claims_check(md_text)

    # --- Layer 2: Pattern conformance ---
    pattern_findings = []
    pattern_findings.extend(_check_new_infrastructure(design_text, impl_notes))
    pattern_findings.extend(_check_existing_patterns(design_text, md_text))

    # --- Layer 3: Steering compliance ---
    steering_findings = []
    steering_findings.extend(_check_design_justification(design_text))

    # --- Layer 4: Open questions resolution ---
    open_questions_results = _resolve_open_questions(md_text)

    # --- Build result ---
    claims_has_issues = bool(
        claims_result["file_missing"]
        or claims_result["gaps"]
        or claims_result["line_moved"]
        or claims_result["possibly_done_tasks"]
    )

    result = {
        "path": rel_path,
        "clean": not claims_has_issues and not pattern_findings and not steering_findings,
    }

    # Claims section
    result["claims"] = {
        "checked": claims_result["claims_checked"],
        "truncated": claims_result["truncated"],
        "verified": len(claims_result["verified"]),
        "unverifiable": len(claims_result["unverifiable"]),
        "issues": {},
    }
    if claims_result["file_missing"]:
        result["claims"]["issues"]["file_missing"] = [
            {"path": c["path"], "section": c["section"], "context": c["context"]}
            for c in claims_result["file_missing"]
        ]
    if claims_result["gaps"]:
        result["claims"]["issues"]["stale_references"] = [
            {"path": c["path"], "line_start": c["line_start"],
             "line_end": c["line_end"], "section": c["section"], "context": c["context"]}
            for c in claims_result["gaps"]
        ]
    if claims_result["line_moved"]:
        result["claims"]["issues"]["line_drift"] = [
            {"path": c["path"], "line_start": c["line_start"],
             "line_end": c["line_end"], "section": c["section"], "context": c["context"]}
            for c in claims_result["line_moved"]
        ]
    if claims_result["possibly_done_tasks"]:
        result["claims"]["issues"]["possibly_done_tasks"] = claims_result["possibly_done_tasks"]

    # Pattern conformance section
    result["pattern_conformance"] = {
        "findings": pattern_findings,
        "count": len(pattern_findings),
    }

    # Steering compliance section
    result["steering_compliance"] = {
        "findings": steering_findings,
        "count": len(steering_findings),
    }

    # Open questions resolution section
    if open_questions_results:
        result["open_questions"] = {
            "count": len(open_questions_results),
            "with_evidence": sum(
                1 for q in open_questions_results if q["resolution_hint"] == "evidence_found"
            ),
            "questions": open_questions_results,
        }

    # Summary
    total_issues = (
        len(claims_result["file_missing"])
        + len(claims_result["gaps"])
        + len(claims_result["line_moved"])
        + len(claims_result["possibly_done_tasks"])
        + len(pattern_findings)
        + len(steering_findings)
    )

    result["summary"] = {
        "total_findings": total_issues,
        "claims_issues": (
            len(claims_result["file_missing"])
            + len(claims_result["gaps"])
            + len(claims_result["line_moved"])
            + len(claims_result["possibly_done_tasks"])
        ),
        "pattern_conformance_issues": len(pattern_findings),
        "steering_compliance_issues": len(steering_findings),
        "claims_verified": len(claims_result["verified"]),
        "open_questions_researched": len(open_questions_results),
        "open_questions_with_evidence": sum(
            1 for q in open_questions_results if q["resolution_hint"] == "evidence_found"
        ),
    }

    if result["clean"]:
        result["message"] = (
            f"Work item passes all checks. {claims_result['claims_checked']} claim(s) "
            f"verified against the codebase, no pattern conformance issues, "
            f"steering compliance satisfied."
        )
    else:
        result["note"] = (
            "All findings are advisory — heuristic pattern matching, not proof. "
            "Review each finding and confirm or dismiss."
        )

    return result
