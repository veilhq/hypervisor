"""
Date parsing utility for age/staleness calculations.
"""

from datetime import datetime


def parse_date(date_str: str | None) -> datetime | None:
    """Parse a YYYY-MM-DDTHH:MM or YYYY-MM-DD date string into a datetime.

    Returns None if the input is None or unparseable.
    """
    if not date_str:
        return None

    # Try full format first: 2026-06-09T11:30
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%dT%H:%M")
    except ValueError:
        pass

    # Fallback: date only: 2026-06-09
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except ValueError:
        pass

    return None


def days_since(date_str: str | None) -> int | None:
    """Calculate the number of days between a date string and now.

    Returns None if the date is unparseable.
    """
    dt = parse_date(date_str)
    if dt is None:
        return None
    delta = datetime.now() - dt
    return delta.days


def best_activity_date(entry: dict) -> str | None:
    """Get the most recent activity date from an index entry (updated > created)."""
    return entry.get("updated") or entry.get("created")
