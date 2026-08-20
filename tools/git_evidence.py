"""Git evidence layer — read-only branch and tree inspection across local clones.

Supplies the raw material for task-progress matching: which branches exist, who
authored them, what they changed, and what currently exists on the integration
branches. Knows nothing about hyperspace or work items.

DESIGN NOTES (see WI-187)

Batched, not per-branch. Enumerating 125 branches with one `git log -1` each
cost 4,875 ms; `for-each-ref` plus `branch -r --merged` gets the same data in
two process spawns and 172 ms. Never loop git invocations over branches for
data these two calls already return.

Two evidence sources, because branch diffs alone are insufficient. A fully
merged branch produces an empty three-dot diff, indistinguishable from "no work
started". So unmerged branches are diffed, and merged/landed work is read from
the integration branch's tree instead. Tree state also survives squash-merges,
which sever ancestry entirely and defeat any archaeology-based approach.

SAFETY

Every operation here is read-only against `origin/*` refs and safe to run with
uncommitted work present. `fetch` writes `.git` but never the working tree or
index, and only runs when explicitly requested.

This module must never run `checkout`, `switch`, or `restore`. `show <ref>:<path>`
and `diff a...b` give full content access with no working-tree involvement.
"""

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

# Integration branch, verified present in all tracked repos. Cannot be derived
# from origin/HEAD, which points at `main` in every repo.
DEFAULT_BASE = "dev"

# Promotion chain, cheapest to query in one pass alongside the base.
PROMOTION_REFS = ("dev", "qa", "main")

# Branches whose names are integration/release targets rather than work.
_NON_WORK_BRANCHES = {"main", "master", "dev", "develop", "qa", "HEAD"}

# Default relevance window for unmerged branches. Not a cost mitigation — the
# merged/unmerged split already removes ~72% of branches from diffing — so this
# can be widened freely at ~42 ms per additional branch.
DEFAULT_MAX_AGE_DAYS = 30

_FETCH_TIMEOUT = 25
_GIT_TIMEOUT = 30

# Suppress console windows when running under pythonw, matching the pattern in
# tools/ado_collector.py. Without this every git call flashes a cmd window.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform.startswith("win") else 0


class GitEvidenceError(Exception):
    """Raised when a git operation fails in a way the caller should surface."""


# ---------------------------------------------------------------------------
# Process plumbing
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str, timeout: int = _GIT_TIMEOUT, check: bool = True) -> str:
    """Run a read-only git command in `repo` and return stdout.

    Returns "" on failure when check=False, so callers can treat a missing ref
    as absence rather than an error.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=timeout,
            creationflags=_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as e:
        raise GitEvidenceError(f"git {' '.join(args)} timed out in {repo.name}") from e
    except OSError as e:
        raise GitEvidenceError(f"git unavailable: {e}") from e

    if proc.returncode != 0:
        if check:
            raise GitEvidenceError(
                f"git {' '.join(args)} failed in {repo.name}: {proc.stderr.strip()[:200]}"
            )
        return ""
    return proc.stdout


def _git_ok(repo: Path, *args: str) -> bool:
    """True if the command exits 0. For existence probes like `cat-file -e`."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True, text=True, timeout=_GIT_TIMEOUT,
            creationflags=_NO_WINDOW,
        )
        return proc.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


# ---------------------------------------------------------------------------
# Repo discovery
# ---------------------------------------------------------------------------

def discover_repos(workspace_root: Path) -> dict[str, Path]:
    """Map repo name -> path for every git clone directly under workspace_root.

    Work items reference files as "{repo-name}/path/to/file", so the repo name
    in a claim is the key into this map. No configuration is required.
    """
    repos = {}
    for child in sorted(workspace_root.iterdir()):
        if child.is_dir() and (child / ".git").exists():
            repos[child.name] = child
    return repos


def base_branch(repo: Path, preferred: str = DEFAULT_BASE) -> str:
    """Resolve the integration branch for a repo.

    Prefers `dev` (present in every tracked repo). Falls back to origin/HEAD's
    target only when `dev` is absent, since origin/HEAD points at `main`
    everywhere and is therefore useless as the primary signal.
    """
    if _git_ok(repo, "rev-parse", "--verify", "--quiet", f"origin/{preferred}"):
        return preferred
    head = _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", check=False).strip()
    if head:
        return head.rsplit("/", 1)[-1]
    return preferred


