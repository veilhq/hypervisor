"""Task progress from git evidence — proposes which work item tasks are satisfied.

Reads a work item's tasks, finds the branches its assignee has pushed, and
matches changed files against the file references in each task. Reports findings
only; never writes to a document.

DESIGN NOTES (see WI-187)

Match on basename and symbol, not the task's stated path. WI-180 task 1
specified `api/permissions/migration_utils.py`; the file landed at
`api/portal_api/migration_utils.py`. A literal path check reports it missing and
the task gets marked incomplete — the exact error this exists to prevent.

Coverage is part of the contract. Only ~29% of tasks corpus-wide carry a
resolvable file reference (1,927 tasks across 151 items: 22% explicit path, 7%
bare filename, 14% symbol-only, 57% none). Reporting "9 of 21 satisfied" without
also reporting how many were assessable implies the rest are incomplete. Every
result therefore carries an `unassessable` count.

Task text only. The Implementation Notes location table has no row-to-task
mapping, so attributing a row to a task requires guessing. The table is used
solely to determine which repos a work item touches.

Evidence unions across branches and repos. Asking "which branch is this work
item's branch" forces a choice and discards the rest — WI-153's evidence spans
two repos and selection would lose half. Where one candidate's changed-file set
strictly contains another's (sequential stacks like
mk/api-restructure-wave-1..wave-5), the narrower branch is preferred and the
wider is kept as context, which biases toward under-claiming.
"""

import re
import sys
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.directory_index import _initials
from site_utils.file_utils import read_md, _extract_assignee_from_text

from .claims import WORKSPACE_ROOT, _extract_section, _resolve_work_item

# tools/ is a sibling of hv_mcp/, not a package — add it to the path the same
# way ado_bridge.py does for ado_collector.
_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import git_evidence as ge  # noqa: E402


# ---------------------------------------------------------------------------
# Reference extraction
# ---------------------------------------------------------------------------

_TASK_RE = re.compile(r'^\s*-\s*\[([ xX])\]\s*(.+)$')

# Backticked path containing a slash — the repo-relative form work items use.
_PATH_RE = re.compile(r'`([\w\-.]+(?:/[\w\-.]+)+\.\w{1,6})`')

_EXT = r'py|js|jsx|ts|tsx|css|json|tf|tfvars|md|yml|yaml|cjs|html|config|sh'
# Bare or backticked filename with a recognised extension.
_FILENAME_RE = re.compile(r'\b([\w\-]+\.(?:' + _EXT + r'))\b')

# Backticked identifier, optionally with call parens. 3-char minimum avoids
# matching noise like `id` or `ok`.
_SYMBOL_RE = re.compile(r'`([A-Za-z_][A-Za-z0-9_]{2,})\(?\)?`')

# Verbs whose completion is proven by absence rather than presence.
_REMOVAL_VERBS = (
    "remove", "delete", "drop", "prune", "strip", "eliminate",
    "decommission", "unregister", "revert",
)

# Verbs implying the target already exists. An add record is then the wrong
# shape of evidence: WI-182's "Rewrite `MessageBoard.js` as a pure consumer of
# context state" matched WI-9's branch *creating* that file. Both branches belong
# to the same author, so candidate selection cannot separate them — the verb can.
_MODIFY_VERBS = (
    "rewrite", "convert", "replace", "refactor", "update", "extend",
    "migrate", "modify", "adjust", "rework", "wire", "rename",
)

# Rename tasks state both sides of the change, and which side is present in the
# file is the whole answer. Old side still there means not done; new side there
# means done. Without this the two collapse into one "file contains a cited
# symbol" signal, which reads as partial progress when it is actually evidence of
# no progress — WI-181's "Rename `student_count` -> `participant_count`" is
# reported as `likely` while `student_count` is still in the file.
_RENAME_ARROW_RE = re.compile(r'`([^`]+)`\s*(?:\u2192|->|=>)\s*`([^`]+)`')
_RENAME_FROM_TO_RE = re.compile(r'\bfrom\s+`([^`]+)`\s+to\s+`([^`]+)`', re.I)


