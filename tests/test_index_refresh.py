"""Index build, path-keyed store, and watcher debounce tests."""

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hv_mcp import backlinks, index  # noqa: E402


class PathIndexTests(unittest.TestCase):
    def test_put_replaces_and_moves_to_end(self):
        store = index._PathIndex([{"path": "a.md"}, {"path": "b.md"}])
        store.put({"path": "a.md", "v": 2})
        self.assertEqual([e["path"] for e in store], ["b.md", "a.md"])
        self.assertEqual(store.get("a.md")["v"], 2)
        self.assertEqual(len(store), 2)

    def test_discard_and_snapshot_iteration(self):
        store = index._PathIndex([{"path": "a.md"}, {"path": "b.md"}])
        for entry in store:
            store.discard(entry["path"])
        self.assertFalse(store)
        self.assertIsNone(store.get("a.md"))


class WorkIdLookupTests(unittest.TestCase):
    def test_lookup_is_case_insensitive_and_tracks_put(self):
        store = index._PathIndex([{"path": "a.md", "work_id": "ID-A"}, {"path": "b.md"}])
        self.assertEqual(store.get_by_work_id("id-a")["path"], "a.md")
        self.assertIsNone(store.get_by_work_id("ID-B"))
        self.assertIsNone(store.get_by_work_id(None))
        store.put({"path": "a.md", "work_id": "ID-B"})
        self.assertIsNone(store.get_by_work_id("ID-A"))
        self.assertEqual(store.get_by_work_id("ID-B")["path"], "a.md")

    def test_discard_and_duplicate_ids_follow_iteration_order(self):
        store = index._PathIndex([
            {"path": "a.md", "work_id": "ID-C"},
            {"path": "b.md", "work_id": "ID-C"},
        ])
        self.assertEqual(store.get_by_work_id("ID-C")["path"], "a.md")
        store.put({"path": "a.md", "work_id": "ID-C"})
        self.assertEqual(store.get_by_work_id("ID-C")["path"], "b.md")
        store.discard("b.md")
        self.assertEqual(store.get_by_work_id("ID-C")["path"], "a.md")
        store.discard("a.md")
        self.assertIsNone(store.get_by_work_id("ID-C"))
        self.assertEqual(store._by_work_id, {})

    def test_matches_linear_scan_on_real_index(self):
        index.rebuild_index()
        for entry in index._index:
            work_id = entry.get("work_id")
            if not work_id:
                continue
            expected = next(e for e in index._index if (e.get("work_id") or "").upper() == work_id.upper())
            self.assertIs(index._index.get_by_work_id(work_id.lower()), expected)


class RebuildRaceTests(unittest.TestCase):
    """A refresh or removal landing mid-rebuild must survive the swap."""

    def setUp(self):
        self.contents = {
            "a.md": "# A\n\n- ID: WI-1\n\n[b](b.md)\n",
            "b.md": "# B\n",
            "c.md": "# C\n\n[a](a.md)\n",
        }
        self.reading_c = threading.Event()
        self.release_c = threading.Event()

    def tearDown(self):
        index.rebuild_index()

    def _fake_read(self, rel):
        rel_str = str(rel).replace("\\", "/")
        if rel_str == "c.md" and threading.current_thread().name == "rebuild":
            self.reading_c.set()
            self.release_c.wait(5)
        return self.contents.get(rel_str)

    def _run_with_midway(self, midway):
        from unittest import mock
        files = [Path("a.md"), Path("b.md"), Path("c.md")]
        with mock.patch.object(index, "collect_files", lambda root: files), \
                mock.patch.object(index, "_read_doc", self._fake_read):
            worker = threading.Thread(target=index.rebuild_index, name="rebuild")
            worker.start()
            self.assertTrue(self.reading_c.wait(5))
            midway()
            self.release_c.set()
            worker.join(5)
            self.assertFalse(worker.is_alive())

    def test_refresh_during_rebuild_is_kept(self):
        def midway():
            self.contents["a.md"] = "# A2\n\n- ID: WI-2\n"
            index.refresh_single("a.md")

        self._run_with_midway(midway)
        self.assertEqual(index._index.get("a.md")["title"], "A2")
        self.assertIsNone(index._index.get_by_work_id("WI-1"))
        self.assertEqual(index._index.get_by_work_id("WI-2")["path"], "a.md")
        self.assertEqual(backlinks._outlinks.get("a.md"), set())
        self.assertNotIn("b.md", backlinks._backlinks)
        self.assertIsNone(index._rebuild_touched)

    def test_removal_during_rebuild_is_kept(self):
        def midway():
            del self.contents["a.md"]
            index.remove_from_index("a.md")

        self._run_with_midway(midway)
        self.assertIsNone(index._index.get("a.md"))
        self.assertIsNone(index._index.get_by_work_id("WI-1"))
        self.assertNotIn("a.md", backlinks._outlinks)
        self.assertEqual(len(index._index), 2)

    def test_refresh_outside_rebuild_is_not_tracked(self):
        from unittest import mock
        with mock.patch.object(index, "_read_doc", self._fake_read):
            index.refresh_single("b.md")
        self.assertIsNone(index._rebuild_touched)


class SinglePassRebuildTests(unittest.TestCase):
    def test_one_pass_matches_backlink_rebuild(self):
        index.rebuild_index()
        one_pass = {k: set(v) for k, v in backlinks._outlinks.items()}
        back_one = {k: set(v) for k, v in backlinks._backlinks.items()}
        backlinks.rebuild_backlinks()
        self.assertEqual(one_pass, backlinks._outlinks)
        self.assertEqual(back_one, backlinks._backlinks)
        self.assertEqual(len(list(index._index)), len({e["path"] for e in index._index}))

    def test_refresh_and_remove_roundtrip(self):
        index.rebuild_index()
        entry = next(iter(index._index))
        before = len(index._index)
        index.refresh_single(entry["path"])
        self.assertEqual(len(index._index), before)
        self.assertEqual(index._index.get(entry["path"])["title"], entry["title"])
        index.remove_from_index(entry["path"])
        self.assertEqual(len(index._index), before - 1)
        index.refresh_single(entry["path"])
        self.assertEqual(len(index._index), before)


class WatcherDebounceTests(unittest.TestCase):
    def test_burst_refreshes_each_path_once(self):
        try:
            import watchdog  # noqa: F401
        except ImportError:
            self.skipTest("watchdog not installed")
        from unittest import mock
        from watchdog.events import FileModifiedEvent

        captured = {}

        class _FakeObserver:
            daemon = False

            def schedule(self, handler, *a, **k):
                captured["handler"] = handler

            def start(self):
                pass

        calls = []
        done = threading.Event()

        def fake_refresh(rel):
            calls.append(rel)
            done.set()

        index._watcher_started = False
        try:
            with mock.patch("watchdog.observers.Observer", _FakeObserver), \
                    mock.patch.object(index, "refresh_single", fake_refresh), \
                    mock.patch("hv_mcp.rag.on_file_changed", lambda rel: None):
                index.start_watcher()
                handler = captured["handler"]
                path = str(index.HYPERSPACE_ROOT / "notes" / "x.md")
                for _ in range(5):
                    handler.on_modified(FileModifiedEvent(path))
                done.wait(2)
                time.sleep(0.4)
        finally:
            index._watcher_started = False
        self.assertEqual(calls, ["notes/x.md"])


if __name__ == "__main__":
    unittest.main()