def fetch_age_hours(repo: Path) -> float | None:
    """Hours since the last fetch, from FETCH_HEAD's mtime. None if never fetched."""
    fh = repo / ".git" / "FETCH_HEAD"
    if not fh.exists():
        return None
    delta = datetime.now(timezone.utc) - datetime.fromtimestamp(fh.stat().st_mtime, timezone.utc)
    return round(delta.total_seconds() / 3600, 1)


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def fetch_repos(repos: list[Path], timeout: int = _FETCH_TIMEOUT) -> dict[str, dict]:
    """Fetch several repos in parallel.

    Cost is round-trip bound rather than data bound (~1.0-1.7 s per repo; 14 days
    of staleness added only ~670 ms over warm), so parallelism is nearly free.

    Credentials come from a git helper. If that cache ever expires, a fetch under
    pythonw could block on an invisible prompt — hence the hard timeout and the
    explicit failure result rather than waiting.
    """
    results: dict[str, dict] = {}
    if not repos:
        return results

    def _one(repo: Path) -> tuple[str, dict]:
        try:
            subprocess.run(
                ["git", "-C", str(repo), "fetch", "origin"],
                capture_output=True, text=True, timeout=timeout,
                creationflags=_NO_WINDOW,
            )
            return repo.name, {"ok": True}
        except subprocess.TimeoutExpired:
            return repo.name, {
                "ok": False,
                "error": f"fetch timed out after {timeout}s — credentials may need refreshing",
            }
        except OSError as e:
            return repo.name, {"ok": False, "error": str(e)}

    with ThreadPoolExecutor(max_workers=min(len(repos), 6)) as pool:
        futures = [pool.submit(_one, r) for r in repos]
        for fut in as_completed(futures):
            name, res = fut.result()
            results[name] = res
    return results


# ---------------------------------------------------------------------------
# Branch enumeration (batched)
# ---------------------------------------------------------------------------

def list_branches(repo: Path, base: str | None = None,
                  max_age_days: int | None = DEFAULT_MAX_AGE_DAYS) -> list[dict]:
    """Enumerate remote branches with author, date, and merged status.

    Two process spawns total, regardless of branch count:
      1. for-each-ref  -> name, author, committer date
      2. branch --merged -> the merged set

    Returns dicts: {name, short, author, prefix, date, age_days, merged}.
    `short` strips the "origin/" prefix; `prefix` is the "mk" in "mk/foo" when
    present, which corroborates authorship independently of commit metadata.
    """
    base = base or base_branch(repo)

    raw = _git(
        repo, "for-each-ref",
        "--format=%(refname:short)|%(authorname)|%(committerdate:iso8601)",
        "refs/remotes/origin",
    )
    merged_raw = _git(
        repo, "branch", "-r", "--merged", f"origin/{base}",
        "--format=%(refname:short)", check=False,
    )
    merged = {l.strip() for l in merged_raw.splitlines() if l.strip()}

    now = datetime.now(timezone.utc)
    out = []
    for line in raw.splitlines():
        parts = line.split("|")
        if len(parts) < 3:
            continue
        name, author, date_s = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not name or name == "origin":
            continue
        short = name[len("origin/"):] if name.startswith("origin/") else name
        if short in _NON_WORK_BRANCHES or short.startswith("HEAD"):
            continue

        age_days = None
        if date_s:
            try:
                age_days = round((now - datetime.fromisoformat(date_s)).total_seconds() / 86400, 1)
            except ValueError:
                pass

        if max_age_days is not None and age_days is not None and age_days > max_age_days:
            continue

        out.append({
            "name": name,
            "short": short,
            "author": author,
            "prefix": short.split("/", 1)[0].lower() if "/" in short else None,
            "date": date_s,
            "age_days": age_days,
            "merged": name in merged,
        })

    out.sort(key=lambda b: b["date"], reverse=True)
    return out


# ---------------------------------------------------------------------------
# Evidence source A — unmerged branch diffs
# ---------------------------------------------------------------------------