def _rename_pair(text: str) -> tuple[str, str] | None:
    """The (old, new) strings of an *identifier* rename, if the task states both.

    Raw backtick contents are used as needles rather than parsed identifiers,
    because the values are often not bare symbols — WI-181 renames
    `data-testid="student-count-input"`, quotes included, which searches fine
    literally but would not survive identifier tokenisation.

    File moves are deliberately excluded. WI-180 writes "move
    `seed_data/autho.json` -> `0025_baseline_autho.json`", which is the same
    arrow shape but a path pair, and searching file *content* for a filename
    proves nothing. Moves are proven by git rename records instead, which the
    diff branch already handles.
    """
    for pattern in (_RENAME_ARROW_RE, _RENAME_FROM_TO_RE):
        m = pattern.search(text)
        if not m:
            continue
        old, new = m.group(1).strip(), m.group(2).strip()
        if not old or not new or old == new:
            continue
        if any(_looks_like_path(s) for s in (old, new)):
            return None
        return old, new
    return None


def _looks_like_path(s: str) -> bool:
    """True if the string is a file path or filename rather than an identifier."""
    return "/" in s or bool(re.search(r'\.(?:' + _EXT + r')$', s, re.I))


def _leading_clause(text: str) -> str:
    """The task's opening clause, with any bold label stripped.

    Tasks commonly read "**Range lambda — writes**: Add ...", so the label has to
    come off before the verb is readable.
    """
    body = re.sub(r'^\s*\*\*[^*]+\*\*\s*:?\s*', '', text).strip()
    return re.split(r'[`,:(]', body, maxsplit=1)[0].lower()


def _is_removal(text: str) -> bool:
    """True if the task's *primary* action is taking something away.

    Only the leading verb counts. Scanning the whole line matches incidental
    mentions: WI-182's "Add `api_classroom_message.py` handling create, pin
    toggle, and delete (delete_item)" is an addition, but a whole-line scan sees
    "delete" and inverts the verdict.
    """
    head = _leading_clause(text)
    return any(re.search(r'\b' + v, head) for v in _REMOVAL_VERBS)


def _is_modification(text: str) -> bool:
    """True if the task's primary action presumes the target already exists."""
    head = _leading_clause(text)
    return any(re.search(r'\b' + v, head) for v in _MODIFY_VERBS)


# Repo hints from the bold-label convention this corpus uses: "**CMS**: ...",
# "**Portal — proxy write endpoints**: ...", "**Range TF — table**: ...".
# Without these, basename matching crosses repos — WI-180's "**CMS**: Create
# permissions/migrations/..." matched a cyber-portal rename of the same
# basename, which would have wrongly marked the task complete.
_REPO_HINTS = (
    (re.compile(r'\bcms\b', re.I), "portal-cms"),
    (re.compile(r'\brange\b', re.I), "cyber-range-api"),
    (re.compile(r'\bportal\b', re.I), "cyber-portal"),
)


def _repo_hint(text: str) -> str | None:
    """Repo named by a task's leading bold label, if any.

    Only the label is consulted. Prose mentions of "portal" or "range" appear
    throughout task bodies and are not scoping statements.
    """
    m = re.match(r'^\s*\*\*([^*]+)\*\*', text)
    if not m:
        return None
    label = m.group(1)
    for pattern, repo in _REPO_HINTS:
        if pattern.search(label):
            return repo
    return None


def extract_task_refs(task_text: str) -> dict:
    """Pull the resolvable references out of one task line.

    Returns {paths, basenames, symbols, removal, assessable}. A task is
    assessable when it names at least one path or filename — a symbol alone is
    not enough to locate a file without a tree-wide search per symbol.
    """
    paths = _PATH_RE.findall(task_text)
    basenames = {p.rsplit("/", 1)[-1] for p in paths}
    basenames.update(_FILENAME_RE.findall(task_text))
    symbols = {s for s in _SYMBOL_RE.findall(task_text)
               if not re.search(r'\.(?:' + _EXT + r')$', s)}

    return {
        "paths": sorted(set(paths)),
        "basenames": sorted(basenames),
        "symbols": sorted(symbols),
        "removal": _is_removal(task_text),
        "modification": _is_modification(task_text),
        "rename": _rename_pair(task_text),
        "repo_hint": _repo_hint(task_text),
        "assessable": bool(paths or basenames),
    }


