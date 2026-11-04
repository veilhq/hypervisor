"""LAN access decision tests.

Run from the .hypervisor directory:
    python -m unittest tests.test_lan_access -v
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from site_utils.lan_access import (  # noqa: E402
    ALLOW, FORBIDDEN, INVALID_PAGE, NOT_FOUND, OFFLINE_PAGE, SEARCH,
    decide_lan_access,
)

KEY = "sesame"


def decide(path, query="", cookie="", cfg=KEY, local=False):
    return decide_lan_access(local, path, query, cookie, cfg)


class LocalRequestTests(unittest.TestCase):
    def test_local_always_allowed(self):
        d = decide("content/work-items/x.json", local=True, cfg="")
        self.assertEqual(d.action, ALLOW)
        self.assertIsNone(d.plant_cookie)
        self.assertEqual(d.path, "content/work-items/x.json")


class NoKeyConfiguredTests(unittest.TestCase):
    def test_nav_page_offline(self):
        self.assertEqual(decide("", cfg="").action, OFFLINE_PAGE)

    def test_content_forbidden(self):
        d = decide("content/context/a.json", cfg="")
        self.assertEqual(d.action, FORBIDDEN)
        self.assertEqual(d.log_level, "info")

    def test_static_still_served(self):
        self.assertEqual(decide("app.js", cfg="").action, ALLOW)


class KeyTests(unittest.TestCase):
    def test_wrong_key_nav_invalid(self):
        self.assertEqual(decide("", query="nope").action, INVALID_PAGE)

    def test_wrong_key_content_forbidden_warning(self):
        d = decide("content/context/a.json", query="nope")
        self.assertEqual(d.action, FORBIDDEN)
        self.assertEqual(d.log_level, "warning")

    def test_no_key_content_forbidden_info(self):
        d = decide("content/context/a.json")
        self.assertEqual(d.action, FORBIDDEN)
        self.assertEqual(d.log_level, "info")

    def test_valid_key_plants_cookie_on_shell(self):
        d = decide("", query=KEY)
        self.assertEqual(d.action, ALLOW)
        self.assertEqual(d.plant_cookie, KEY)
        self.assertTrue(d.key_accepted)

    def test_cookie_key_authorizes_without_planting(self):
        d = decide("content/context/a.json", cookie=KEY)
        self.assertEqual(d.action, ALLOW)
        self.assertIsNone(d.plant_cookie)
        self.assertFalse(d.cookie_on_response)

    def test_valid_query_key_on_content_sets_response_cookie(self):
        d = decide("content/context/a.json", query=KEY)
        self.assertEqual(d.action, ALLOW)
        self.assertTrue(d.cookie_on_response)


class PathTests(unittest.TestCase):
    def test_nav_state_blocked_even_with_key(self):
        self.assertEqual(decide("nav-state.json", cookie=KEY).action, NOT_FOUND)

    def test_content_outside_allowlist_404(self):
        d = decide("content/work-items/x.json", cookie=KEY)
        self.assertEqual(d.action, NOT_FOUND)

    def test_home_rewritten_to_context(self):
        d = decide("content/home.json", cookie=KEY)
        self.assertEqual(d.action, ALLOW)
        self.assertEqual(d.path, "content/context.json")

    def test_404_fragment_needs_no_key(self):
        self.assertEqual(decide("content/404.json").action, ALLOW)

    def test_search_index_needs_key_and_is_filtered(self):
        self.assertEqual(decide("search-index.json").action, FORBIDDEN)
        self.assertEqual(decide("search-index.json", cookie=KEY).action, SEARCH)

    def test_static_extension_no_key(self):
        for p in ("style.css", "fonts/a.woff2", "img/x.png"):
            self.assertEqual(decide(p).action, ALLOW, p)


if __name__ == "__main__":
    unittest.main()
