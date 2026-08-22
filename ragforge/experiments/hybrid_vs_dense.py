"""
experiments/hybrid_vs_dense.py — A/B Retrieval Experiment
============================================================

This is Step 1 of the Phase 3 experiment harness. It runs each retrieval
strategy against every question in eval/qa_pairs.json and prints a
comparison table showing retrieval quality and latency.

Usage:
    cd ragforge
    python experiments/hybrid_vs_dense.py

    # or limit top-k:
    python experiments/hybrid_vs_dense.py --top-k 5

What "hit" means:
    A "hit" is when the expected source document is found in the top-k
    retrieved chunks. Hit Rate (also called Recall@K or Hit@K) is the
    fraction of queries for which at least one expected source is retrieved.

    It does NOT measure whether the answer is correct — only whether the
    right document was retrieved. Generation quality is a separate concern.

Why compare strategies?
    Dense search and BM25 have complementary failure modes:
    - Dense fails on exact-match queries (typos, model numbers, rare terms).
    - BM25 fails on semantic/paraphrase queries.
    - Hybrid (RRF) captures both signals.
    - Reranking refines the order but doesn't change recall (same candidate pool).

    This script makes those trade-offs measurable and visible.
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

# ── Path setup: allow running from any directory ──────────────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import retrieve_with_timing
from src.query.rewrite import normalize_query


# ── Strategies to benchmark (in display order) ───────────────────────────────
STRATEGIES = ["dense", "bm25", "hybrid", "hybrid_rerank"]

STRATEGY_DISPLAY = {
    "dense":         "Dense (vector only)       ",
    "bm25":          "BM25 (keyword only)       ",
    "hybrid":        "Hybrid (Dense+BM25+RRF)   ",
    "hybrid_rerank": "Hybrid + Reranker         ",
}


def load_qa_pairs(path: Path) -> List[Dict]:
    """Load Q&A evaluation pairs from JSON, skipping placeholder/comment entries."""
    if not path.exists():
        print(f"❌ Eval file not found: {path}")
        print(f"   Create it at: {path}")
        sys.exit(1)

    with path.open(encoding="utf-8") as f:
        pairs = json.load(f)

    # Filter out entries that still use placeholder source names
    real_pairs = [
        p for p in pairs
        if "_comment" not in p
        and not any("your_document" in s for s in p.get("expected_sources", []))
    ]

    if not real_pairs:
        print("\n⚠️  eval/qa_pairs.json only contains placeholder questions.")
        print("   To run a real benchmark, add questions like this:\n")
        print('   {"question": "What is X?", "expected_sources": ["your_actual_file.pdf"]}')
        print("\n   Running with placeholder pairs skipped — no results to show.\n")
        sys.exit(0)

    return real_pairs


def evaluate_strategy(
    strategy: str,
    qa_pairs: List[Dict],
    top_k: int,
) -> Dict:
    """
    Run retrieval for every Q&A pair and compute Hit Rate + avg latency.

    Returns a dict with keys: hits, total, hit_rate, avg_latency_ms, latencies.
    """
    hits = 0
    latencies = []

    for pair in qa_pairs:
        query = pair["question"]
        expected_sources = set(pair.get("expected_sources", []))

        # Normalise the query (fix typos) before embedding — same as in the UI
        query = normalize_query(query)

        try:
            results, meta = retrieve_with_timing(query, top_k=top_k, strategy=strategy)
        except Exception as e:
            print(f"   ⚠️  [{strategy}] failed for query '{query[:60]}': {e}")
            latencies.append(0)
            continue

        latencies.append(meta["total_ms"])

        # A hit = at least one result's source matches an expected source
        retrieved_sources = {r.get("source", "") for r in results}
        if retrieved_sources & expected_sources:
            hits += 1

    total = len(qa_pairs)
    hit_rate = (hits / total * 100) if total > 0 else 0.0
    avg_latency = round(sum(latencies) / len(latencies)) if latencies else 0

    return {
        "hits": hits,
        "total": total,
        "hit_rate": hit_rate,
        "avg_latency_ms": avg_latency,
        "latencies": latencies,
    }


def print_results(results: Dict[str, Dict], top_k: int, qa_pairs: List[Dict]):
    """Print a formatted comparison table to stdout."""
    print("\n" + "=" * 72)
    print(f"  RAGForge — Retrieval Benchmark  |  top_k={top_k}  |  {len(qa_pairs)} question(s)")
    print("=" * 72)
    print(
        f"\n  {'Strategy':<32}  {'Hit Rate':>10}  {'Hits':>6}  {'Avg Latency':>12}"
    )
    print(f"  {'-'*32}  {'-'*10}  {'-'*6}  {'-'*12}")

    # Sort by hit rate descending, then by latency ascending
    sorted_strategies = sorted(
        STRATEGIES,
        key=lambda s: (-results[s]["hit_rate"], results[s]["avg_latency_ms"]),
    )

    for strategy in sorted_strategies:
        r = results[strategy]
        label = STRATEGY_DISPLAY.get(strategy, strategy)
        print(
            f"  {label:<32}  {r['hit_rate']:>9.1f}%  "
            f"{r['hits']:>3}/{r['total']:<3}  "
            f"{r['avg_latency_ms']:>8} ms"
        )

    print("\n" + "=" * 72)

    # ── Per-question breakdown ───────────────────────────────────────────────
    print("\n  Per-question breakdown (latency in ms):\n")
    print(f"  {'#':<3}  {'Question':<45}  " + "  ".join(
        f"{STRATEGY_DISPLAY[s].strip()[:10]:>10}" for s in STRATEGIES
    ))
    print(f"  {'-'*3}  {'-'*45}  " + "  ".join(f"{'─'*10}" for _ in STRATEGIES))

    for i, pair in enumerate(qa_pairs):
        q_short = pair["question"][:44]
        latency_cols = "  ".join(
            f"{results[s]['latencies'][i]:>10}ms" for s in STRATEGIES
        )
        print(f"  {i+1:<3}  {q_short:<45}  {latency_cols}")

    print("\n" + "=" * 72)

    # ── Learning notes ───────────────────────────────────────────────────────
    best = sorted_strategies[0]
    print(f"\n  🏆 Best strategy: {STRATEGY_DISPLAY[best].strip()}")
    print(
        """
  Key things to notice:
  ─────────────────────
  • Dense vs BM25: does semantic or keyword search work better for YOUR docs?
  • Hybrid vs Dense: does BM25 bring in hits that semantic search missed?
  • Hybrid vs Hybrid+Rerank: reranking changes ORDER but not RECALL (same pool).
    A strategy can have identical hit rates but better answer quality because
    the most relevant chunk is now at position #1.
  • Latency: Dense ≈ BM25 < Hybrid << Hybrid+Reranker.
    The CrossEncoder adds ~50-200ms per query.

  To see WHY results differ, re-run with DEBUG=1:
    DEBUG=1 python experiments/hybrid_vs_dense.py
