"""Storage compaction tests for the RAG engine.

Run from the .hypervisor directory:
    python -m unittest tests.test_rag_compaction -v

These exercise the SQLite side only (FTS5 optimize, cadenced VACUUM, WAL
checkpoint). Chunks are inserted with synthetic vectors so the embedding model
is never loaded.
"""

import logging
import random
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hv_mcp import rag  # noqa: E402
from hv_mcp.rag import EMBEDDING_DIM, HyperspaceRAG, _serialize_f32  # noqa: E402

_saved_handlers: list = []


def setUpModule():
    # The engine logs through the shared rag logger, whose handler writes the
    # production rag.log. Swap it for a NullHandler so test runs leave no trace
    # there; assertLogs still works because it attaches its own handler.
    _saved_handlers[:] = rag.logger.handlers
    rag.logger.handlers = [logging.NullHandler()]


def tearDownModule():
    rag.logger.handlers = list(_saved_handlers)


DOC_COUNT = 20
CHUNKS_PER_DOC = 8
BODY = "retrieval augmented generation over hyperspace markdown " * 40


def _vector(seed: int) -> list[float]:
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]


class CompactionTestBase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="rag-compaction-"))
        # Registered first so it runs last: cleanups are LIFO, and Windows
        # cannot delete the database while any connection (peers included) is open.
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.db_path = self.tmpdir / "rag.db"
        self.engine = HyperspaceRAG(db_path=self.db_path)

    def tearDown(self):
        self.engine.close()

    def write_doc(self, doc_index: int, generation: int):
        """Delete-and-reinsert one document, mirroring index_document's write path."""
        path = f"docs/doc-{doc_index}.md"
        db = self.engine.db
        self.engine._delete_document(path)
        for chunk in range(CHUNKS_PER_DOC):
            content = f"doc{doc_index} chunk{chunk} gen{generation} {BODY}"
            cur = db.execute(
                "INSERT INTO chunks (path, title, section, content) VALUES (?, ?, ?, ?)",
                (path, f"Doc {doc_index}", f"Section {chunk}", content),
            )
            db.execute(
                "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                (cur.lastrowid, _serialize_f32(_vector(doc_index * 100 + chunk))),
            )
            db.execute(
                "INSERT INTO fts_chunks(rowid, content) VALUES (?, ?)",
                (cur.lastrowid, content),
            )
        db.commit()

    def seed(self):
        for doc_index in range(DOC_COUNT):
            self.write_doc(doc_index, generation=0)

    def churn(self, rounds: int):
        """Re-save every document `rounds` times - the frequent-edit workload."""
        for generation in range(1, rounds + 1):
            for doc_index in range(DOC_COUNT):
                self.write_doc(doc_index, generation)

    def wal_size(self) -> int:
        wal = Path(str(self.db_path) + "-wal")
        return wal.stat().st_size if wal.exists() else 0

    def db_size(self) -> int:
        return self.db_path.stat().st_size

    def search_snapshot(self) -> tuple[list[str], list[str]]:
        """Paths returned by the vector arm and the keyword arm."""
        db = self.engine.db
        vec_rows = db.execute(
            "SELECT c.path, c.section FROM vec_chunks v JOIN chunks c ON c.id = v.rowid "
            "WHERE v.embedding MATCH ? AND k = 10 ORDER BY v.distance",
            (_serialize_f32(_vector(3 * 100 + 2)),),
        ).fetchall()
        fts_rows = db.execute(
            "SELECT c.path, c.section FROM fts_chunks f JOIN chunks c ON c.id = f.rowid "
            "WHERE fts_chunks MATCH ? ORDER BY rank LIMIT 10",
            ("doc7",),
        ).fetchall()
        return [f"{p}#{s}" for p, s in vec_rows], [f"{p}#{s}" for p, s in fts_rows]


