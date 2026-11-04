"""similar_documents tests: semantic tiers and the Jaccard fallback.

Run from the .hypervisor directory:
    python -m unittest tests.test_similar_documents_rag -v

The RAG singleton is replaced by a stub that returns canned chunk hits, so no
embedding model or live database is involved.
"""

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hv_mcp import generation  # noqa: E402


def hit(path, title, sim, section="Overview", tags=None):
    return {
        "path": path, "title": title, "similarity": sim, "section": section,
        "doc_type": "work-item", "tags": tags or [],
    }


class StubRag:
    def __init__(self, hits=None, empty=False, fail=False):
        self._hits, self._empty, self._fail = hits or [], empty, fail

    def is_empty(self):
        return self._empty

    def search(self, query, top_k=5, **kwargs):
        if self._fail:
            raise RuntimeError("model unavailable")
        return self._hits


def run(stub, title="Add tag management UI"):
    with mock.patch("hv_mcp.rag.get_rag", return_value=stub):
        return generation.similar_documents(title, "Manage tags in the UI.")


class SimilarDocumentsTests(unittest.TestCase):
    def test_high_tier_is_likely_duplicate(self):
        out = run(StubRag([hit("a.md", "Tag management", 0.82)]))
        self.assertEqual(out["recommendation"], "likely_duplicate")
        self.assertEqual(out["similar"][0]["similarity"], "high")

    def test_medium_tier_is_review_existing(self):
        out = run(StubRag([hit("a.md", "Unrelated heading", 0.70)]))
        self.assertEqual(out["recommendation"], "review_existing")
        self.assertEqual(out["similar"][0]["similarity"], "medium")

    def test_low_tier_proceeds(self):
        out = run(StubRag([hit("a.md", "Something else", 0.60)]))
        self.assertEqual(out["recommendation"], "proceed")
        self.assertEqual(out["similar"][0]["similarity"], "low")

    def test_below_floor_is_dropped(self):
        out = run(StubRag([hit("a.md", "Something else", 0.40)]))
        self.assertNotIn("a.md", [s["path"] for s in out["similar"]])

    def test_title_match_lowers_high_threshold(self):
        out = run(StubRag([hit("a.md", "Add tag management UI", 0.73)]))
        self.assertEqual(out["similar"][0]["similarity"], "high")

    def test_aggregates_max_per_document(self):
        out = run(StubRag([hit("a.md", "Doc", 0.60), hit("a.md", "Doc", 0.80),
                           hit("b.md", "Other", 0.58)]))
        self.assertEqual([s["path"] for s in out["similar"]], ["a.md", "b.md"])
        self.assertEqual(out["similar"][0]["score"], 0.8)

    def test_keyword_only_hits_use_jaccard(self):
        stub = StubRag([hit("a.md", "Doc", 0.0)])
        fallback = {"similar": [], "recommendation": "proceed"}
        with mock.patch("hv_mcp.generation._similar_documents_jaccard",
                        return_value=fallback) as j:
            with mock.patch("hv_mcp.rag.get_rag", return_value=stub):
                generation.similar_documents("Anything", None)
        j.assert_called_once()

    def test_empty_index_uses_jaccard(self):
        sentinel = {"similar": [], "recommendation": "proceed", "tag": "jaccard"}
        with mock.patch("hv_mcp.generation._similar_documents_jaccard", return_value=sentinel):
            with mock.patch("hv_mcp.rag.get_rag", return_value=StubRag(empty=True)):
                out = generation.similar_documents("Anything at all", None)
        self.assertEqual(out, sentinel)

    def test_engine_error_uses_jaccard(self):
        sentinel = {"similar": [], "recommendation": "proceed", "tag": "jaccard"}
        with mock.patch("hv_mcp.generation._similar_documents_jaccard", return_value=sentinel):
            with mock.patch("hv_mcp.rag.get_rag", return_value=StubRag(fail=True)):
                out = generation.similar_documents("Anything at all", None)
        self.assertEqual(out, sentinel)

    def test_jaccard_path_runs_for_real(self):
        out = run(StubRag(empty=True))
        self.assertIn(out["recommendation"], ("proceed", "review_existing", "likely_duplicate"))
        self.assertIn("similar", out)

    def test_blank_title(self):
        self.assertEqual(generation.similar_documents("  ")["recommendation"], "proceed")


if __name__ == "__main__":
    unittest.main()
