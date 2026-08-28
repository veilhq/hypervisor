"""
Semantic RAG over hyperspace markdown (WI-123).

Hybrid retrieval: dense vectors (sqlite-vec) fused with keyword search (FTS5)
via Reciprocal Rank Fusion, then MMR-reranked for source diversity.

Design decisions and the empirical verification behind them are recorded in
`work/to-do/semantic-rag-over-hyperspace.md`. The load-bearing constraint:
the embedding model truncates at 512 tokens with no warning, so chunk sizing
is a hard ceiling rather than a soft target.
"""

import hashlib
import json
import math
import re
import sqlite3
import struct
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from site_utils.config import HYPERSPACE_ROOT
from site_utils.file_utils import read_md, get_title, extract_dates
from site_utils.file_utils import (
    _extract_tags_from_text,
    _extract_status_from_text,
)

from .config import STATE_DIR

# Dedicated RAG logger → writes to .hyperspace/.logs/rag.log
sys.path.insert(0, str(HYPERSPACE_ROOT / ".hyperkit" / "python"))
from hyper_logging import setup_logger  # noqa: E402

logger = setup_logger("rag")

# ---------------------------------------------------------------------------
# Model + storage configuration (values verified against fastembed 0.8.0)
# ---------------------------------------------------------------------------

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384

# The model's tokenizer reports max_length=512 with right-truncation. Text past
# that boundary is silently discarded from the embedding, so 512 is a hard
# ceiling, not a target. Body chunks aim lower to leave room for the context
# prefix (title + section heading) prepended before embedding.
MODEL_MAX_TOKENS = 512
TARGET_BODY_TOKENS = 400
CONTEXT_PREFIX_BUDGET = 60

# Sections below this are short enough that packing them with a neighbour helps.
# A complete-but-short `## ` section is still a coherent retrieval unit, so this
# is a preference, not an invariant — see FRAGMENT_TOKENS for the hard case.
MIN_CHUNK_TOKENS = 200

# Below this a chunk is a genuine fragment with too little signal to stand
# alone. The benchmark failure case was chunks averaging 43 tokens. These get a
# relaxed merge budget so they always find a home.
FRAGMENT_TOKENS = 100

# Ceiling for merge operations. Higher than TARGET_BODY_TOKENS so undersized
# sections have room to combine, still low enough that the context prefix keeps
# the total under MODEL_MAX_TOKENS.
MERGE_BUDGET_TOKENS = 430

# Relaxed ceiling used only to rescue a fragment. Absorbing 100 tokens into a
# full chunk beats leaving a 47-token orphan in the index.
FRAGMENT_MERGE_BUDGET_TOKENS = 470

# Overlap between sub-chunks of an oversized section (~19% of target, inside
# the 10-25% range the benchmarks converge on).
OVERLAP_TOKENS = 75

DB_PATH = STATE_DIR / "rag.db"

# ---------------------------------------------------------------------------
# Corpus inclusion policy
# ---------------------------------------------------------------------------
# Deliberately independent of site_utils.SKIP_DIRS: the site build excludes
# `.kb/` from publication, but the RAG indexes it. Retrieval scope and
# publication scope are separate concerns.

INCLUDE_PREFIXES = (
    "work/",
    "research/",
    "context/",
    "ideas/",
    "patterns/",
    "analysis/",
    "reference/",
    ".external/",
    ".kb/",
)

EXCLUDE_DIR_PARTS = {
    "templates",
    "prototypes",
    "__pycache__",
    "site",
    "learn",
    ".scratch",
    ".hypervisor",
    ".hyperagent",
    ".hyperkit",
    ".hypereye",
    ".events",
    ".logs",
}

EXCLUDE_FILENAMES = {"_index.md", "_meta.md", "_conventions.md", "_readme.md"}

# RRF constant. 60 is the value from the original Cormack et al. formulation
# and the de-facto default across implementations.
RRF_K = 60

# MMR relevance/diversity balance. Leans toward relevance.
MMR_LAMBDA = 0.7

# Recency boost ceiling — a document updated today scores this much higher than
# one untouched for RECENCY_HALFLIFE_DAYS. Deliberately small per decision #5.
RECENCY_BOOST = 0.15
RECENCY_HALFLIFE_DAYS = 90


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_f32(vector) -> bytes:
    """Pack a float vector into the raw byte format sqlite-vec expects."""
    return struct.pack(f"{len(vector)}f", *vector)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def collect_rag_files() -> list[str]:
    """Walk hyperspace and return relative POSIX paths eligible for indexing."""
    results = []
    for path in sorted(HYPERSPACE_ROOT.rglob("*.md")):
        rel = path.relative_to(HYPERSPACE_ROOT)
        rel_str = str(rel).replace("\\", "/")

        if path.name in EXCLUDE_FILENAMES:
            continue
        if any(part in EXCLUDE_DIR_PARTS for part in rel.parts[:-1]):
            continue
        if not rel_str.startswith(INCLUDE_PREFIXES):
            continue
        results.append(rel_str)
    return results


def is_indexable(rel_path: str) -> bool:
    """Whether a relative path falls inside the RAG corpus."""
    rel_str = rel_path.replace("\\", "/")
    if not rel_str.endswith(".md"):
        return False
    parts = rel_str.split("/")
    if parts[-1] in EXCLUDE_FILENAMES:
        return False
    if any(part in EXCLUDE_DIR_PARTS for part in parts[:-1]):
        return False
    return rel_str.startswith(INCLUDE_PREFIXES)


def _source_type_for(rel_path: str) -> str:
    """'kb' for agent knowledge-bank entries, 'doc' for authored hyperspace docs."""
    return "kb" if rel_path.replace("\\", "/").startswith(".kb/") else "doc"


