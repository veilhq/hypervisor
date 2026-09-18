"""
Range Bridge — cyber-portal range monitoring data for the Hypervisor desktop app.

Mirrors ado_bridge.py: standalone functions returning dicts suitable for pushing
to the frontend via the PyWebView bridge. Consumes the existing staff-authenticated
REST endpoint (GET /api/logs/analytics/range-monitoring/) — no new backend, no infra.

Auth model: the operator pastes their portal `access_token` (a JWT cookie the portal
sets with httponly=False, so it is browser-copyable). We seed a module-level
requests.Session cookie jar with it. The portal's auth middleware performs sliding
refresh — an expired access_token with a still-valid session is re-issued via
Set-Cookie — so a persistent Session stays authenticated across polls for up to the
refresh window without re-pasting.

Token is held in memory only. It is never written to disk (it is a staff session
credential). Re-paste after an app restart.
"""

import sys
from pathlib import Path

_HYPERKIT_PYTHON = str(Path(__file__).parent.parent / ".hyperkit" / "python")
if _HYPERKIT_PYTHON not in sys.path:
    sys.path.insert(0, _HYPERKIT_PYTHON)

from hyper_logging import setup_logger  # noqa: E402

logger = setup_logger("hypervisor")

# Environment base URLs the operator can target. The dashboard sends one of these
# keys; the value is the origin the range-monitoring endpoint lives under.
BASE_URLS = {
    "dev": "https://dev.cyber.org",
    "qa": "https://qa.cyber.org",
    "prod": "https://portal.cyber.org",
}
_ENDPOINT_PATH = "/api/logs/analytics/range-monitoring/"
_SESSIONS_PATH = "/api/logs/analytics/active-sessions/"
_CLASSROOMS_PATH = "/api/logs/analytics/active-classrooms/"

# In-memory session state (never persisted to disk).
_state = {
    "session": None,   # requests.Session with the access_token cookie
    "base": "dev",     # selected environment key
}


def _get_requests():
    """Import requests lazily, matching ado_collector's optional-import posture."""
    try:
        import requests
        return requests
    except ImportError:
        return None


def set_range_token(token, base="dev"):
    """Seed the module-level session with the pasted portal access_token.

    Args:
        token: The portal `access_token` JWT cookie value (copied from the browser).
        base: Environment key — one of BASE_URLS ('dev', 'qa', 'prod').

    Returns:
        dict: {"ok": True} on success, or {"ok": False, "error": ...}.
    """
    requests = _get_requests()
    if requests is None:
        logger.error("range_bridge: 'requests' package not available")
        return {"ok": False, "error": "The 'requests' package is required."}

    token = (token or "").strip()
    if not token:
        return {"ok": False, "error": "Empty token."}
    if base not in BASE_URLS:
        return {"ok": False, "error": "Unknown environment: %s" % base}

    session = requests.Session()
    # Seed the Session cookie jar with the access_token, scoped to the target
    # host. Using the jar (not a static header) matters: the portal's auth
    # middleware re-issues a fresh token via Set-Cookie on each response, and
    # a Session jar captures that — keeping the session alive across the 30-min
    # access-token expiry up to the 10h refresh window.
    from urllib.parse import urlparse
    host = urlparse(BASE_URLS[base]).hostname
    session.cookies.set("access_token", token, domain=host, path="/")

    _state["session"] = session
    _state["base"] = base
    logger.info("range_bridge: session seeded for env=%s host=%s", base, host)
    return {"ok": True}


def clear_range_token():
    """Drop the in-memory session (e.g. on auth_expired or explicit disconnect)."""
    _state["session"] = None
    logger.info("range_bridge: session cleared")
    return {"ok": True}


def range_session_status():
    """Report whether a live session exists, without exposing the token.

    Lets the frontend restore the connected view after a page navigation or
    refresh — the session lives in this module for the life of the hypervisor
    process, so it survives page reloads (but not an app restart).

    Returns:
        dict: {"ok": True, "connected": bool, "base": <env key or None>}.
    """
    connected = _state.get("session") is not None
    return {"ok": True, "connected": connected,
            "base": _state.get("base") if connected else None}


def _fetch(path):
    """Shared GET against a portal analytics endpoint using the seeded session.

    Args:
        path: URL path under the selected environment base (e.g. _SESSIONS_PATH).

    Returns:
        dict: {"ok": True, "content": {...}} on success, or an error dict with a
        `reason` the frontend maps to a message:
          - no_token       — no session seeded yet (default/unauthenticated state)
          - auth_expired    — HTTP 401 (session no longer valid; re-paste needed)
          - network_error   — request failed to reach the host
          - server_error    — non-200/401, invalid JSON, or success=false w/o reason
        Plus the endpoint's own reasons (e.g. not_configured) passed through.
    """
    session = _state.get("session")
    if session is None:
        return {"ok": False, "reason": "no_token"}

    requests = _get_requests()
    if requests is None:
        return {"ok": False, "reason": "network_error", "error": "requests missing"}

    url = BASE_URLS[_state["base"]] + path
    try:
        resp = session.get(url, timeout=(5, 10))
    except requests.exceptions.RequestException as e:
        logger.warning("range_bridge: request failed (%s): %s", path, e)
        return {"ok": False, "reason": "network_error", "error": str(e)}

    ctype = resp.headers.get("Content-Type", "")
    redirected = resp.url != url
    body_snippet = (resp.text or "")[:300]

    if resp.status_code == 401:
        logger.info("range_bridge: 401 on %s — session expired", path)
        clear_range_token()
        return {"ok": False, "reason": "auth_expired"}

    if resp.status_code != 200:
        logger.warning(
            "range_bridge: unexpected status %s on %s (url=%s, redirected=%s, ctype=%s) body=%s",
            resp.status_code, path, resp.url, redirected, ctype, body_snippet
        )
        return {"ok": False, "reason": "server_error", "status": resp.status_code,
                "final_url": resp.url, "redirected": redirected, "body": body_snippet}

    try:
        data = resp.json()
    except ValueError as e:
        logger.warning(
            "range_bridge: bad JSON on %s (url=%s, redirected=%s, ctype=%s): %s | body=%s",
            path, resp.url, redirected, ctype, e, body_snippet
        )
        return {"ok": False, "reason": "server_error", "error": "invalid JSON",
                "final_url": resp.url, "redirected": redirected,
                "ctype": ctype, "body": body_snippet}

    if data.get("success"):
        return {"ok": True, "content": data.get("content", {})}
    logger.info("range_bridge: %s success=false reason=%s", path, data.get("reason"))
    return {"ok": False, "reason": data.get("reason", "server_error"),
            "message": data.get("message")}


def refresh_range():
    """Fetch range monitoring data (instances, participants, SGs, orphans)."""
    return _fetch(_ENDPOINT_PATH)


def refresh_sessions():
    """Fetch active session counts: {total, by_role: {role: count}}."""
    return _fetch(_SESSIONS_PATH)


def refresh_classrooms():
    """Fetch active classroom count: {total}."""
    return _fetch(_CLASSROOMS_PATH)
