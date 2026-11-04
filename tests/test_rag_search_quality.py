"""Search-quality tests for the RAG engine: rerank, ID lookup, stemming, schema.

Run from the .hypervisor directory:
    python -m unittest tests.test_rag_search_quality -v

Everything runs against a temp database with a tiny synthetic corpus. The
embedding model and cross-encoder are replaced by deterministic fakes so no
model is downloaded or loaded.
"""

import hashlib
import logging
import math
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hv_mcp import rag  # noqa: E402
from hv_mcp.rag import EMBEDDING_DIM, SCHEMA_VERSION, HyperspaceRAG, _serialize_f32  # noqa: E402

_saved_handlers: list = []


def setUpModule():
    _saved_handlers[:] = rag.logger.handlers
    rag.logger.handlers = [logging.NullHandler()]


def tearDownModule():
    rag.logger.handlers = list(_saved_handlers)


def _embed(text: str) -> list[float]:
    """Hashed bag-of-words vector, L2-normalized."""
    vec = [0.0] * EMBEDDING_DIM
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        idx = int(hashlib.md5(tok.encode()).hexdigest(), 16) % EMBEDDING_DIM
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


class FakeModel:
    def embed(self, texts, batch_size=1):
        return [_embed(t) for t in texts]

    def query_embed(self, texts):
        return [_embed(t) for t in texts]


class FakeReranker:
    """Logit +8 for docs containing the marker word, -8 otherwise."""

    def __init__(self, marker: str):
        self.marker = marker

    def rerank(self, query, docs):
        return [8.0 if self.marker in d.lower() else -8.0 for d in docs]


class RaisingReranker:
    def rerank(self, query, docs):
        raise RuntimeError("boom")


CORPUS = [
    ("a.md", "WI-101", "Deploy pipeline", "Overview", "How the deployment of the service works."),
    ("b.md", "WI-102", "Login rework", "Overview", "Sessions and password reset flow for users."),
    ("c.md", "WI-103", "Billing export", "Overview", "Monthly invoice export to csv for finance."),
    ("d.md", "WI-148", "Tag cleanup", "Details", "Merge duplicate tags and prune unused ones."),
]


def make_rag(tmp: Path) -> HyperspaceRAG:
    r = HyperspaceRAG(db_path=tmp / "rag.db")
    r._model = FakeModel()
    db = r.db
    for path, wid, title, section, body in CORPUS:
        cur = db.execute(
            "INSERT INTO chunks (path, title, section, content, doc_type, source_type,"
            " project, status, tags, updated, token_count)"
            " VALUES (?, ?, ?, ?, 'work-item', 'work', 'p', 'to-do', '[]', NULL, 10)",
            (path, title, section, body),
        )
        cid = cur.lastrowid
        db.execute(
            "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
            (cid, _serialize_f32(_embed(f"{title} {section} {body}"))),
        )
        db.execute(
            "INSERT INTO fts_chunks(rowid, title, section, content) VALUES (?, ?, ?, ?)",
            (cid, f"{wid} {title}", section, body),
        )
    db.commit()
    return r


class SearchQualityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="rag_quality_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.rag = make_rag(self.tmp)
        self.addCleanup(self.rag.close)

    def test_rerank_reorders_results(self):
        self.rag._reranker = FakeReranker("invoice")
        hits = self.rag.search("deployment of the service", top_k=4)
        self.assertEqual(hits[0]["path"], "c.md")
        self.assertGreater(hits[0]["rerank_score"], 0.9)
        self.assertEqual(hits[0]["confidence"], "high")

    def test_rerank_error_falls_back(self):
        self.rag._reranker = RaisingReranker()
        hits = self.rag.search("deployment of the service", top_k=4)
        self.assertEqual(hits[0]["path"], "a.md")
        self.assertTrue(all(h["rerank_score"] is None for h in hits))

    def test_reranker_unavailable_falls_back(self):
        self.rag._reranker_failed = True
        hits = self.rag.search("password reset", top_k=3)
        self.assertEqual(hits[0]["path"], "b.md")
        self.assertEqual(hits[0]["below_floor"], hits[0]["confidence"] == "low")

    def test_exact_id_lookup(self):
        self.rag._reranker = FakeReranker("invoice")
        hits = self.rag.search("wi-148", top_k=5)
        self.assertEqual(hits[0]["path"], "d.md")
        self.assertEqual([h["matched_by"] for h in hits].count("id"), 1)
        self.assertEqual(hits[0]["matched_by"], "id")
        self.assertEqual(hits[0]["confidence"], "high")

    def test_exact_id_accepts_a_label(self):
        self.rag._reranker = FakeReranker("invoice")
        for query in ("work item WI-148", "Story: WI-148", "ticket #WI-148"):
            hits = self.rag.search(query, top_k=5)
            self.assertEqual(hits[0]["path"], "d.md", query)
            self.assertEqual(hits[0]["matched_by"], "id", query)

    def test_id_inside_a_sentence_is_not_an_id_lookup(self):
        self.assertEqual(
            self.rag._exact_id_search("what changed in WI-148 last week", None), []
        )

    def _add_chunk(self, path, section, body):
        db = self.rag.db
        cur = db.execute(
            "INSERT INTO chunks (path, title, section, content, doc_type, source_type,"
            " project, status, tags, updated, token_count)"
            " VALUES (?, 'Deploy pipeline', ?, ?, 'work-item', 'work', 'p', 'to-do', '[]', NULL, 10)",
            (path, section, body),
        )
        cid = cur.lastrowid
        db.execute(
            "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
            (cid, _serialize_f32(_embed(f"Deploy pipeline {section} {body}"))),
        )
        db.execute(
            "INSERT INTO fts_chunks(rowid, title, section, content) VALUES (?, ?, ?, ?)",
            (cid, "WI-101 Deploy pipeline", section, body),
        )
        db.commit()

    def test_one_chunk_per_document_by_default(self):
        self._add_chunk("a.md", "Rollback", "Rollback of the deployment of the service.")
        self.rag._reranker = FakeReranker("deployment")
        hits = self.rag.search("deployment of the service", top_k=5)
        paths = [h["path"] for h in hits]
        self.assertEqual(len(paths), len(set(paths)))

    def test_one_per_doc_can_be_disabled(self):
        self._add_chunk("a.md", "Rollback", "Rollback of the deployment of the service.")
        self.rag._reranker = FakeReranker("deployment")
        hits = self.rag.search("deployment of the service", top_k=5, one_per_doc=False)
        self.assertGreater([h["path"] for h in hits].count("a.md"), 1)

    def test_exact_id_respects_filters(self):
        self.assertEqual(self.rag.search("WI-148", doc_type="analysis"), [])

    def test_stemming_matches_variants(self):
        ids = [rid for rid, _ in self.rag._keyword_search("deploying", 10, None)]
        paths = {
            self.rag.db.execute("SELECT path FROM chunks WHERE id=?", (i,)).fetchone()[0]
            for i in ids
        }
        self.assertEqual(paths, {"a.md"})

    def test_no_match_flagged_low(self):
        self.rag._reranker = FakeReranker("zzzz-never")
        hits = self.rag.search("sourdough bread starter", top_k=3)
        self.assertTrue(hits)
        self.assertTrue(all(h["confidence"] == "low" and h["below_floor"] for h in hits))

    def test_schema_version_recorded_on_fresh_db(self):
        self.assertEqual(self.rag._read_meta_int("schema_version", 0), SCHEMA_VERSION)

    def test_schema_mismatch_triggers_rebuild(self):
        db = self.rag.db
        db.execute("INSERT INTO doc_hashes(path, content_hash) VALUES ('a.md', 'x')")
        db.execute(
            "INSERT OR REPLACE INTO rag_meta(key, value) VALUES ('schema_version', '1')"
        )
        db.commit()
        self.rag.close()

        reopened = HyperspaceRAG(db_path=self.tmp / "rag.db")
        self.addCleanup(reopened.close)
        db = reopened.db
        self.assertEqual(db.execute("SELECT COUNT(*) FROM doc_hashes").fetchone()[0], 0)
        self.assertEqual(db.execute("SELECT COUNT(*) FROM fts_chunks").fetchone()[0], 0)
        self.assertEqual(reopened._read_meta_int("schema_version", 0), SCHEMA_VERSION)

    def test_same_schema_version_keeps_data(self):
        self.rag.close()
        reopened = HyperspaceRAG(db_path=self.tmp / "rag.db")
        self.addCleanup(reopened.close)
        self.assertEqual(
            reopened.db.execute("SELECT COUNT(*) FROM fts_chunks").fetchone()[0], len(CORPUS)
        )


if __name__ == "__main__":
    unittest.main()