def extract_tasks(md_text: str) -> list[dict]:
    """Every task in the Tasks section, with line numbers and extracted refs.

    Line numbers are 1-based against the whole document, so a caller can edit
    the right checkbox without re-parsing.
    """
    tasks_block = _extract_section(md_text, "tasks")
    if not tasks_block:
        return []

    # Locate the block within the document to recover absolute line numbers.
    all_lines = md_text.splitlines()
    block_lines = tasks_block.splitlines()
    offset = 0
    for i in range(len(all_lines) - len(block_lines) + 1):
        if all_lines[i:i + len(block_lines)] == block_lines:
            offset = i
            break

    out = []
    for idx, line in enumerate(block_lines):
        m = _TASK_RE.match(line)
        if not m:
            continue
        checked = m.group(1).lower() == "x"
        text = m.group(2).strip()
        out.append({
            "line": offset + idx + 1,
            "checked": checked,
            "text": text,
            **extract_task_refs(text),
        })
    return out


def referenced_repos(md_text: str, known_repos: set[str]) -> list[str]:
    """Which repos a work item touches, from every path it mentions.

    Scans the whole document (tasks plus the Implementation Notes location
    table) because the table is the most reliable signal for repo scoping even
    though it cannot be attributed to individual tasks.

    Returns [] when no path carries a repo prefix — many work items write
    repo-relative paths like `api/permissions/foo.py`. Callers should fall back
    to narrow_repos_by_content() rather than scanning every repo, which pulls in
    unrelated branches as candidates.
    """
    found = []
    for path in _PATH_RE.findall(md_text):
        head = path.split("/", 1)[0]
        if head in known_repos and head not in found:
            found.append(head)
    return found


def narrow_repos_by_content(repos: dict[str, Path], paths: list[str],
                            basenames: list[str]) -> list[str]:
    """Repos whose base tree actually contains any referenced file.

    Fallback for work items that write repo-relative paths with no prefix. One
    `ls-tree` per repo, then set membership — cheaper than diffing candidate
    branches in repos the work item never touches.
    """
    want_paths = {p.lower() for p in paths}
    want_bn = {b.lower() for b in basenames}
    hits = []
    for name, path in repos.items():
        base = ge.base_branch(path)
        listing = ge._git(path, "ls-tree", "-r", "--name-only",
                          f"origin/{base}", check=False)
        if not listing:
            continue
        tracked = listing.splitlines()
        lowered = {t.lower() for t in tracked}
        if want_paths & lowered:
            hits.append(name)
            continue
        if want_bn and {t.rsplit("/", 1)[-1].lower() for t in tracked} & want_bn:
            hits.append(name)
    return hits


# ---------------------------------------------------------------------------
# Assignee resolution
# ---------------------------------------------------------------------------

def candidate_branches(repo_path: Path, assignee: str, max_age_days: int | None) -> dict:
    """Branches in one repo plausibly belonging to `assignee`.

    Two independent signals, both cheap since list_branches already returns
    author and prefix:

      commit author — always present, so this is primary
      branch prefix — absent on branches like `qa`, `portal-terraform`,
                      `test/wave3-only`, `hotfix/copyright`, so corroborating only

    Disagreement between them (someone pushing to a colleague's branch) is
    reported rather than suppressed.
    """
    want = _initials(assignee) if assignee else None
    branches = ge.list_branches(repo_path, max_age_days=max_age_days)

    mine, disagreements = [], []
    for b in branches:
        by_author = bool(want) and _initials(b["author"] or "") == want
        by_prefix = bool(want) and (b["prefix"] or "").upper() == want
        if by_author or by_prefix:
            b = {**b, "matched_by": "both" if (by_author and by_prefix)
                 else ("author" if by_author else "prefix")}
            mine.append(b)
            if by_author != by_prefix and b["prefix"]:
                disagreements.append({
                    "branch": b["short"], "author": b["author"],
                    "prefix": b["prefix"], "matched_by": b["matched_by"],
                })
    return {"branches": mine, "disagreements": disagreements, "scanned": len(branches)}


# ---------------------------------------------------------------------------
# Evidence gathering
# ---------------------------------------------------------------------------

def _prefer_narrower(branches: list[dict], diffs: dict[str, list[dict]]) -> set[str]:
    """Names of branches whose changed-file set is a strict superset of another's.

    Sequential stacks diff against the base, so a later stage contains every
    earlier stage's files. Crediting a work item for the whole stack over-claims,
    so the wider branch is demoted to context.
    """
    sets = {name: {d["path"] for d in ds} for name, ds in diffs.items() if ds}
    wider = set()
    for a, sa in sets.items():
        for b, sb in sets.items():
            if a != b and sb < sa:      # sa strictly contains sb
                wider.add(a)
                break
    return wider


