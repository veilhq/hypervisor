"""
RAG Trace — structured instrumentation for the semantic search pipeline.

Emits intermediate state at each pipeline stage for visualization in Hyperfield.
Trace data is either written to a JSON file (replay mode) or streamed over
WebSocket (live mode).

Schema version: 1
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Trace event types — one per pipeline stage
# ---------------------------------------------------------------------------

@dataclass
class TraceQuery:
    """The query that initiated the search."""
    query: str
    top_k: int
    filters: dict[str, Any]  # tags, doc_type, project, source_type
    timestamp: float = field(default_factory=time.time)


@dataclass
class TraceDenseResult:
    """A single chunk from dense (vector) retrieval."""
    chunk_id: int
    path: str
    title: str | None
    section: str | None
    cosine_similarity: float


@dataclass
class TraceDenseStage:
    """Dense retrieval results — all candidates with cosine scores."""
    stage: str = "dense_retrieval"
    results: list[TraceDenseResult] = field(default_factory=list)
    fetch_k: int = 0
    elapsed_ms: float = 0.0


@dataclass
class TraceKeywordResult:
    """A single chunk from keyword (FTS5) retrieval."""
    chunk_id: int
    path: str
    title: str | None
    section: str | None
    bm25_score: float


@dataclass
class TraceKeywordStage:
    """Keyword retrieval results — all candidates with BM25 scores."""
    stage: str = "keyword_retrieval"
    fts_query: str = ""
    results: list[TraceKeywordResult] = field(default_factory=list)
    fetch_k: int = 0
    elapsed_ms: float = 0.0


@dataclass
class TraceFusedItem:
    """A single item in the RRF-fused ranking."""
    chunk_id: int
    rrf_score: float
    dense_rank: int | None    # rank in dense results (None if absent)
    keyword_rank: int | None  # rank in keyword results (None if absent)
    sources: list[str]        # ['dense', 'keyword'] or just one


@dataclass
class TraceFusionStage:
    """RRF fusion output — merged ranking with provenance."""
    stage: str = "rrf_fusion"
    results: list[TraceFusedItem] = field(default_factory=list)
    rrf_k: int = 60
    recency_applied: bool = False


@dataclass
class TraceMMRStep:
    """A single MMR selection step — one item kept or skipped."""
    chunk_id: int
    relevance: float
    max_redundancy: float     # max cosine to any already-selected item
    mmr_score: float          # lambda * relevance - (1-lambda) * redundancy
    selected: bool            # True = kept, False = passed over this round


@dataclass
class TraceMMRStage:
    """MMR reranking — the full selection sequence."""
    stage: str = "mmr_rerank"
    mmr_lambda: float = 0.7
    steps: list[TraceMMRStep] = field(default_factory=list)
    final_ids: list[int] = field(default_factory=list)  # ordered result IDs
    elapsed_ms: float = 0.0


@dataclass
class TraceChunkMeta:
    """Minimal metadata for each chunk involved in the trace."""
    chunk_id: int
    path: str
    title: str | None
    section: str | None
    doc_type: str | None
    tags: list[str]
    grid_col: int = 0   # 2D projected position (PCA of embedding)
    grid_row: int = 0


@dataclass
class SearchTrace:
    """Complete trace for one search invocation."""
    version: int = 1
    query: TraceQuery | None = None
    candidates_filtered: int | None = None  # how many chunks passed pre-filter
    dense: TraceDenseStage | None = None
    keyword: TraceKeywordStage | None = None
    fusion: TraceFusionStage | None = None
    mmr: TraceMMRStage | None = None
    chunk_meta: list[TraceChunkMeta] = field(default_factory=list)
    total_elapsed_ms: float = 0.0

    def to_dict(self) -> dict:
        """Serialize to plain dict (JSON-safe)."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def write(self, path: Path):
        """Write trace to a JSON file for replay."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