class DeleteCounterTests(CompactionTestBase):
    def test_delete_document_returns_and_accumulates_row_count(self):
        self.seed()
        self.assertEqual(self.engine._deletes_since_vacuum, 0)
        removed = self.engine._delete_document("docs/doc-0.md")
        self.assertEqual(removed, CHUNKS_PER_DOC)
        self.assertEqual(self.engine._deletes_since_vacuum, CHUNKS_PER_DOC)

    def test_counter_survives_reopen(self):
        self.seed()
        self.churn(rounds=1)  # 160 deletions, below the threshold
        self.engine._compact(churn_rows=DOC_COUNT)
        expected = DOC_COUNT * CHUNKS_PER_DOC
        self.engine.close()

        reopened = HyperspaceRAG(db_path=self.db_path)
        try:
            _ = reopened.db
            self.assertEqual(reopened._deletes_since_vacuum, expected)
        finally:
            reopened.close()


class CompactionTests(CompactionTestBase):
    def test_below_threshold_checkpoints_without_vacuum(self):
        self.seed()
        self.churn(rounds=1)
        self.assertGreater(self.wal_size(), 0)

        result = self.engine._compact(churn_rows=DOC_COUNT)

        self.assertFalse(result["vacuumed"])
        self.assertFalse(result["checkpoint_busy"])
        self.assertEqual(self.wal_size(), 0, "TRUNCATE checkpoint should empty the WAL")

    def test_threshold_triggers_vacuum_and_reclaims_space(self):
        self.seed()
        self.churn(rounds=5)  # 800 deletions, crosses the 500 threshold
        self.engine.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        bloated = self.db_size()

        result = self.engine._compact(churn_rows=DOC_COUNT)

        self.assertTrue(result["vacuumed"])
        self.assertEqual(result["deletes_since_vacuum"], 0)
        self.assertEqual(self.wal_size(), 0, "checkpoint after VACUUM must empty the WAL")
        self.assertLess(self.db_size(), bloated, "VACUUM should shrink the main file")

    def test_repeated_saves_do_not_grow_store_without_bound(self):
        self.seed()
        sizes = []
        for _ in range(6):
            self.churn(rounds=2)
            self.engine._compact(churn_rows=DOC_COUNT)
            sizes.append(self.db_size() + self.wal_size())
        # After the first VACUUM cycle the total should plateau, not climb
        # linearly with the number of re-saves.
        self.assertLessEqual(max(sizes[2:]), sizes[1] * 1.25, sizes)

    def test_search_results_identical_after_compaction(self):
        self.seed()
        self.churn(rounds=5)
        before = self.search_snapshot()
        self.engine._compact(churn_rows=DOC_COUNT)
        after = self.search_snapshot()
        self.assertEqual(before, after)
        self.assertTrue(before[0] and before[1], "both search arms should return rows")

    def test_active_reader_blocks_checkpoint_without_raising(self):
        self.seed()
        self.churn(rounds=1)

        reader = sqlite3.connect(str(self.db_path))
        try:
            reader.execute("BEGIN")
            reader.execute("SELECT COUNT(*) FROM chunks").fetchone()
            # Writes after the reader's snapshot leave frames it still needs.
            self.churn(rounds=1)
            result = self.engine._compact(churn_rows=DOC_COUNT)
            self.assertTrue(result["checkpoint_busy"])
        finally:
            reader.rollback()
            reader.close()

        # Once the reader is gone the next compaction completes normally.
        self.churn(rounds=1)
        result = self.engine._compact(churn_rows=DOC_COUNT)
        self.assertFalse(result["checkpoint_busy"])
        self.assertEqual(self.wal_size(), 0)

    def test_idle_second_connection_does_not_block_checkpoint(self):
        self.seed()
        idle = sqlite3.connect(str(self.db_path))
        try:
            idle.execute("SELECT COUNT(*) FROM chunks").fetchone()  # no open transaction
            self.churn(rounds=1)
            result = self.engine._compact(churn_rows=DOC_COUNT)
            self.assertFalse(result["checkpoint_busy"])
            self.assertEqual(self.wal_size(), 0)
        finally:
            idle.close()