def gather_evidence(repo_name: str, repo_path: Path, branches: list[dict],
                    paths: list[str], basenames: list[str]) -> dict:
    """Collect diff and tree evidence for one repo.

    Diffs only unmerged branches — a merged branch yields an empty three-dot
    diff, so merged work is read from tree state instead.
    """
    base = ge.base_branch(repo_path)

    diffs: dict[str, list[dict]] = {}
    for b in branches:
        if b["merged"]:
            continue
        try:
            diffs[b["short"]] = ge.diff_evidence(repo_path, b["name"], base)
        except ge.GitEvidenceError:
            diffs[b["short"]] = []

    wider = _prefer_narrower(branches, diffs)

    # Strip the repo prefix — git paths are repo-relative.
    rel_paths = []
    for p in paths:
        head, _, rest = p.partition("/")
        rel_paths.append(rest if head == repo_name and rest else p)

    tree = ge.tree_evidence(repo_path, rel_paths) if rel_paths else {}

    # Resolve basename-only references to real paths, so tasks that name a file
    # without a path still get tree evidence. One ls-tree for the whole repo
    # beats one find_by_basename call per basename.
    basename_paths: dict[str, list[str]] = {}
    if basenames:
        want = {b.lower() for b in basenames}
        listing = ge._git(repo_path, "ls-tree", "-r", "--name-only",
                          f"origin/{base}", check=False)
        for tracked in listing.splitlines():
            bn = tracked.rsplit("/", 1)[-1].lower()
            if bn in want:
                basename_paths.setdefault(bn, []).append(tracked)

    resolved = sorted({p for ps in basename_paths.values() for p in ps})
    basename_tree = ge.tree_evidence(repo_path, resolved) if resolved else {}

    # Locate files whose stated path is absent from the base tree; they may have
    # landed elsewhere. This is what catches the migration_utils.py case.
    relocated: dict[str, list[str]] = {}
    for p, st in tree.items():
        if not st.get(base):
            bn = p.rsplit("/", 1)[-1]
            hits = [h for h in ge.find_by_basename(repo_path, base, bn) if h != p]
            if hits:
                relocated[p] = hits

    return {
        "base": base,
        "repo_path": repo_path,
        "diffs": diffs,
        "wider_branches": sorted(wider),
        "tree": tree,
        "basename_paths": basename_paths,
        "basename_tree": basename_tree,
        "relocated": relocated,
        "merged_branches": [b["short"] for b in branches if b["merged"]],
        "unmerged_branches": [b["short"] for b in branches if not b["merged"]],
    }


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def _match_in_diffs(task: dict, repo_name: str, ev: dict) -> list[dict]:
    """Diff records in this repo matching the task's paths or basenames.

    Honours the task's repo hint: a "**CMS**:" task must not be satisfied by
    cyber-portal evidence just because both repos contain a file of the same name.
    """
    if task.get("repo_hint") and task["repo_hint"] != repo_name:
        return []

    wanted_bn = {b.lower() for b in task["basenames"]}
    wanted_paths = set()
    for p in task["paths"]:
        head, _, rest = p.partition("/")
        wanted_paths.add((rest if head == repo_name and rest else p).lower())

    hits = []
    for branch, records in ev["diffs"].items():
        if branch in ev["wider_branches"]:
            continue
        for rec in records:
            path_l = rec["path"].lower()
            old_l = (rec["old_path"] or "").lower()
            if (path_l in wanted_paths or old_l in wanted_paths
                    or path_l.rsplit("/", 1)[-1] in wanted_bn
                    or (old_l and old_l.rsplit("/", 1)[-1] in wanted_bn)):
                hits.append({"repo": repo_name, "branch": branch, **rec})
    return hits