def _infer_doc_type(rel_path: str) -> str:
    """Infer document type from path. Mirrors hv_mcp.index._infer_doc_type."""
    parts = rel_path.replace("\\", "/").split("/")
    head = parts[0]
    if head == "work":
        return "work-item"
    if head == "ideas":
        return "idea"
    if head == "research":
        return "bugfix" if len(parts) > 1 and parts[1] == "bugfixes" else "research"
    if head == "context":
        return "context"
    if head == "patterns":
        return "pattern"
    if head == "analysis":
        return "analysis"
    if head == "reference":
        return "reference"
    if head == ".external":
        return "external"
    if head == ".kb":
        return "kb"
    return "document"


def _extract_project(md_text: str) -> str | None:
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r"Project\s*:\s*(.+)", stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_work_id(md_text: str) -> str | None:
    """Extract the `- ID: WI-N` metadata value."""
    for line in md_text.splitlines()[:30]:
        stripped = line.strip().lstrip("- ")
        m = re.match(r"ID\s*:\s*(WI-\d+)", stripped, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


# Metadata keys that appear as `- Key: value` in document headers. These are
# stored as structured filters, not embedded as searchable prose (decision #9).
_METADATA_LINE_RE = re.compile(
    r"^-\s*(created|updated|date|tags|technologies|id|type|status|project|related|"
    r"severity|affected|idea doc|external story|source|confidence|version|captured|"
    r"pr author|pr created|pr link)\s*:",
    re.IGNORECASE,
)


def strip_metadata_block(md_text: str) -> str:
    """Remove header metadata lines and separators, preserving prose.

    The H1 title and the one-line description survive — they carry meaning.
    Only the `- Key: value` metadata rows and the horizontal rule that closes
    the header block are removed.
    """
    lines = md_text.splitlines()
    out = []
    in_body = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            in_body = True
        if not in_body:
            if _METADATA_LINE_RE.match(stripped):
                continue
            if stripped in ("---", "***", "___"):
                continue
        out.append(line)
    return "\n".join(out).strip()


def split_h2_sections(body: str) -> list[tuple[str | None, str]]:
    """Split markdown into (heading, text) pairs on `## ` boundaries.

    Content before the first `## ` is returned with heading None. Fenced code
    blocks are respected so a `## ` inside a code fence is not treated as a
    heading.
    """
    sections: list[tuple[str | None, str]] = []
    current_heading: str | None = None
    current: list[str] = []
    in_fence = False

    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            current.append(line)
            continue
        if not in_fence and stripped.startswith("## "):
            text = "\n".join(current).strip()
            if text or current_heading is not None:
                sections.append((current_heading, text))
            current_heading = stripped[3:].strip()
            current = []
            continue
        current.append(line)

    text = "\n".join(current).strip()
    if text or current_heading is not None:
        sections.append((current_heading, text))

    return [(h, t) for h, t in sections if t.strip() or h]


# ---------------------------------------------------------------------------
# RAG engine
# ---------------------------------------------------------------------------

class HyperspaceRAG:
    """Chunk, embed, and hybrid-search hyperspace markdown."""

    def __init__(self, db_path: Path | None = None, model_name: str = MODEL_NAME):
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.model_name = model_name
        self._model = None
        self._tokenizer = None
        self._db: sqlite3.Connection | None = None
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._indexing = False

    # -- lifecycle ---------------------------------------------------------

    @property
    def model(self):
        """Embedding model, loaded on first access (thread-safe)."""
        if self._model is None:
            with self._lock:
                # Double-check after acquiring lock.
                if self._model is None:
                    from fastembed import TextEmbedding

                    logger.info("loading embedding model %s", self.model_name)
                    model = TextEmbedding(model_name=self.model_name)
                    self._tokenizer = self._build_counting_tokenizer(
                        model.model.tokenizer
                    )
                    # Publish after tokenizer is ready so other threads see both.
                    self._model = model
                    logger.info("embedding model ready")
        return self._model

    @staticmethod
    def _build_counting_tokenizer(model_tokenizer):
        """Return an independent tokenizer with truncation disabled.

        The model's own tokenizer truncates at MODEL_MAX_TOKENS, which is
        correct for inference but wrong for measurement: encoding a 3,000-token
        section would report 512 and expose only the first 512 offsets, so
        windowing over it would silently discard the rest of the section.

        Mutating the shared instance would change inference behaviour, so this
        round-trips through a serialized copy instead.
        """
        from tokenizers import Tokenizer

        counting = Tokenizer.from_str(model_tokenizer.to_str())
        counting.no_truncation()
        counting.no_padding()
        return counting

    @property
    def tokenizer(self):
        """Non-truncating tokenizer used for counting and windowing."""
        if self._tokenizer is None:
            _ = self.model  # triggers load, which sets _tokenizer
        return self._tokenizer

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            import sqlite_vec

            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            db = sqlite3.connect(str(self.db_path), check_same_thread=False)
            db.enable_load_extension(True)
            sqlite_vec.load(db)
            db.enable_load_extension(False)
            # WAL mode allows concurrent readers alongside a single writer,
            # eliminating cross-process "database is locked" errors when the
            # MCP server and the Hypervisor desktop app access rag.db
            # simultaneously.  busy_timeout gives the loser of a write race
            # up to 5 seconds to retry before raising OperationalError.
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=5000")
            self._db = db
            self._init_schema()
        return self._db

    def _init_schema(self):
        db = self._db
        db.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS chunks (
                id           INTEGER PRIMARY KEY,
                path         TEXT NOT NULL,
                title        TEXT,
                section      TEXT,
                content      TEXT NOT NULL,
                doc_type     TEXT,
                source_type  TEXT,
                project      TEXT,
                status       TEXT,
                tags         TEXT,
                updated      TEXT,
                token_count  INTEGER
            );
            CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path);
            CREATE INDEX IF NOT EXISTS idx_chunks_doc_type ON chunks(doc_type);

            CREATE TABLE IF NOT EXISTS doc_hashes (
                path          TEXT PRIMARY KEY,
                content_hash  TEXT NOT NULL,
                indexed_at    TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                embedding float[{EMBEDDING_DIM}] distance_metric=cosine
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(content);
            """
        )
        db.commit()
        self._repair_orphans()

    def _repair_orphans(self):
        """Remove vec_chunks/fts_chunks rows whose rowid has no matching chunks row.

        This state can occur if a prior crash left partial writes uncommitted
        (or committed the chunks INSERT but crashed before vec_chunks INSERT,
        leaving the inverse inconsistency on the next attempt).
        """
        db = self._db
        # vec0 doesn't support subquery-based DELETE, so fetch orphan IDs first.
        orphans = db.execute(
            "SELECT v.rowid FROM vec_chunks v "
            "WHERE v.rowid NOT IN (SELECT id FROM chunks)"
        ).fetchall()
        if orphans:
            logger.info("repairing %d orphan vec_chunks rows", len(orphans))
            for (rid,) in orphans:
                db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (rid,))
            db.commit()

        fts_orphans = db.execute(
            "SELECT rowid FROM fts_chunks "
            "WHERE rowid NOT IN (SELECT id FROM chunks)"
        ).fetchall()
        if fts_orphans:
            logger.info("repairing %d orphan fts_chunks rows", len(fts_orphans))
            for (rid,) in fts_orphans:
                db.execute("DELETE FROM fts_chunks WHERE rowid = ?", (rid,))
            db.commit()

    def close(self):
        if self._db is not None:
            self._db.close()
            self._db = None

    # -- tokenization ------------------------------------------------------

    def count_tokens(self, text: str) -> int:
        if not text.strip():
            return 0
        return len(self.tokenizer.encode(text, add_special_tokens=False).ids)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        enc = self.tokenizer.encode(text, add_special_tokens=False)
        if len(enc.ids) <= max_tokens:
            return text
        end_char = enc.offsets[max_tokens - 1][1]
        return text[:end_char]

    def _token_windows(self, text: str, target: int, overlap: int) -> list[str]:
        """Split text into overlapping windows at exact token boundaries."""
        enc = self.tokenizer.encode(text, add_special_tokens=False)
        offsets = enc.offsets
        n = len(offsets)
        if n <= target:
            return [text]

        stride = max(1, target - overlap)
        windows = []
        start = 0
        while start < n:
            end = min(start + target, n)
            char_start = offsets[start][0]
            char_end = offsets[end - 1][1]
            piece = text[char_start:char_end].strip()
            if piece:
                windows.append(piece)
            if end >= n:
                break
            start += stride
        return windows

    # -- chunking ----------------------------------------------------------

    def chunk_document(self, md_text: str) -> list[tuple[str | None, str]]:
        """Split a document into (section_heading, chunk_text) pairs.

        Structure-aware: splits on `## ` headings, which map to hyperspace's
        document conventions. Oversized sections are sub-split at token
        boundaries with overlap; undersized ones are merged forward so no
        standalone fragment falls below MIN_CHUNK_TOKENS.
        """
        body = strip_metadata_block(md_text)
        if not body.strip():
            return []

        # Short documents stay whole — splitting a self-contained doc into
        # fragments is a net loss.
        if self.count_tokens(body) <= TARGET_BODY_TOKENS:
            return [(None, body)]

        raw: list[tuple[str | None, str]] = []
        for heading, text in split_h2_sections(body):
            if not text.strip():
                continue
            if self.count_tokens(text) > TARGET_BODY_TOKENS:
                for window in self._token_windows(
                    text, TARGET_BODY_TOKENS, OVERLAP_TOKENS
                ):
                    raw.append((heading, window))
            else:
                raw.append((heading, text))

        return self._merge_small(raw)

    def _merge_small(
        self, chunks: list[tuple[str | None, str]]
    ) -> list[tuple[str | None, str]]:
        """Fold undersized sections into neighbours.

        A complete-but-short `## ` section is not the pathological case the
        200-token floor guards against — that was mid-sentence fragments. Still,
        packing short sections together gives the embedding more to work with.
        Tries forward accumulation first, then folds backward into the previous
        chunk, and only emits a short chunk standalone when neither fits.
        """
        if not chunks:
            return []

        out: list[tuple[str | None, str]] = []
        buf: tuple[str | None, str] | None = None

        def budget_for(candidate_text: str) -> int:
            """Fragments get a relaxed ceiling so they always find a home."""
            if self.count_tokens(candidate_text) < FRAGMENT_TOKENS:
                return FRAGMENT_MERGE_BUDGET_TOKENS
            return MERGE_BUDGET_TOKENS

        def fold_backward(candidate: tuple[str | None, str]) -> bool:
            if not out:
                return False
            prev_heading, prev_text = out[-1]
            combined = f"{prev_text}\n\n{candidate[1]}".strip()
            if self.count_tokens(combined) <= budget_for(candidate[1]):
                out[-1] = (prev_heading, combined)
                return True
            return False

        for heading, text in chunks:
            size = self.count_tokens(text)

            if buf is None:
                if size >= MIN_CHUNK_TOKENS:
                    out.append((heading, text))
                else:
                    buf = (heading, text)
                continue

            combined = f"{buf[1]}\n\n{text}".strip()
            if self.count_tokens(combined) <= budget_for(buf[1]):
                buf = (buf[0] or heading, combined)
                if self.count_tokens(buf[1]) >= MIN_CHUNK_TOKENS:
                    out.append(buf)
                    buf = None
                continue

            # Forward merge would overflow. Try backward before giving up.
            if not fold_backward(buf):
                out.append(buf)
            buf = None

            if size >= MIN_CHUNK_TOKENS:
                out.append((heading, text))
            else:
                buf = (heading, text)

        if buf is not None and not fold_backward(buf):
            out.append(buf)

        return out

    def _build_embed_text(
        self, title: str, section: str | None, body: str, work_id: str | None = None
    ) -> str:
        """Prepend structural context, then hard-clamp to the model's limit.

        Carrying the title and section heading into the embedded text is the
        cheap form of contextual retrieval — an isolated chunk like "the third
        requirement" is meaningless without knowing which document and section
        it came from. This is document structure, distinct from the header
        metadata that decision #9 keeps out of embeddings.

        The work item ID is included because it is an identifier, not a label:
        without it, searching "WI-123" cannot find the document whose ID is
        WI-123, since metadata stripping removes the `- ID:` line.
        """
        parts = [p for p in (work_id, title) if p]
        prefix = " — ".join(parts)
        if section:
            prefix = f"{prefix} — {section}" if prefix else section
        prefix = self._truncate_to_tokens(prefix, CONTEXT_PREFIX_BUDGET)

        text = f"{prefix}\n\n{body}".strip() if prefix else body
        # Guarantee no silent truncation by the model.
        return self._truncate_to_tokens(text, MODEL_MAX_TOKENS)

    # -- indexing ----------------------------------------------------------

    def _document_metadata(self, rel_path: str, md_text: str) -> dict:
        dates = extract_dates(md_text)
        return {
            "path": rel_path,
            "title": get_title(md_text, Path(rel_path).stem.replace("-", " ").title()),
            "work_id": _extract_work_id(md_text),
            "doc_type": _infer_doc_type(rel_path),
            "source_type": _source_type_for(rel_path),
            "project": _extract_project(md_text),
            "status": _extract_status_from_text(md_text),
            "tags": _extract_tags_from_text(md_text),
            "updated": dates.get("updated") or dates.get("created"),
        }

    def _delete_document(self, rel_path: str):
        db = self.db
        rows = db.execute("SELECT id FROM chunks WHERE path = ?", (rel_path,)).fetchall()
        for (chunk_id,) in rows:
            db.execute("DELETE FROM vec_chunks WHERE rowid = ?", (chunk_id,))
            db.execute("DELETE FROM fts_chunks WHERE rowid = ?", (chunk_id,))
        db.execute("DELETE FROM chunks WHERE path = ?", (rel_path,))

    def index_document(self, rel_path: str, commit: bool = True) -> int:
        """Index (or re-index) a single document. Returns chunks written."""
        full_path = HYPERSPACE_ROOT / rel_path
        if not full_path.exists():
            self.remove_document(rel_path)
            return 0

        try:
            md_text = read_md(full_path)
        except (OSError, UnicodeDecodeError):
            logger.warning("unreadable file skipped: %s", rel_path)
            return 0

        meta = self._document_metadata(rel_path, md_text)
        pieces = self.chunk_document(md_text)
        if not pieces:
            with self._write_lock:
                self._delete_document(rel_path)
                if commit:
                    self.db.commit()
            return 0

        embed_texts = [
            self._build_embed_text(meta["title"], section, body, meta["work_id"])
            for section, body in pieces
        ]
        vectors = list(self.model.embed(embed_texts))

        with self._write_lock:
            db = self.db
            self._delete_document(rel_path)

            tags_json = json.dumps(meta["tags"])
            for (section, body), embed_text, vector in zip(pieces, embed_texts, vectors):
                cur = db.execute(
                    """
                    INSERT INTO chunks (
                        path, title, section, content, doc_type,
                        source_type, project, status, tags, updated, token_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rel_path,
                        meta["title"],
                        section,
                        body,
                        meta["doc_type"],
                        meta["source_type"],
                        meta["project"],
                        meta["status"],
                        tags_json,
                        meta["updated"],
                        self.count_tokens(embed_text),
                    ),
                )
                chunk_id = cur.lastrowid
                db.execute(
                    "INSERT INTO vec_chunks(rowid, embedding) VALUES (?, ?)",
                    (chunk_id, _serialize_f32(vector)),
                )
                # The FTS index carries the context prefix so identifier lookups
                # (work item IDs, section titles) resolve on the keyword arm.
                db.execute(
                    "INSERT INTO fts_chunks(rowid, content) VALUES (?, ?)",
                    (chunk_id, embed_text),
                )

            db.execute(
                """
                INSERT INTO doc_hashes (path, content_hash, indexed_at)
                VALUES (?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    content_hash = excluded.content_hash,
                    indexed_at = excluded.indexed_at
                """,
                (rel_path, _content_hash(md_text), datetime.now().strftime("%Y-%m-%dT%H:%M")),
            )
            if commit:
                db.commit()
        return len(pieces)

    def remove_document(self, rel_path: str):
        with self._write_lock:
            db = self.db
            self._delete_document(rel_path)
            db.execute("DELETE FROM doc_hashes WHERE path = ?", (rel_path,))
            db.commit()

    def reindex_changed(self, force: bool = False) -> dict:
        """Index new/changed documents and drop deleted ones.

        Content-hash comparison keeps unchanged documents from being re-embedded.
        """
        with self._lock:
            if self._indexing:
                return {"status": "already_running"}
            self._indexing = True

        try:
            db = self.db
            known = {
                path: h
                for path, h in db.execute("SELECT path, content_hash FROM doc_hashes")
            }
            on_disk = collect_rag_files()

            indexed = skipped = removed = chunks_written = 0

            # Determine the work set first so progress can be reported. Embedding
            # runs at roughly 6-9 chunks/s on CPU, so a cold build over the full
            # corpus takes minutes — silence would look like a hang.
            to_index: list[str] = []
            for rel_path in on_disk:
                full = HYPERSPACE_ROOT / rel_path
                try:
                    md_text = read_md(full)
                except (OSError, UnicodeDecodeError):
                    logger.warning("unreadable file skipped: %s", rel_path)
                    continue
                if not force and known.get(rel_path) == _content_hash(md_text):
                    skipped += 1
                else:
                    to_index.append(rel_path)

            if to_index:
                logger.info(
                    "indexing %d document(s) (%d unchanged)",
                    len(to_index),
                    skipped,
                )

            report_every = max(1, len(to_index) // 10)
            for position, rel_path in enumerate(to_index, start=1):
                chunks_written += self.index_document(rel_path, commit=False)
                indexed += 1
                if position % report_every == 0 or position == len(to_index):
                    logger.info(
                        "%d/%d documents, %d chunks",
                        position,
                        len(to_index),
                        chunks_written,
                    )

            with self._write_lock:
                for stale in set(known) - set(on_disk):
                    self._delete_document(stale)
                    db.execute("DELETE FROM doc_hashes WHERE path = ?", (stale,))
                    removed += 1

                db.commit()

            result = {
                "status": "ok",
                "documents_indexed": indexed,
                "documents_skipped": skipped,
                "documents_removed": removed,
                "chunks_written": chunks_written,
                "total_chunks": self.chunk_count(),
            }
            logger.info(
                "reindex complete — %d indexed, %d skipped, %d removed, %d chunks",
                indexed,
                skipped,
                removed,
                result["total_chunks"],
            )
            return result
        finally:
            with self._lock:
                self._indexing = False

    def chunk_count(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]

    def is_empty(self) -> bool:
        return self.chunk_count() == 0

    # -- retrieval ---------------------------------------------------------

    def _candidate_rowids(
        self,
        tags: list[str] | None,
        doc_type: str | None,
        project: str | None,
        source_type: str | None,
    ) -> list[int] | None:
        """Rowids matching the metadata filters, or None when unfiltered.

        Pre-filtering matters: sqlite-vec resolves KNN before any join, so
        filtering after the fact can silently return fewer than k results.
        """
        clauses = []
        params: list = []

        if doc_type:
            clauses.append("doc_type = ?")
            params.append(doc_type)
        if project:
            clauses.append("project = ?")
            params.append(project)
        if source_type:
            clauses.append("source_type = ?")
            params.append(source_type)
        if tags:
            for tag in tags:
                clauses.append(
                    "EXISTS (SELECT 1 FROM json_each(chunks.tags) WHERE json_each.value = ?)"
                )
                params.append(tag.lower())

        if not clauses:
            return None

        sql = f"SELECT id FROM chunks WHERE {' AND '.join(clauses)}"
        return [r[0] for r in self.db.execute(sql, params).fetchall()]

    def _vector_search(
        self, query: str, k: int, candidates: list[int] | None
    ) -> list[tuple[int, float]]:
        vector = list(self.model.query_embed([query]))[0]
        blob = _serialize_f32(vector)

        if candidates is None:
            sql = (
                "SELECT rowid, distance FROM vec_chunks "
                "WHERE embedding MATCH ? AND k = ? ORDER BY distance"
            )
            rows = self.db.execute(sql, (blob, k)).fetchall()
        else:
            if not candidates:
                return []
            placeholders = ",".join("?" * len(candidates))
            sql = (
                f"SELECT rowid, distance FROM vec_chunks "
                f"WHERE embedding MATCH ? AND k = ? AND rowid IN ({placeholders}) "
                f"ORDER BY distance"
            )
            rows = self.db.execute(
                sql, (blob, min(k, len(candidates)), *candidates)
            ).fetchall()

        # Cosine distance on L2-normalized vectors → similarity = 1 - distance.
        return [(rowid, 1.0 - dist) for rowid, dist in rows]

    def _keyword_search(
        self, query: str, k: int, candidates: list[int] | None
    ) -> list[tuple[int, float]]:
        fts_query = _to_fts_query(query)
        if not fts_query:
            return []

        sql = (
            "SELECT rowid, bm25(fts_chunks) AS score FROM fts_chunks "
            "WHERE fts_chunks MATCH ?"
        )
        params: list = [fts_query]
        if candidates is not None:
            if not candidates:
                return []
            placeholders = ",".join("?" * len(candidates))
            sql += f" AND rowid IN ({placeholders})"
            params.extend(candidates)
        sql += " ORDER BY score LIMIT ?"
        params.append(k)

        try:
            rows = self.db.execute(sql, params).fetchall()
        except sqlite3.OperationalError as exc:
            # Malformed FTS5 expression (unbalanced quotes, bare operators).
            logger.debug("fts query rejected (%s): %r", exc, fts_query)
            return []

        # bm25() returns negative values, more negative = better.
        return [(rowid, -score) for rowid, score in rows]

    def _recency_multiplier(self, updated: str | None) -> float:
        if not updated:
            return 1.0
        try:
            when = datetime.fromisoformat(updated)
        except ValueError:
            return 1.0
        age_days = max(0.0, (datetime.now() - when).total_seconds() / 86400.0)
        decay = math.exp(-age_days / RECENCY_HALFLIFE_DAYS)
        return 1.0 + RECENCY_BOOST * decay

    def search(
        self,
        query: str,
        top_k: int = 5,
        tags: list[str] | None = None,
        doc_type: str | None = None,
        project: str | None = None,
        source_type: str | None = None,
        recency_boost: bool = True,
        trace: "SearchTrace | None" = None,
    ) -> list[dict]:
        """Hybrid search: vector + keyword, RRF-fused, MMR-reranked."""
        from .trace import (
            SearchTrace, TraceQuery, TraceDenseStage, TraceDenseResult,
            TraceKeywordStage, TraceKeywordResult, TraceFusionStage, TraceFusedItem,
            TraceMMRStage, TraceMMRStep, TraceChunkMeta,
        )

        if not query or not query.strip():
            return []
        if self.is_empty():
            return []

        t_start = time.time()

        # Auto-trace when broadcast listeners are connected, even if caller
        # didn't explicitly request tracing. Zero overhead when no listeners.
        if trace is None and _has_trace_listeners():
            trace = SearchTrace()

        # Initialize trace if requested
        if trace is not None:
            trace.query = TraceQuery(
                query=query,
                top_k=top_k,
                filters={
                    k: v for k, v in
                    {"tags": tags, "doc_type": doc_type, "project": project, "source_type": source_type}.items()
                    if v is not None
                },
            )

        # Over-fetch so fusion and reranking have room to work.
        fetch_k = max(top_k * 4, 20)
        candidates = self._candidate_rowids(tags, doc_type, project, source_type)
        if candidates is not None and not candidates:
            return []

        if trace is not None:
            trace.candidates_filtered = len(candidates) if candidates is not None else None

        # --- Dense retrieval ---
        t_dense = time.time()
        vector_hits = self._vector_search(query, fetch_k, candidates)
        t_dense_end = time.time()

        if trace is not None:
            dense_meta = self._fetch_chunk_meta([rid for rid, _ in vector_hits])
            trace.dense = TraceDenseStage(
                results=[
                    TraceDenseResult(
                        chunk_id=rid,
                        path=dense_meta.get(rid, {}).get("path", ""),
                        title=dense_meta.get(rid, {}).get("title"),
                        section=dense_meta.get(rid, {}).get("section"),
                        cosine_similarity=round(score, 6),
                    )
                    for rid, score in vector_hits
                ],
                fetch_k=fetch_k,
                elapsed_ms=round((t_dense_end - t_dense) * 1000, 2),
            )

        # --- Keyword retrieval ---
        t_kw = time.time()
        keyword_hits = self._keyword_search(query, fetch_k, candidates)
        t_kw_end = time.time()

        if trace is not None:
            kw_meta = self._fetch_chunk_meta([rid for rid, _ in keyword_hits])
            trace.keyword = TraceKeywordStage(
                fts_query=_to_fts_query(query),
                results=[
                    TraceKeywordResult(
                        chunk_id=rid,
                        path=kw_meta.get(rid, {}).get("path", ""),
                        title=kw_meta.get(rid, {}).get("title"),
                        section=kw_meta.get(rid, {}).get("section"),
                        bm25_score=round(score, 6),
                    )
                    for rid, score in keyword_hits
                ],
                fetch_k=fetch_k,
                elapsed_ms=round((t_kw_end - t_kw) * 1000, 2),
            )

        if not vector_hits and not keyword_hits:
            return []

        # --- RRF Fusion ---
        fused = _reciprocal_rank_fusion([vector_hits, keyword_hits])
        similarity = dict(vector_hits)

        if trace is not None:
            dense_rank_map = {rid: i for i, (rid, _) in enumerate(vector_hits)}
            kw_rank_map = {rid: i for i, (rid, _) in enumerate(keyword_hits)}
            trace.fusion = TraceFusionStage(
                results=[
                    TraceFusedItem(
                        chunk_id=rid,
                        rrf_score=round(score, 6),
                        dense_rank=dense_rank_map.get(rid),
                        keyword_rank=kw_rank_map.get(rid),
                        sources=[s for s in ['dense', 'keyword']
                                 if (s == 'dense' and rid in dense_rank_map) or
                                    (s == 'keyword' and rid in kw_rank_map)],
                    )
                    for rid, score in fused
                ],
                rrf_k=RRF_K,
                recency_applied=recency_boost,
            )

        if recency_boost:
            updated_by_id = self._fetch_updated({rid for rid, _ in fused})
            fused = [
                (rid, score * self._recency_multiplier(updated_by_id.get(rid)))
                for rid, score in fused
            ]
            fused.sort(key=lambda pair: pair[1], reverse=True)

        # --- MMR reranking ---
        t_mmr = time.time()
        ordered_ids = self._mmr_rerank(
            [rid for rid, _ in fused], similarity, top_k, trace=trace,
        )
        t_mmr_end = time.time()

        if trace is not None and trace.mmr is not None:
            trace.mmr.elapsed_ms = round((t_mmr_end - t_mmr) * 1000, 2)

        # --- Hydrate ---
        results = self._hydrate(ordered_ids, fused_scores=dict(fused), similarity=similarity)

        # --- Finalize trace ---
        if trace is not None:
            trace.total_elapsed_ms = round((time.time() - t_start) * 1000, 2)
            # Collect chunk metadata for all chunks involved
            all_ids = set()
            if trace.dense:
                all_ids.update(r.chunk_id for r in trace.dense.results)
            if trace.keyword:
                all_ids.update(r.chunk_id for r in trace.keyword.results)
            chunk_meta_map = self._fetch_chunk_meta(list(all_ids))

            # Project embeddings to 2D grid positions (PCA)
            # Use a standard grid size — hyperfield will remap to its actual dimensions
            TRACE_GRID_COLS = 80
            TRACE_GRID_ROWS = 80
            all_embeddings = self._fetch_embeddings(list(all_ids))
            positions = _project_embeddings_2d(all_embeddings, TRACE_GRID_COLS, TRACE_GRID_ROWS)

            trace.chunk_meta = [
                TraceChunkMeta(
                    chunk_id=rid,
                    path=meta.get("path", ""),
                    title=meta.get("title"),
                    section=meta.get("section"),
                    doc_type=meta.get("doc_type"),
                    tags=meta.get("tags", []),
                    grid_col=positions.get(rid, (TRACE_GRID_COLS // 2, TRACE_GRID_ROWS // 2))[0],
                    grid_row=positions.get(rid, (TRACE_GRID_COLS // 2, TRACE_GRID_ROWS // 2))[1],
                )
                for rid, meta in chunk_meta_map.items()
            ]

            # Broadcast to any connected listeners (Hyperfield)
            _broadcast_trace(trace, len(results))

        return results

    def _fetch_updated(self, rowids: set[int]) -> dict[int, str | None]:
        if not rowids:
            return {}
        placeholders = ",".join("?" * len(rowids))
        rows = self.db.execute(
            f"SELECT id, updated FROM chunks WHERE id IN ({placeholders})",
            tuple(rowids),
        ).fetchall()
        return {rid: updated for rid, updated in rows}

    def _fetch_embeddings(self, rowids: list[int]) -> dict[int, list[float]]:
        if not rowids:
            return {}
        placeholders = ",".join("?" * len(rowids))
        rows = self.db.execute(
            f"SELECT rowid, embedding FROM vec_chunks WHERE rowid IN ({placeholders})",
            tuple(rowids),
        ).fetchall()
        out = {}
        for rowid, blob in rows:
            count = len(blob) // 4
            out[rowid] = list(struct.unpack(f"{count}f", blob))
        return out

    def _fetch_chunk_meta(self, rowids: list[int]) -> dict[int, dict]:
        """Fetch lightweight metadata for a set of chunk IDs (for tracing)."""
        if not rowids:
            return {}
        placeholders = ",".join("?" * len(rowids))
        rows = self.db.execute(
            f"SELECT id, path, title, section, doc_type, tags FROM chunks "
            f"WHERE id IN ({placeholders})",
            tuple(rowids),
        ).fetchall()
        return {
            r[0]: {
                "path": r[1],
                "title": r[2],
                "section": r[3],
                "doc_type": r[4],
                "tags": json.loads(r[5]) if r[5] else [],
            }
            for r in rows
        }

    def _mmr_rerank(
        self, rowids: list[int], similarity: dict[int, float], top_k: int,
        trace: "SearchTrace | None" = None,
    ) -> list[int]:
        """Greedy MMR selection to keep the result set diverse.

        Without this, a concept documented in three places consumes three of
        five result slots with near-identical text.
        """
        if len(rowids) <= 1:
            return rowids[:top_k]

        embeddings = self._fetch_embeddings(rowids)
        if not embeddings:
            return rowids[:top_k]

        # Rank position stands in for query relevance when a row surfaced only
        # via keyword search and has no cosine similarity.
        fallback = {rid: 1.0 / (i + 1) for i, rid in enumerate(rowids)}

        selected: list[int] = []
        remaining = [r for r in rowids if r in embeddings]

        # Import trace types only when tracing
        if trace is not None:
            from .trace import TraceMMRStage, TraceMMRStep
            trace.mmr = TraceMMRStage(mmr_lambda=MMR_LAMBDA)

        while remaining and len(selected) < top_k:
            best_id = None
            best_score = -math.inf
            round_candidates = []
            for rid in remaining:
                relevance = similarity.get(rid, fallback[rid])
                if selected:
                    redundancy = max(
                        _cosine(embeddings[rid], embeddings[s]) for s in selected
                    )
                else:
                    redundancy = 0.0
                score = MMR_LAMBDA * relevance - (1.0 - MMR_LAMBDA) * redundancy
                round_candidates.append((rid, relevance, redundancy, score))
                if score > best_score:
                    best_score = score
                    best_id = rid

            # Emit trace steps for this round
            if trace is not None:
                for rid, relevance, redundancy, score in round_candidates:
                    trace.mmr.steps.append(TraceMMRStep(
                        chunk_id=rid,
                        relevance=round(relevance, 6),
                        max_redundancy=round(redundancy, 6),
                        mmr_score=round(score, 6),
                        selected=(rid == best_id),
                    ))

            selected.append(best_id)
            remaining.remove(best_id)

        # Any rows without embeddings fall in behind, preserving fused order.
        for rid in rowids:
            if len(selected) >= top_k:
                break
            if rid not in selected:
                selected.append(rid)

        if trace is not None and trace.mmr is not None:
            trace.mmr.final_ids = selected[:top_k]

        return selected[:top_k]

    def _hydrate(
        self,
        rowids: list[int],
        fused_scores: dict[int, float],
        similarity: dict[int, float],
    ) -> list[dict]:
        if not rowids:
            return []
        placeholders = ",".join("?" * len(rowids))
        rows = self.db.execute(
            f"""
            SELECT id, path, title, section, content, doc_type, source_type,
                   project, status, tags, updated, token_count
            FROM chunks WHERE id IN ({placeholders})
            """,
            tuple(rowids),
        ).fetchall()

        by_id = {}
        for r in rows:
            by_id[r[0]] = {
                "chunk_id": r[0],
                "path": r[1],
                "title": r[2],
                "section": r[3],
                "content": r[4],
                "doc_type": r[5],
                "source_type": r[6],
                "project": r[7],
                "status": r[8],
                "tags": json.loads(r[9]) if r[9] else [],
                "updated": r[10],
                "token_count": r[11],
                "similarity": round(similarity.get(r[0], 0.0), 4),
                "score": round(fused_scores.get(r[0], 0.0), 6),
                "matched_by": "vector" if r[0] in similarity else "keyword",
            }

        return [by_id[rid] for rid in rowids if rid in by_id]

    # -- introspection -----------------------------------------------------

    def stats(self) -> dict:
        db = self.db
        chunks = self.chunk_count()
        docs = db.execute("SELECT COUNT(*) FROM doc_hashes").fetchone()[0]
        by_type = dict(
            db.execute(
                "SELECT doc_type, COUNT(*) FROM chunks GROUP BY doc_type ORDER BY 2 DESC"
            ).fetchall()
        )
        token_stats = db.execute(
            "SELECT MIN(token_count), MAX(token_count), AVG(token_count) FROM chunks"
        ).fetchone()
        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0
        return {
            "documents": docs,
            "chunks": chunks,
            "chunks_by_type": by_type,
            "tokens_min": token_stats[0],
            "tokens_max": token_stats[1],
            "tokens_avg": round(token_stats[2], 1) if token_stats[2] else None,
            "db_bytes": db_size,
            "db_path": str(self.db_path),
            "model": self.model_name,
            "model_max_tokens": MODEL_MAX_TOKENS,
        }


# ---------------------------------------------------------------------------
# Ranking primitives
# ---------------------------------------------------------------------------

def _cosine(a, b) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def _reciprocal_rank_fusion(
    rankings: list[list[tuple[int, float]]], k: int = RRF_K
) -> list[tuple[int, float]]:
    """Fuse ranked lists by reciprocal rank.

    Scale-free by construction, which is why it beats trying to normalize
    cosine similarity and BM25 onto a shared scale.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, (rowid, _score) in enumerate(ranking):
            scores[rowid] = scores.get(rowid, 0.0) + 1.0 / (k + rank + 1)
    fused = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    return fused


_FTS_SAFE_RE = re.compile(r"[^0-9A-Za-z_\-]+")

# In an OR-joined FTS query, stopwords match nearly every row and flatten the
# bm25 ranking. Dropping them lets the content words carry the score.
_FTS_STOPWORDS = frozenset(
    """
    a an and are as at be been but by can did do does for from had has have how
    i if in into is it its of on or our so than that the their them then there
    these they this to was were what when where which who why will with would you
    your
    """.split()
)


def _to_fts_query(query: str) -> str:
    """Convert free text into a safe FTS5 OR-expression.

    FTS5 treats characters like `"`, `*`, `:`, `(`, `-` as syntax, so each token
    is quoted individually rather than passing user text through as an
    expression. Stopwords are dropped; if a query is nothing but stopwords the
    keyword arm returns nothing and the vector arm carries the search.
    """
    tokens = [t for t in _FTS_SAFE_RE.split(query) if len(t) > 1]
    meaningful = [t for t in tokens if t.lower() not in _FTS_STOPWORDS]
    chosen = meaningful or tokens
    if not chosen:
        return ""
    return " OR ".join(f'"{t}"' for t in chosen)


# ---------------------------------------------------------------------------
# Trace broadcast hooks — called by HyperspaceRAG.search() when listeners exist
# The actual listener list lives in mcp-server.py; these are stubs that get
# monkey-patched at server startup. When running standalone (tests, CLI),
# they're no-ops.
# ---------------------------------------------------------------------------

def _project_embeddings_2d(
    embeddings: dict[int, list[float]], grid_cols: int, grid_rows: int, padding: int = 3
) -> dict[int, tuple[int, int]]:
    """Project high-dimensional embeddings to 2D grid positions via PCA.

    Returns {chunk_id: (col, row)} mapping. Chunks that are semantically
    similar will land near each other on the grid.
    """
    if not embeddings or len(embeddings) < 2:
        # Single point — put it at center
        for rid in embeddings:
            return {rid: (grid_cols // 2, grid_rows // 2)}
        return {}

    import numpy as np

    ids = list(embeddings.keys())
    matrix = np.array([embeddings[rid] for rid in ids], dtype=np.float32)

    # PCA: center, compute top-2 eigenvectors via SVD
    mean = matrix.mean(axis=0)
    centered = matrix - mean
    # Economy SVD — we only need 2 components
    U, S, Vt = np.linalg.svd(centered, full_matrices=False)
    # Project onto first 2 principal components
    proj = centered @ Vt[:2].T  # shape: (n_chunks, 2)

    # Normalize to grid coordinates with padding
    min_vals = proj.min(axis=0)
    max_vals = proj.max(axis=0)
    ranges = max_vals - min_vals
    # Avoid division by zero if all points collapse
    ranges[ranges < 1e-6] = 1.0

    usable_cols = grid_cols - padding * 2
    usable_rows = grid_rows - padding * 2

    normalized = (proj - min_vals) / ranges  # 0-1
    cols = (normalized[:, 0] * usable_cols + padding).astype(int)
    rows = (normalized[:, 1] * usable_rows + padding).astype(int)

    # Clamp
    cols = np.clip(cols, padding, grid_cols - padding - 1)
    rows = np.clip(rows, padding, grid_rows - padding - 1)

    return {ids[i]: (int(cols[i]), int(rows[i])) for i in range(len(ids))}
# ---------------------------------------------------------------------------

_trace_listener_check = None   # set to a callable by mcp-server.py
_trace_broadcast_fn = None     # set to a callable by mcp-server.py


def _has_trace_listeners() -> bool:
    """Check if any Hyperfield instances are listening for traces."""
    if _trace_listener_check is None:
        return False
    return _trace_listener_check()


def _broadcast_trace(trace, result_count: int):
    """Broadcast a completed trace to all connected listeners."""
    if _trace_broadcast_fn is None:
        return
    _trace_broadcast_fn(trace, result_count)


# ---------------------------------------------------------------------------
# Module singleton + watcher hooks
# ---------------------------------------------------------------------------

_rag: HyperspaceRAG | None = None
_rag_lock = threading.Lock()


def get_rag() -> HyperspaceRAG:
    """Return the process-wide RAG instance, constructing it on first call."""
    global _rag
    with _rag_lock:
        if _rag is None:
            _rag = HyperspaceRAG()
    return _rag


def is_initialized() -> bool:
    """Whether the RAG singleton exists. Used to keep watcher hooks free."""
    return _rag is not None


def on_file_changed(rel_path: str):
    """Watcher hook: re-index a single document after a save."""
    if not is_initialized() or not is_indexable(rel_path):
        return
    try:
        get_rag().index_document(rel_path)
    except Exception as exc:  # noqa: BLE001 — watcher must never die
        logger.warning("reindex failed for %s: %s", rel_path, exc)


def on_file_deleted(rel_path: str):
    """Watcher hook: drop a deleted document from the index."""
    if not is_initialized() or not is_indexable(rel_path):
        return
    try:
        get_rag().remove_document(rel_path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("removal failed for %s: %s", rel_path, exc)
