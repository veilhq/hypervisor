"""
Hypervisor Desktop App launcher.

Starts hypervisor-app.py as a detached subprocess if not already running.
"""

import subprocess
import sys
from pathlib import Path

from .config import CONFIG_DIR


_APP_LOCK = CONFIG_DIR / ".app_running"
_APP_SCRIPT = CONFIG_DIR / "hypervisor-app.py"


def launch_hypervisor() -> dict:
    """Launch the Hypervisor desktop app if it isn't already running.

    Returns:
        Dict with status and message.
    """
    # Check if already running via the lock file the app creates on startup
    if _APP_LOCK.exists():
        try:
            pid = int(_APP_LOCK.read_text(encoding="utf-8").strip())
            # Verify the process is actually alive (Windows-compatible)
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return {
                    "status": "already_running",
                    "message": f"Hypervisor desktop app is already running (PID {pid}).",
                }
            # Lock file is stale — process no longer exists
            _APP_LOCK.unlink(missing_ok=True)
        except (ValueError, OSError):
            # Corrupt lock file — remove it and proceed with launch
            _APP_LOCK.unlink(missing_ok=True)

    # Launch the app as a detached subprocess
    python = sys.executable
    try:
        proc = subprocess.Popen(
            [python, str(_APP_SCRIPT)],
            cwd=str(CONFIG_DIR),
            # Detach from parent — app runs independently
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return {
            "status": "launched",
            "message": f"Hypervisor desktop app launched (PID {proc.pid}). Site build runs automatically on startup.",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to launch Hypervisor: {e}",
        }