def _match_in_tree(task: dict, repo_name: str, ev: dict) -> list[dict]:
    """Tree-state facts relevant to this task, including relocations.

    Covers both explicit paths and basename-only references. The latter matters:
    WI-153's tasks name `AnalyticsContext.js` and `RangeAnalyticsTab.js` with no
    path, and its branches are merged, so without basename resolution the item
    yields no evidence at all despite four tasks being demonstrably done.
    """
    base = ev["base"]
    out = []
    seen = set()

    if task.get("repo_hint") and task["repo_hint"] != repo_name:
        return []

    def _fact(rel: str, via: str):
        st = ev["tree"].get(rel) or ev["basename_tree"].get(rel)
        if not st or rel in seen:
            return
        seen.add(rel)

        # Which cited symbols appear in the file on the base branch, and which
        # appeared on an older release ref. Both are needed: absence on base is
        # only removal evidence if the symbol was there before. Without the
        # older-ref check, "RUN_SEED absent from application-init's
        # variables.tf" reads as a completed removal when the variable was
        # never in that repo at all.
        on_base, on_older, older_ref = [], [], None
        if task["symbols"]:
            if st.get(base):
                on_base = ge.file_contains(ev["repo_path"], base, rel, task["symbols"])
            for ref in ("main", "qa"):
                if ref != base and st.get(ref):
                    older_ref = ref
                    on_older = ge.file_contains(ev["repo_path"], ref, rel, task["symbols"])
                    break

        # Rename direction. Both sides are checked in one read, and which one is
        # present is decisive rather than suggestive.
        rn_old = rn_new = False
        if task.get("rename") and st.get(base):
            old, new = task["rename"]
            found = ge.file_contains(ev["repo_path"], base, rel, [old, new])
            rn_old, rn_new = old in found, new in found

        out.append({
            "repo": repo_name, "path": rel, "via": via,
            "on_base": bool(st.get(base)),
            "tier_present": st.get("tier_present"),
            "tier_absent": st.get("tier_absent"),
            "relocated_to": ev["relocated"].get(rel, []),
            "symbols_present": on_base,
            "symbols_on_older": on_older,
            "older_ref": older_ref,
            "rename_old_present": rn_old,
            "rename_new_present": rn_new,
        })

    for p in task["paths"]:
        head, _, rest = p.partition("/")
        _fact(rest if head == repo_name and rest else p, "path")

    for bn in task["basenames"]:
        for rel in ev["basename_paths"].get(bn.lower(), []):
            _fact(rel, "basename")

    return out