class ReindexWiringTests(CompactionTestBase):
    def test_noop_reindex_skips_compaction(self):
        calls = []
        self.engine._compact = lambda churn_rows: calls.append(churn_rows)
        original = rag.collect_rag_files
        rag.collect_rag_files = lambda: []
        try:
            self.engine.reindex_changed()
        finally:
            rag.collect_rag_files = original
        self.assertEqual(calls, [])

    def test_reindex_with_removals_runs_compaction(self):
        self.seed()
        db = self.engine.db
        db.execute(
            "INSERT INTO doc_hashes (path, content_hash) VALUES (?, ?)",
            ("docs/doc-0.md", "stale"),
        )
        db.commit()
        calls = []
        self.engine._compact = lambda churn_rows: calls.append(churn_rows)
        original = rag.collect_rag_files
        rag.collect_rag_files = lambda: []  # doc-0 vanished from disk
        try:
            result = self.engine.reindex_changed()
        finally:
            rag.collect_rag_files = original
        self.assertEqual(result["documents_removed"], 1)
        self.assertEqual(calls, [1])


class _FakeModel:
    """Stands in for fastembed: deterministic vectors, no ONNX load."""

    def __init__(self):
        self.batch_sizes = []

    def embed(self, texts, batch_size=256):
        self.batch_sizes.append(batch_size)
        for text in texts:
            yield _vector(hash(text) & 0xFFFF)


class SavePathBase(CompactionTestBase):
    """Drives the real index_document with a stubbed model, tokenizer, and chunker."""

    def setUp(self):
        super().setUp()
        self.root = self.tmpdir / "hyperspace"
        (self.root / "docs").mkdir(parents=True)
        self._original_root = rag.HYPERSPACE_ROOT
        rag.HYPERSPACE_ROOT = self.root
        self.engine._model = _FakeModel()
        self.engine.count_tokens = lambda text: 10
        self.engine._build_embed_text = (
            lambda title, section, body, work_id: f"{title} {section} {body}"
        )
        self.engine.chunk_document = lambda md_text: [
            (f"Section {chunk}", f"{md_text} body {chunk}") for chunk in range(CHUNKS_PER_DOC)
        ]
        self.compactions = []
        real_compact = self.engine._compact

        def recording_compact(churn_rows):
            result = real_compact(churn_rows=churn_rows)
            self.compactions.append(result)
            return result

        self.engine._compact = recording_compact

    def tearDown(self):
        rag.HYPERSPACE_ROOT = self._original_root
        super().tearDown()

    def save(self, name: str, generation: int, commit: bool = True) -> int:
        path = self.root / "docs" / f"{name}.md"
        path.write_text(f"# {name}\n\nGeneration {generation}\n", encoding="utf-8")
        return self.engine.index_document(f"docs/{name}.md", commit=commit)