def diff_evidence(repo: Path, branch: str, base: str | None = None) -> list[dict]:
    """File-level changes a branch introduces relative to `base`.

    Rename detection is on by default, and rename records are preserved as a
    single entry carrying both paths. That matters: a rename record proves a
    "move X to Y" task outright, where the same change read as separate add and
    delete entries proves nothing on its own.

    Returns dicts: {path, change_type, old_path}. change_type is one of
    A(dd) M(odify) D(elete) R(ename) C(opy) T(ype-change).
    """
    base = base or base_branch(repo)
    raw = _git(
        repo, "diff", "--name-status", "--find-renames",
        f"origin/{base}...{branch}", check=False,
    )

    out = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        fields = line.split("\t")
        status = fields[0].strip()
        kind = status[0]
        if kind in ("R", "C") and len(fields) >= 3:
            out.append({"path": fields[2].strip(), "change_type": kind, "old_path": fields[1].strip()})
        elif len(fields) >= 2:
            out.append({"path": fields[1].strip(), "change_type": kind, "old_path": None})
    return out


# ---------------------------------------------------------------------------
# Evidence source B — integration branch tree state
# ---------------------------------------------------------------------------

def tree_evidence(repo: Path, paths: list[str],
                  refs: tuple[str, ...] = PROMOTION_REFS) -> dict[str, dict]:
    """Whether each path exists on each promotion ref.

    This is how merged and removed work is detected. An attempt to recover
    merged-branch evidence via merge-base was abandoned: for a fully merged
    branch the merge-base *is* the branch tip, so the diff is empty by
    construction. Reading the integration tree sidesteps that and additionally
    survives squash-merges.

    Returns {path: {<ref>: bool, ..., "tier_present": str|None, "tier_absent": str|None}}.

    Two tiers, because promotion means opposite things for additions and
    removals and a single field misreports one of them. Observed live on
    `lambdas/get_monitoring.py`: absent on dev, present on qa and main. As an
    addition that would read "shipped to main"; in reality it is a *removal*
    that has only reached dev. So:

      tier_present — furthest ref where the path exists. Meaningful for
                     "add X" tasks: how far the addition has shipped.
      tier_absent  — furthest ref where the path is gone. Meaningful for
                     "remove X" tasks: how far the removal has shipped.

    The caller picks based on the task's verb; this layer does not guess intent.
    """
    out: dict[str, dict] = {}
    available = [r for r in refs if _git_ok(repo, "rev-parse", "--verify", "--quiet", f"origin/{r}")]

    for path in paths:
        presence = {r: _git_ok(repo, "cat-file", "-e", f"origin/{r}:{path}") for r in available}

        tier_present = None
        tier_absent = None
        # Walk main -> qa -> dev so the first hit is the furthest-promoted ref.
        for r in reversed(available):
            if tier_present is None and presence.get(r):
                tier_present = r
            if tier_absent is None and not presence.get(r):
                tier_absent = r

        out[path] = {**presence, "tier_present": tier_present, "tier_absent": tier_absent}
    return out


def find_by_basename(repo: Path, ref: str, basename: str) -> list[str]:
    """Every path on `ref` whose filename matches `basename`.

    Needed because a task's stated path and the path the work actually landed at
    frequently differ. WI-180 specified `api/permissions/migration_utils.py`; the
    file landed at `api/portal_api/migration_utils.py`. A literal path check
    reports it missing and the task gets marked incomplete, which is exactly the
    error this exists to prevent.
    """
    raw = _git(repo, "ls-tree", "-r", "--name-only", f"origin/{ref}", check=False)
    target = basename.lower()
    return [p for p in raw.splitlines() if p.rsplit("/", 1)[-1].lower() == target]


def file_contains(repo: Path, ref: str, path: str, needles: list[str]) -> list[str]:
    """Which of `needles` appear in a file's content at `ref`.

    Confirms a symbol actually lives in a relocated file, rather than trusting a
    filename match alone.
    """
    raw = _git(repo, "show", f"origin/{ref}:{path}", check=False)
    if not raw:
        return []
    return [n for n in needles if n in raw]