def classify(task: dict, diff_hits: list[dict], tree_facts: list[dict]) -> dict:
    """Assign a verdict and confidence to one task.

    Verdicts:
      satisfied     strong evidence the work landed
      likely        the right files were modified, but completion isn't proven
      not_found     nothing touched the referenced files
      unassessable  no resolvable file reference in the task text
    """
    if not task["assessable"]:
        return {"verdict": "unassessable", "confidence": "none",
                "why": "no resolvable file reference in task text"}

    # Renames are decided by which side of the change is in the file. Skipped
    # when a diff already shows the file added or renamed — a branch record is
    # stronger evidence than inspecting the base tree's content, and running
    # this first would discard it.
    if task.get("rename") and not any(
            h["change_type"] in ("A", "R", "C") for h in diff_hits):
        old, new = task["rename"]
        for f in tree_facts:
            if f["rename_new_present"] and not f["rename_old_present"]:
                return {"verdict": "satisfied", "confidence": "strong",
                        "why": f"{f['path']} uses {new} and no longer contains {old}"}
            if f["rename_new_present"] and f["rename_old_present"]:
                return {"verdict": "likely", "confidence": "moderate",
                        "why": f"{f['path']} contains both {old} and {new}"
                               " — rename appears partial"}
            if f["rename_old_present"]:
                return {"verdict": "not_found", "confidence": "strong",
                        "why": f"{f['path']} still contains {old} — rename not done"}
        # Neither side found: the file reference is probably pointing elsewhere.
        if tree_facts:
            return {"verdict": "not_found", "confidence": "weak",
                    "why": f"neither {old} nor {new} found in the referenced file"}

    # Removal tasks are proven by absence, not presence.
    if task["removal"]:
        for f in tree_facts:
            # Absence alone is not removal evidence — the path may never have
            # existed there. WI-180 cites `.ebextensions/02_db-migrate.config`
            # while the file lives at `api/.ebextensions/...`, so it reads as
            # absent on every ref. Require it to still exist on a later ref,
            # which is what distinguishes "removed on dev" from "wrong path".
            if not f["on_base"] and f["tier_present"]:
                return {"verdict": "satisfied", "confidence": "strong",
                        "why": f"{f['path']} is gone from {f['repo']}'s base branch but "
                               f"still on {f['tier_present']} — removal landed"}
        for h in diff_hits:
            if h["change_type"] == "D":
                return {"verdict": "satisfied", "confidence": "strong",
                        "why": f"{h['branch']} deletes {h['path']}"}
        # Symbol-level removal: the file survives but a cited identifier is gone
        # from it. Evaluated per symbol, not across all of them — a task citing
        # several identifiers (or carrying an annotation that adds incidental
        # ones) would otherwise fail the check because some unrelated token is
        # still present. Requires the symbol to have existed on an older ref,
        # so a file that never contained it does not read as a completed removal.
        for f in tree_facts:
            removed = [s for s in f["symbols_on_older"] if s not in f["symbols_present"]]
            if f["on_base"] and removed:
                return {"verdict": "satisfied", "confidence": "strong",
                        "why": f"{f['path']} contained {', '.join(removed[:3])} on "
                               f"{f['older_ref']} and no longer does on the base "
                               "branch — removal landed"}
        # Absent everywhere means the reference does not resolve, not that the
        # work is done.
        if any(not f["on_base"] and not f["tier_present"] for f in tree_facts):
            return {"verdict": "not_found", "confidence": "weak",
                    "why": "referenced path does not exist on any ref — "
                           "the task's path is probably stale or relative"}
        if tree_facts or diff_hits:
            return {"verdict": "not_found", "confidence": "moderate",
                    "why": "referenced files still present on the base branch"}
        return {"verdict": "not_found", "confidence": "weak",
                "why": "no branch or tree evidence for the referenced files"}

    # Addition / modification tasks.
    adds = [h for h in diff_hits if h["change_type"] in ("A", "R", "C")]
    if adds:
        h = adds[0]
        detail = (f"{h['branch']} renames {h['old_path']} -> {h['path']}"
                  if h["change_type"] in ("R", "C")
                  else f"{h['branch']} adds {h['path']}")
        # A task that rewrites or replaces something presumes it already exists,
        # so an add record probably belongs to whatever created the file — often
        # an earlier story on a sibling branch by the same author.
        if task.get("modification") and h["change_type"] == "A":
            return {"verdict": "likely", "confidence": "weak",
                    "why": f"{detail}, but this task describes modifying existing code"
                           " — the add likely belongs to earlier work"}
        return {"verdict": "satisfied", "confidence": "strong", "why": detail}

    # Merged work: present on the integration branch but not yet on main means
    # it was added since the last release, which attributes it to recent work.
    for f in tree_facts:
        if f["on_base"] and f["tier_present"] and f["tier_present"] != "main":
            return {"verdict": "satisfied", "confidence": "strong",
                    "why": f"{f['path']} exists on {f['tier_present']} but not main"
                           " — landed since the last release"}

    # Relocation: stated path is empty but the basename lives elsewhere. Only
    # "likely" — a relocation is ambiguous on its own. It may mean the file
    # moved (task done, different path) or that the stated path is simply wrong
    # and the file sits where it always did (task not done). WI-180's CMS task
    # cites `seed_data/permissions.json` while the file is at
    # `api/seed_data/permissions.json`, which is a prefix mismatch rather than a
    # completed move. Genuine relocations that were done also produce a diff
    # add record, which the stronger branch above already catches.
    for f in tree_facts:
        if f["relocated_to"]:
            return {"verdict": "likely", "confidence": "moderate",
                    "why": f"stated path {f['path']} is absent; a file of that name "
                           f"exists at {', '.join(f['relocated_to'][:2])} — verify "
                           "whether this is a completed move or a stale path"}

    mods = [h for h in diff_hits if h["change_type"] == "M"]
    if mods:
        return {"verdict": "likely", "confidence": "moderate",
                "why": f"{mods[0]['branch']} modifies {mods[0]['path']}"
                       " — work happened here, completion not proven"}

    # Symbol confirmation in an existing file: weaker than a diff record, but it
    # shows the named identifier is actually there rather than only the file.
    for f in tree_facts:
        if f["on_base"] and task["symbols"] and f["symbols_present"]:
            return {"verdict": "likely", "confidence": "moderate",
                    "why": f"{f['path']} contains {', '.join(f['symbols_present'][:3])}"
                           " — cannot date the change from tree state alone"}

    for f in tree_facts:
        if f["on_base"] and f["tier_present"] == "main":
            return {"verdict": "likely", "confidence": "weak",
                    "why": f"{f['path']} exists everywhere including main"
                           " — cannot attribute to this task"}

    return {"verdict": "not_found", "confidence": "moderate",
            "why": "no candidate branch touched the referenced files"}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def check_task_progress(slug: str, fetch: bool = True,
                        max_age_days: int | None = 30) -> dict:
    """Report which of a work item's tasks are supported by git evidence.

    Args:
        slug: Work item slug or ID (e.g. 'WI-180').
        fetch: Fetch the referenced repos first. Only pushed work is visible to
               git, so skipping this reads whatever refs are already local.
        max_age_days: Age window for candidate branches. None for no limit.

    Returns a dict with per-task findings plus coverage counts. Never writes.
    """
    rel_path, err = _resolve_work_item(slug)
    if err:
        return {"ok": False, "error": err}

    doc = HYPERSPACE_ROOT / rel_path
    md = read_md(doc)

    assignee = _extract_assignee_from_text(md)
    tasks = extract_tasks(md)
    if not tasks:
        return {"ok": False, "error": f"{rel_path} has no Tasks section"}

    repos = ge.discover_repos(WORKSPACE_ROOT)
    all_paths = sorted({p for t in tasks for p in t["paths"]})
    all_bn = sorted({b for t in tasks for b in t["basenames"]})

    # Prefer repo-prefixed paths; fall back to asking which repos actually
    # contain the referenced files. Scanning every repo would pull in unrelated
    # branches as candidates and add noise to every finding.
    scoped = referenced_repos(md, set(repos))
    scope_basis = "path prefix"
    if not scoped:
        scoped = narrow_repos_by_content(repos, all_paths, all_bn)
        scope_basis = "file content"
    if not scoped:
        scoped = list(repos)
        scope_basis = "fallback: all repos"

    fetch_results = {}
    if fetch:
        fetch_results = ge.fetch_repos([repos[r] for r in scoped if r in repos])

    per_repo, disagreements = {}, []
    for name in scoped:
        if name not in repos:
            continue
        cand = candidate_branches(repos[name], assignee or "", max_age_days)
        disagreements.extend(cand["disagreements"])
        repo_paths = [p for p in all_paths if p.split("/", 1)[0] == name] or all_paths
        per_repo[name] = {
            "candidates": cand,
            "evidence": gather_evidence(name, repos[name], cand["branches"],
                                        repo_paths, all_bn),
            "fetch_age_hours": ge.fetch_age_hours(repos[name]),
        }

    findings = []
    for t in tasks:
        diff_hits, tree_facts = [], []
        for name, blob in per_repo.items():
            diff_hits.extend(_match_in_diffs(t, name, blob["evidence"]))
            tree_facts.extend(_match_in_tree(t, name, blob["evidence"]))
        verdict = classify(t, diff_hits, tree_facts)
        findings.append({
            "line": t["line"], "checked": t["checked"],
            "text": t["text"][:160],
            "removal": t["removal"],
            **verdict,
            "evidence": diff_hits[:4],
        })

    assessable = [f for f in findings if f["verdict"] != "unassessable"]
    satisfied = [f for f in assessable if f["verdict"] == "satisfied"]
    # Only unchecked-but-satisfied tasks are actionable.
    actionable = [f for f in satisfied if not f["checked"]]

    return {
        "ok": True,
        "work_item": rel_path,
        "assignee": assignee,
        "assignee_initials": _initials(assignee) if assignee else None,
        "repos_scoped": scoped,
        "scope_basis": scope_basis,
        "fetched": fetch_results,
        "freshness_hours": {n: b["fetch_age_hours"] for n, b in per_repo.items()},
        "branch_candidates": {
            n: [b["short"] for b in b_["candidates"]["branches"]]
            for n, b_ in per_repo.items()
        },
        "author_prefix_disagreements": disagreements,
        "coverage": {
            "tasks_total": len(tasks),
            "assessed": len(assessable),
            "unassessable": len(tasks) - len(assessable),
            "satisfied": len(satisfied),
            "likely": sum(1 for f in assessable if f["verdict"] == "likely"),
            "not_found": sum(1 for f in assessable if f["verdict"] == "not_found"),
            "already_checked": sum(1 for f in findings if f["checked"]),
            "actionable": len(actionable),
        },
        "actionable_lines": [f["line"] for f in actionable],
        "findings": findings,
        "note": (
            "Only pushed work is visible to git — a teammate working locally "
            "produces no evidence. Findings are advisory; this tool never edits "
            "a document."
        ),
    }