class SavePathCompactionTests(SavePathBase):
    """Per-save writes bypass reindex_changed, so they must compact on their own."""

    def test_repeated_saves_trigger_compaction_and_bound_wal(self):
        for generation in range(30):
            self.save("hot-doc", generation)
        # 8 inserted + 8 deleted rows per re-save -> compaction every few saves.
        self.assertGreaterEqual(len(self.compactions), 5)
        self.assertLess(self.engine._rows_since_compact, rag.COMPACT_ROW_THRESHOLD)
        self.assertEqual(self.engine.chunk_count(), CHUNKS_PER_DOC)

    def test_sustained_saves_plateau_store_size(self):
        totals = []
        for generation in range(400):
            self.save("hot-doc", generation)
            if generation % 50 == 49:
                totals.append(self.db_size() + self.wal_size())
        self.assertTrue(any(result["vacuumed"] for result in self.compactions))
        self.assertLessEqual(max(totals[2:]), max(totals[:2]) * 1.25, totals)

    def test_unchanged_content_is_not_reembedded(self):
        # Watcher events fire on reads too (last-access updates on Windows), so
        # an event for unchanged content must be a no-op.
        self.assertEqual(self.save("hot-doc", 0), CHUNKS_PER_DOC)
        deletes_before = self.engine._deletes_since_vacuum
        self.assertEqual(self.engine.index_document("docs/hot-doc.md"), 0)
        self.assertEqual(len(self.engine._model.batch_sizes), 1)
        self.assertEqual(self.engine._deletes_since_vacuum, deletes_before)
        self.assertEqual(self.engine.chunk_count(), CHUNKS_PER_DOC)

        self.assertEqual(
            self.engine.index_document("docs/hot-doc.md", force=True), CHUNKS_PER_DOC
        )
        self.assertEqual(len(self.engine._model.batch_sizes), 2)

    def test_embeds_with_bounded_batch_size(self):
        # One large inference pins the ONNX arena at its peak for the life of
        # the session, so document embedding must stay at the bounded batch.
        self.save("hot-doc", 0)
        self.assertEqual(self.engine._model.batch_sizes, [rag.EMBED_BATCH_SIZE])

    def test_batched_writes_defer_compaction(self):
        for generation in range(10):
            self.save("hot-doc", generation, commit=False)
        self.engine.db.commit()
        self.assertEqual(self.compactions, [])

    def test_remove_document_triggers_compaction(self):
        for index in range(7):
            self.save(f"doc-{index}", 0)  # 56 inserts -> one compaction
        self.compactions.clear()
        self.engine._rows_since_compact = rag.COMPACT_ROW_THRESHOLD - 1
        self.engine.remove_document("docs/doc-0.md")
        self.assertEqual(len(self.compactions), 1)

    def test_skipped_while_reindex_running(self):
        self.engine._rows_since_compact = rag.COMPACT_ROW_THRESHOLD * 2
        self.engine._indexing = True
        try:
            self.assertIsNone(self.engine._maybe_compact())
        finally:
            self.engine._indexing = False
        self.assertEqual(self.compactions, [])

    def test_failure_is_logged_not_raised_and_retried(self):
        self.save("hot-doc", 0)
        self.engine._rows_since_compact = rag.COMPACT_ROW_THRESHOLD

        def failing_compact(churn_rows):
            raise sqlite3.OperationalError("database is locked")

        self.engine._compact = failing_compact
        with self.assertLogs(rag.logger, level="WARNING"):
            self.assertIsNone(self.engine._maybe_compact())
        self.assertEqual(self.engine._rows_since_compact, rag.COMPACT_ROW_THRESHOLD)

    def test_vacuum_with_statement_in_flight_does_not_break_save(self):
        for generation in range(3):
            self.save("hot-doc", generation)
        self.engine._compact = self.engine.__class__._compact.__get__(self.engine)
        self.engine._deletes_since_vacuum = rag.VACUUM_DELETE_THRESHOLD
        self.engine._rows_since_compact = rag.COMPACT_ROW_THRESHOLD
        # An unfinished SELECT on the shared connection - what a concurrent
        # search thread looks like mid-iteration.
        pending = self.engine.db.execute("SELECT id FROM chunks")
        pending.fetchone()
        try:
            with self.assertLogs(rag.logger, level="WARNING"):
                self.assertIsNone(self.engine._maybe_compact())
        finally:
            pending.close()
        # Counters survive the failure, and the next attempt succeeds.
        self.assertEqual(self.engine._deletes_since_vacuum, rag.VACUUM_DELETE_THRESHOLD)
        self.assertGreaterEqual(self.engine._rows_since_compact, rag.COMPACT_ROW_THRESHOLD)
        result = self.engine._maybe_compact()
        self.assertTrue(result["vacuumed"])
        self.assertEqual(self.wal_size(), 0)


