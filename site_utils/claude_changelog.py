"""Claude Code release notes for the changelog viewer.

Fetches the upstream CHANGELOG.md, parses it into the same version-block shape
the kiro archive uses, and keeps the last good copy on disk so the viewer still
works offline. Independent of hyperagent's helpers to preserve app decoupling.
"""

import json
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

from site_utils.config import DATA_DIR

CLAUDE_CHANGELOG_URL = "https://raw.githubusercontent.com/anthropics/claude-code/main/CHANGELOG.md"
CLAUDE_CHANGELOG_CACHE_FILE = DATA_DIR / "claude-changelog.json"

_HEADER_RE = re.compile(r"^##\s+(\d+\.\d+\.\d+)\s*$")
# Leading verb -> display category; unlisted verbs keep their text under Changed.
_VERB_TYPES = {
    "Added": "Added", "Fixed": "Fixed", "Changed": "Changed", "Security": "Security",
    "Deprecated": "Deprecated", "Improved": "Changed", "Updated": "Changed",
    "Removed": "Deprecated",
}
_STRIPPED_VERBS = ("Added", "Fixed", "Changed", "Security", "Deprecated")


def version_key(version):
    """Sortable tuple for a dotted version string; () when unparsable."""
    try:
        return tuple(int(part) for part in version.split("."))
    except (ValueError, AttributeError):
        return ()


def parse_claude_changelog(text):
    """Parse CHANGELOG.md into version blocks, newest-first (date is None)."""
    blocks = []
    current = None
    for line in text.splitlines():
        header = _HEADER_RE.match(line)
        if header:
            current = {"version": header.group(1), "date": None, "entries": []}
            blocks.append(current)
            continue
        if current is None or not line.startswith("- "):
            continue
        body = line[2:].strip()
        verb = body.split(" ", 1)[0]
        if verb in _STRIPPED_VERBS:
            body = body[len(verb):].strip()
        current["entries"].append(
            {"type": _VERB_TYPES.get(verb, "Changed"), "tag": None, "text": body})
    return blocks


def _read_cache():
    try:
        data = json.loads(CLAUDE_CHANGELOG_CACHE_FILE.read_text(encoding="utf-8"))
        return data.get("versions", []) if isinstance(data, dict) else []
    except (OSError, ValueError):
        return []


def load_claude_changelog():
    """Return (versions, source): fetched live, else the cached copy, else empty.

    A successful fetch rewrites the cache; a failed one falls back to it.
    """
    try:
        request = urllib.request.Request(
            CLAUDE_CHANGELOG_URL, headers={"User-Agent": "hypervisor"})
        with urllib.request.urlopen(request, timeout=8) as response:
            blocks = parse_claude_changelog(response.read().decode("utf-8"))
    except Exception:
        blocks = []
    if blocks:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            CLAUDE_CHANGELOG_CACHE_FILE.write_text(json.dumps({
                "captured": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "versions": blocks,
            }, indent=2), encoding="utf-8")
        except OSError:
            pass
        return blocks, "live"
    cached = _read_cache()
    return cached, ("cache" if cached else "empty")


def _find_claude_cli():
    cli = shutil.which("claude")
    if cli:
        return cli
    fallback = Path(os.environ.get("USERPROFILE", "")) / ".local" / "bin" / "claude.exe"
    return str(fallback) if fallback.exists() else None


def update_claude_cli():
    """Run `claude update`. Returns {ok, version, output} (output is the tail)."""
    cli = _find_claude_cli()
    if not cli:
        return {"ok": False, "version": None, "output": "claude CLI not found."}
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        proc = subprocess.run([cli, "update"], capture_output=True, text=True,
                              timeout=300, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "version": None, "output": str(e)}
    output = ((proc.stdout or "") + (proc.stderr or "")).strip()[-500:]
    return {"ok": proc.returncode == 0, "version": installed_claude_version(), "output": output}


def installed_claude_version():
    """Version reported by the local `claude` CLI, or None."""
    cli = _find_claude_cli()
    if not cli:
        return None
    flags = 0x08000000 if os.name == "nt" else 0
    try:
        proc = subprocess.run([cli, "--version"], capture_output=True, text=True,
                              timeout=10, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired):
        return None
    match = re.search(r"\d+\.\d+\.\d+", proc.stdout or "")
    return match.group(0) if match else None
