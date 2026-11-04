"""Pure LAN access decision for the Hypervisor asset route.

Given the request facts, decide whether to serve, deny, or 404, and whether
to plant the auth cookie. The route owns logging, cookies and responses.
"""

import os
from dataclasses import dataclass
from typing import Optional

SHARE_DIRS = {"context"}

ALLOW = "allow"
OFFLINE_PAGE = "offline_page"
INVALID_PAGE = "invalid_page"
FORBIDDEN = "forbidden"
NOT_FOUND = "not_found"
SEARCH = "search"

STATIC_EXTS = {'.js', '.css', '.json', '.ico', '.png', '.jpg',
               '.svg', '.woff', '.woff2', '.ttf', '.map'}
HOME_REWRITES = ('content/home.json', 'content/_index.json', 'content/_pins.json')


@dataclass
class LanDecision:
    action: str = ALLOW
    path: str = ""
    # Cookie value to plant on the served file response (valid ?key= present).
    plant_cookie: Optional[str] = None
    # True when the global response should also carry the cookie (content path).
    cookie_on_response: bool = False
    key_accepted: bool = False
    log_level: Optional[str] = None
    # %-format with the remote address first, then the path when log_with_path.
    log_fmt: str = ""
    log_with_path: bool = False


def lan_blocks_path(url_path: str) -> bool:
    """True if a LAN request for this path must be blocked.

    Only content fragments (`content/<doc-path>.json`) are gated; a fragment is
    blocked when its first segment is not in SHARE_DIRS.
    """
    p = url_path.lstrip("/").replace("\\", "/")
    prefix = "content/"
    if not p.startswith(prefix):
        return False
    rest = p[len(prefix):]
    if not rest.endswith(".json"):
        return False
    top = rest.split("/", 1)[0]
    top = top[:-5] if top.endswith(".json") else top
    return top not in SHARE_DIRS


def decide_lan_access(is_local, path, query_key, cookie_key, configured_key) -> LanDecision:
    """Return the access decision for one request."""
    d = LanDecision(path=path)
    if is_local:
        return d

    norm = path.lstrip('/').replace('\\', '/')
    cfg = configured_key
    if cfg and query_key == cfg:
        d.plant_cookie = cfg
        d.key_accepted = True

    is_content = norm.startswith('content/') and norm.endswith('.json')
    is_search = norm == 'search-index.json'
    is_404 = norm == 'content/404.json'

    if norm == 'nav-state.json':
        d.action = NOT_FOUND
        d.log_level, d.log_fmt = "warning", "BLOCK %s  nav-state.json  (structure)"
        return d

    ext = os.path.splitext(norm)[1].lower()
    is_html_nav = not is_content and not is_search and ext not in STATIC_EXTS
    supplied = query_key or cookie_key

    if is_html_nav:
        if not cfg:
            d.action = OFFLINE_PAGE
            d.log_level, d.log_fmt = "info", "OFFLINE  %s  (sharing disabled)"
        elif supplied != cfg:
            d.action = INVALID_PAGE
            d.log_level, d.log_fmt = "warning", "INVALID  %s  (bad/no code on nav)"
        return d

    if (is_content or is_search) and not is_404:
        d.log_with_path = True
        if not cfg:
            d.action = FORBIDDEN
            d.log_level, d.log_fmt = "info", "DENY  %s  %s  (sharing disabled - no key set)"
            return d
        if supplied != cfg:
            d.action = FORBIDDEN
            if supplied:
                d.log_level, d.log_fmt = "warning", "DENY  %s  %s  (invalid key)"
            else:
                d.log_level, d.log_fmt = "info", "DENY  %s  %s  (no key)"
            return d
        if query_key == cfg:
            d.cookie_on_response = True
        if norm in HOME_REWRITES:
            d.path = norm = 'content/context.json'
        if is_search:
            d.action = SEARCH
            d.log_level, d.log_fmt = "debug", "OK    %s  search-index.json (filtered)"
            d.log_with_path = False
            return d
        if lan_blocks_path(d.path):
            d.action = NOT_FOUND
            d.log_level, d.log_fmt = "warning", "BLOCK %s  %s  (outside allowlist)"
            return d
        d.log_level, d.log_fmt = "debug", "OK    %s  %s"
    return d