class CrossConnectionTests(SavePathBase):
    """The MCP service and the desktop app each hold a connection and both index
    every save, so writes from two connections must not corrupt or deadlock."""

    def make_peer(self) -> HyperspaceRAG:
        peer = HyperspaceRAG(db_path=self.db_path)
        peer._model = _FakeModel()
        peer.count_tokens = self.engine.count_tokens
        peer._build_embed_text = self.engine._build_embed_text
        peer.chunk_document = self.engine.chunk_document
        self.addCleanup(peer.close)
        return peer

    def consistency(self) -> dict:
        db = self.engine.db
        return {
            "vec_orphans": db.execute(
                "SELECT COUNT(*) FROM vec_chunks WHERE rowid NOT IN (SELECT id FROM chunks)"
            ).fetchone()[0],
            "fts_orphans": db.execute(
                "SELECT COUNT(*) FROM fts_chunks WHERE rowid NOT IN (SELECT id FROM chunks)"
            ).fetchone()[0],
            "chunks_without_vec": db.execute(
                "SELECT COUNT(*) FROM chunks WHERE id NOT IN (SELECT rowid FROM vec_chunks)"
            ).fetchone()[0],
        }

    def test_concurrent_saves_from_two_connections(self):
        import threading

        peer = self.make_peer()
        # Both production processes hold long-lived connections to a database
        # already in WAL mode; open both here first so the test exercises
        # concurrent writes rather than two simultaneous first-time opens.
        _ = self.engine.db
        _ = peer.db
        errors: list[str] = []
        path = self.root / "docs" / "hot-doc.md"

        def worker(engine, rounds):
            for _ in range(rounds):
                try:
                    engine.index_document("docs/hot-doc.md")
                except Exception as exc:  # noqa: BLE001 - collected for the assertion
                    errors.append(f"{type(exc).__name__}: {exc}")

        for generation in range(40):
            path.write_text(f"# hot-doc\n\nGeneration {generation}\n", encoding="utf-8")
            threads = [
                threading.Thread(target=worker, args=(self.engine, 1)),
                threading.Thread(target=worker, args=(peer, 1)),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

        self.assertEqual(errors, [])
        self.assertEqual(
            self.consistency(),
            {"vec_orphans": 0, "fts_orphans": 0, "chunks_without_vec": 0},
        )
        self.assertEqual(self.engine.chunk_count(), CHUNKS_PER_DOC)

    def test_write_section_holds_database_lock_before_reading(self):
        # If the lock were taken lazily (at the first DELETE), another
        # connection could change the document between the chunk-id read and
        # the delete, which is what produced the vec0 UNIQUE failures.
        peer = self.make_peer()
        peer.db.execute("PRAGMA busy_timeout=100")
        with self.engine._write_txn():
            with self.assertRaises(sqlite3.OperationalError):
                peer.db.execute("BEGIN IMMEDIATE")
        peer.db.execute("BEGIN IMMEDIATE")
        peer.db.rollback()

    def test_failed_write_releases_the_lock(self):
        peer = self.make_peer()
        self.save("hot-doc", 0)

        class _BrokenModel(_FakeModel):
            def embed(self, texts, batch_size=256):
                for _ in texts:
                    yield [0.0]  # wrong dimension - the vec0 INSERT raises

        self.engine._model = _BrokenModel()
        (self.root / "docs" / "hot-doc.md").write_text("# hot-doc\n\nchanged\n", encoding="utf-8")
        with self.assertRaises(sqlite3.Error):
            self.engine.index_document("docs/hot-doc.md")
        self.assertFalse(self.engine.db.in_transaction, "failed write left a transaction open")

        # The other connection can still write, and the failed attempt left no partial state.
        self.assertEqual(peer.index_document("docs/hot-doc.md"), CHUNKS_PER_DOC)
        self.assertEqual(
            self.consistency(),
            {"vec_orphans": 0, "fts_orphans": 0, "chunks_without_vec": 0},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
