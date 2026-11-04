"""
Git blame lookup for bug work items - resolves the repo that owns a file and
summarizes who last touched a line range.
"""

import logging
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT

logger = logging.getLogger(__name__)

_WORKSPACE_ROOT = HYPERSPACE_ROOT.parent
_GIT_TIMEOUT_SECONDS = 15
_MAX_COMMITS = 5
_UNCOMMITTED_SHA = "0" * 40
_RANGE_RE = re.compile(r'^\s*(\d+)(?:\s*-\s*(\d+))?\s*$')


def _find_repo_root(file_path: Path) -> Path | None:
    """Walk up from a file to the nearest directory containing .git."""
    for parent in file_path.parents:
        if (parent / ".git").exists():
            return parent
    return None


def _parse_line_range(lines: str | None) -> tuple[int, int] | None:
    """Parse '120' or '120-135' into an inclusive (start, end) pair."""
    if not lines:
        return None
    m = _RANGE_RE.match(str(lines))
    if not m:
        return None
    start = int(m.group(1))
    end = int(m.group(2) or start)
    if start < 1 or end < start:
        return None
    return start, end


def _parse_porcelain(output: str) -> list[dict]:
    """Collapse `git blame --porcelain` output into one record per commit."""
    commits: dict[str, dict] = {}
    current = None
    for line in output.splitlines():
        if line.startswith("\t"):
            continue
        header = re.match(r'^([0-9a-f]{40}) \d+ \d+', line)
        if header:
            current = header.group(1)
            commits.setdefault(current, {"sha": current})
            continue
        if current is None:
            continue
        key, _, value = line.partition(" ")
        if key == "author":
            commits[current]["author"] = value
        elif key == "author-time":
            commits[current]["time"] = int(value)
        elif key == "summary":
            commits[current]["summary"] = value
    return list(commits.values())


def _format_commit(commit: dict) -> str:
    """Render one commit as a markdown table row."""
    if commit["sha"] == _UNCOMMITTED_SHA:
        return "| uncommitted | - | - | Lines are modified in the working tree |"
    when = datetime.fromtimestamp(commit.get("time", 0), tz=timezone.utc).strftime("%Y-%m-%d")
    summary = commit.get("summary", "").replace("|", "\\|")
    author = commit.get("author", "unknown").replace("|", "\\|")
    return f"| `{commit['sha'][:8]}` | {author} | {when} | {summary} |"


def build_location_section(file: str | None, lines: str | None) -> str:
    """Return the body of a bug's Location section.

    Always returns text: a blame table when git can resolve the lines, or a
    one-line note saying why blame was unavailable.
    """
    if not file:
        return "Blame unavailable: no file or line range was given."

    parsed = _parse_line_range(lines)
    if parsed is None:
        return f"Blame unavailable for `{file}`: no valid line range was given."
    start, end = parsed

    path = Path(file)
    if not path.is_absolute():
        path = _WORKSPACE_ROOT / path
    path = path.resolve()
    label = f"`{file}` lines {start}-{end}" if end != start else f"`{file}` line {start}"

    if not path.is_file():
        return f"Blame unavailable: {label} does not exist."
    repo = _find_repo_root(path)
    if repo is None:
        return f"Blame unavailable: {label} is outside any git repository."

    cmd = [
        "git", "-C", str(repo), "blame", "--porcelain",
        "-L", f"{start},{end}", "--", str(path.relative_to(repo)),
    ]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=_GIT_TIMEOUT_SECONDS, creationflags=flags,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        logger.warning("git blame failed for %s: %s", file, e)
        return f"Blame unavailable: git could not be run for {label}."
    if result.returncode != 0:
        logger.warning("git blame exited %d for %s: %s", result.returncode, file, result.stderr.strip())
        return f"Blame unavailable: git could not blame {label} (the lines may be past the end of the file or the file is untracked)."

    commits = _parse_porcelain(result.stdout)
    if not commits:
        return f"Blame unavailable: git returned no commits for {label}."
    commits.sort(
        key=lambda c: float("inf") if c["sha"] == _UNCOMMITTED_SHA else c.get("time", 0),
        reverse=True,
    )

    out = [
        f"{label} in `{repo.name}`, as of creation. Most recent change first.",
        "",
        "| Commit | Author | Date | Summary |",
        "|--------|--------|------|---------|",
    ]
    out.extend(_format_commit(c) for c in commits[:_MAX_COMMITS])
    return "\n".join(out)
