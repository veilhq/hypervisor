"""Retrieval eval for the hyperspace RAG: recall@5 and MRR over a golden query set.

Run from the .hypervisor directory:
    python tests/rag_eval/run_eval.py [--db PATH] [--json] [--top-k 5]

Without --db a temporary database is built over the real corpus (takes
minutes) and its path is printed so it can be reused with --db. The live
rag.db is never opened.
"""

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from hv_mcp.rag import HyperspaceRAG  # noqa: E402

KINDS = ("paraphrase", "id", "no-answer")


def ranked_paths(results: list[dict]) -> list[str]:
    seen: list[str] = []
    for r in results:
        if r["path"] not in seen:
            seen.append(r["path"])
    return seen


def score_query(expected: list[str], paths: list[str]) -> tuple[float, float]:
    hits = [p for p in expected if p in paths]
    recall = len(hits) / len(expected)
    ranks = [paths.index(p) + 1 for p in hits]
    return recall, (1.0 / min(ranks) if ranks else 0.0)


def summarize(rows: list[dict]) -> dict:
    scored = [r for r in rows if r["expected_paths"]]
    out = {"queries": len(rows), "scored": len(scored)}
    if scored:
        out["recall@5"] = sum(r["recall"] for r in scored) / len(scored)
        out["mrr"] = sum(r["rr"] for r in scored) / len(scored)
        out["first_result_hit"] = sum(
            1 for r in scored if r["paths"] and r["paths"][0] in r["expected_paths"]
        ) / len(scored)
    return out


SWEEP_FLOORS = (0.001, 0.005, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.2)


def confidence_report(rows: list[dict]) -> dict:
    """How well the confidence flag separates real hits from no-answer queries."""
    hits = [r for r in rows if r["expected_paths"] and r["hit_rerank"] is not None]
    nos = [r for r in rows if r["kind"] == "no-answer" and r["top_rerank"] is not None]
    # A query's best result is what an agent reads first, so the sweep uses the
    # best expected-hit score for real queries and the top score for no-answer.
    return {
        "hit_queries": len(hits),
        "no_answer_queries": len(nos),
        "hit_high_rate": (
            sum(1 for r in hits if r["hit_confidence"] == "high") / len(hits)
            if hits else 0.0
        ),
        "no_answer_all_low_rate": (
            sum(1 for r in nos if r["all_low"]) / len(nos) if nos else 0.0
        ),
        "hit_rerank_sorted": sorted(round(r["hit_rerank"], 4) for r in hits),
        "no_answer_top_rerank": sorted(round(r["top_rerank"], 4) for r in nos),
        "sweep": [
            {
                "floor": f,
                "hit_kept": sum(1 for r in hits if r["hit_rerank"] >= f) / len(hits) if hits else 0.0,
                "no_answer_flagged": (
                    sum(1 for r in nos if r["top_rerank"] < f) / len(nos) if nos else 0.0
                ),
            }
            for f in SWEEP_FLOORS
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--db", help="reuse a prebuilt temp database instead of indexing")
    ap.add_argument("--golden", default=str(HERE / "golden.json"))
    ap.add_argument("--top-k", type=int, default=5)
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = ap.parse_args()

    log = sys.stderr
    if args.db:
        db_path = Path(args.db)
    else:
        db_path = Path(tempfile.mkdtemp(prefix="rag_eval_")) / "rag_eval.db"
    print(f"eval db: {db_path}", file=log)

    rag = HyperspaceRAG(db_path=db_path)
    if not args.db or rag.is_empty():
        t0 = time.time()
        stats = rag.reindex_changed()
        print(f"indexed in {time.time() - t0:.0f}s: {stats}", file=log)

    golden = json.loads(Path(args.golden).read_text(encoding="utf-8"))
    rows = []
    for g in golden:
        results = rag.search(g["query"], top_k=args.top_k)
        paths = ranked_paths(results)
        if g["expected_paths"]:
            recall, rr = score_query(g["expected_paths"], paths)
        else:
            recall = rr = None
        top = results[0] if results else {}
        hit_results = [
            r for r in results
            if r["path"] in g["expected_paths"] and r.get("rerank_score") is not None
        ]
        best_hit = max(hit_results, key=lambda r: r["rerank_score"], default=None)
        rows.append({
            **g,
            "paths": paths,
            "recall": recall,
            "rr": rr,
            "top_similarity": top.get("similarity"),
            "top_score": top.get("score"),
            "confidence": top.get("confidence"),
            "top_rerank": top.get("rerank_score"),
            "hit_rerank": best_hit["rerank_score"] if best_hit else None,
            "hit_confidence": best_hit["confidence"] if best_hit else None,
            "all_low": bool(results) and all(r.get("confidence") == "low" for r in results),
        })

    report = {"db": str(db_path), "top_k": args.top_k, "overall": summarize(rows)}
    report["by_kind"] = {k: summarize([r for r in rows if r["kind"] == k]) for k in KINDS}
    nos = [r for r in rows if r["kind"] == "no-answer"]
    report["no_answer_top_similarity"] = [r["top_similarity"] for r in nos]
    report["misses"] = [
        {"query": r["query"], "kind": r["kind"], "expected": r["expected_paths"], "got": r["paths"]}
        for r in rows if r["expected_paths"] and r["recall"] < 1.0
    ]
    report["confidence"] = confidence_report(rows)
    report["rows"] = rows

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"\n{'kind':<12}{'n':>4}{'recall@5':>10}{'MRR':>8}{'top1':>8}")
    for name, s in [("overall", report["overall"])] + list(report["by_kind"].items()):
        if "recall@5" in s:
            print(f"{name:<12}{s['scored']:>4}{s['recall@5']:>10.3f}{s['mrr']:>8.3f}{s['first_result_hit']:>8.3f}")
        else:
            print(f"{name:<12}{s['queries']:>4}{'n/a':>10}{'n/a':>8}{'n/a':>8}")
    print("\nno-answer top similarity (higher = more confident-looking):")
    for r in nos:
        print(f"  {r['top_similarity']!s:>8}  {r['query']}")
    c = report["confidence"]
    print(f"\nconfidence at the current floor: real hit high {c['hit_high_rate']:.2f}"
          f" ({c['hit_queries']} queries), no-answer all-low {c['no_answer_all_low_rate']:.2f}"
          f" ({c['no_answer_queries']} queries)")
    print("floor sweep (real hits kept / no-answer flagged):")
    for row in c["sweep"]:
        print(f"  {row['floor']:<7}{row['hit_kept']:>6.2f}{row['no_answer_flagged']:>8.2f}")
    print(f"\nmisses ({len(report['misses'])}):")
    for m in report["misses"]:
        print(f"  [{m['kind']}] {m['query']}\n     expected {m['expected']}\n     got      {m['got']}")
    print(f"\neval db: {db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