"""
    )


def print_debug(strategy: str, query: str, results, meta: Dict):
    """Print detailed per-query debug info when DEBUG env var is set."""
    print(f"\n  [{strategy.upper()}] Query: '{query}'")
    print(f"  Latency: {meta['total_ms']}ms  |  Results: {meta['num_results']}")
    for i, r in enumerate(results, start=1):
        method = r.get("retrieval_method", "?")
        dist = r.get("distance")
        bm25 = r.get("bm25_score")
        rerank = r.get("rerank_score")
        score_parts = []
        if dist is not None:
            score_parts.append(f"dist={dist:.4f}")
        if bm25 is not None:
            score_parts.append(f"bm25={bm25:.4f}")
        if rerank is not None:
            score_parts.append(f"rerank={rerank:.4f}")
        scores = " | ".join(score_parts)
        print(f"    #{i} [{method}] {r.get('source')}:p{r.get('page')} | {scores}")
        print(f"       {r.get('text', '')[:120]}…")


def main():
    parser = argparse.ArgumentParser(
        description="Compare retrieval strategies on your eval dataset."
    )
    parser.add_argument(
        "--top-k", type=int, default=5, help="Number of chunks to retrieve per query."
    )
    args = parser.parse_args()

    import os
    debug = os.environ.get("DEBUG", "").strip() == "1"

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)

    print(f"\n🔬 RAGForge Retrieval Experiment")
    print(f"   Eval set:  {qa_path}")
    print(f"   Questions: {len(qa_pairs)}")
    print(f"   Top-K:     {args.top_k}")
    print(f"   Strategies: {', '.join(STRATEGIES)}\n")

    results = {}
    for strategy in STRATEGIES:
        print(f"  ⏳ Running {STRATEGY_DISPLAY[strategy].strip()}...", end="", flush=True)
        t_start = time.perf_counter()

        # Run evaluation, with optional debug output
        hits = 0
        latencies = []
        for pair in qa_pairs:
            query = normalize_query(pair["question"])
            expected_sources = set(pair.get("expected_sources", []))
            try:
                chunks, meta = retrieve_with_timing(query, top_k=args.top_k, strategy=strategy)
                latencies.append(meta["total_ms"])
                if {r.get("source", "") for r in chunks} & expected_sources:
                    hits += 1
                if debug:
                    print_debug(strategy, query, chunks, meta)
            except Exception as e:
                print(f"\n   ⚠️  Error: {e}")
                latencies.append(0)

        total_ms = round((time.perf_counter() - t_start) * 1000)
        total = len(qa_pairs)
        hit_rate = hits / total * 100 if total else 0

        results[strategy] = {
            "hits": hits,
            "total": total,
            "hit_rate": hit_rate,
            "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
            "latencies": latencies,
        }
        print(f" done ({total_ms}ms total). Hit rate: {hit_rate:.0f}%")

    print_results(results, args.top_k, qa_pairs)


if __name__ == "__main__":
    main()
