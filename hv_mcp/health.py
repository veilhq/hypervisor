"""
Health history — persists validation snapshots for trend tracking.

Stores snapshots in .hypervisor/state/health-history.json. Each entry records:
- timestamp
- total documents
- valid count
- violation count
- top issues

Used by health_report to compare current vs previous state and compute trends.
"""

import json
from datetime import datetime
from pathlib import Path

from .config import STATE_DIR

HEALTH_HISTORY_FILE = STATE_DIR / "health-history.json"
MAX_HISTORY_ENTRIES = 50  # Keep last 50 snapshots


def _load_history() -> list[dict]:
    """Load health history from disk."""
    if HEALTH_HISTORY_FILE.exists():
        try:
            return json.loads(HEALTH_HISTORY_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []


def _save_history(history: list[dict]):
    """Persist health history to disk."""
    HEALTH_HISTORY_FILE.write_text(
        json.dumps(history, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def record_health_snapshot(validation_result: dict):
    """Append a validation snapshot to the health history.

    Args:
        validation_result: The output of validate_all() — must contain
                          'total_documents', 'valid', 'violations', 'top_issues'.
    """
    history = _load_history()

    snapshot = {
        "timestamp": datetime.now().strftime("%Y-%m-%dT%H:%M"),
        "total_documents": validation_result.get("total_documents", 0),
        "valid": validation_result.get("valid", 0),
        "violations": validation_result.get("violations", 0),
        "top_issues": validation_result.get("top_issues", [])[:5],  # Keep top 5
    }

    history.append(snapshot)

    # Trim to max entries
    if len(history) > MAX_HISTORY_ENTRIES:
        history = history[-MAX_HISTORY_ENTRIES:]

    _save_history(history)


def get_latest_snapshot() -> dict | None:
    """Get the most recent health snapshot (for comparison)."""
    history = _load_history()
    return history[-1] if history else None


def get_previous_snapshot() -> dict | None:
    """Get the second-most-recent snapshot (for trend calculation)."""
    history = _load_history()
    return history[-2] if len(history) >= 2 else None


def get_history(limit: int = 10) -> list[dict]:
    """Get the most recent N snapshots."""
    history = _load_history()
    return history[-limit:]
