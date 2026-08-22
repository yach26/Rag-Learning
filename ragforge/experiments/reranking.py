"""
experiments/reranking.py — Step 2: CrossEncoder Reranking Experiment
======================================================================

Benchmarks "Hybrid" vs "Hybrid + Reranker" to answer the key question:

    "Does the CrossEncoder's precision gain justify its latency cost?"

IMPORTANT: Reranking does NOT change recall.
    hybrid and hybrid_rerank pull from the same candidate pool (same chunks).
    The reranker only changes ORDER — it moves the most relevant chunk to #1.
    So Hit@K is often identical; the value shows up in answer quality
    (when the LLM only reads the top-N chunks, the order matters a lot).

This experiment measures:
    - Hit@K (same pool → usually equal, but sometimes improves for small K)
    - Position of first relevant chunk (precision metric — lower = better)
    - Mean Reciprocal Rank (MRR)
    - Reranker latency vs hybrid-only latency

Usage:
    cd ragforge
    venv\\Scripts\\python experiments/reranking.py --top-k 5

Output:
    A comparison table + per-question MRR and position breakdown.

When reranking helps:
    - The most relevant chunk was at rank 3-5 after RRF; reranker moves it to 1.
    - This is common when BM25 promotes keyword-heavy-but-less-relevant chunks.

When reranking does NOT help much:
    - The most relevant chunk was already at rank 1 after RRF.
    - For simple, unambiguous queries, RRF ordering is already near-optimal.
    - Every query pays the latency cost even when it doesn't need it.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import retrieve_with_timing
from src.query.rewrite import normalize_query


def load_qa_pairs(path: Path) -> List[Dict]:
    with path.open(encoding="utf-8") as f:
        pairs = json.load(f)
    real_pairs = [
        p for p in pairs
        if "_comment" not in p
        and not any("your_document" in s for s in p.get("expected_sources", []))
    ]
    if not real_pairs:
        print("\n⚠️  eval/qa_pairs.json only has placeholder questions.")
        print("   Add real questions to run this benchmark.")
        sys.exit(0)
    return real_pairs


def first_hit_position(results: List[Dict], expected_sources) -> Optional[int]:
    """Return the 1-indexed position of the first relevant result, or None."""
    for i, r in enumerate(results, start=1):
        if r.get("source", "") in expected_sources:
            return i
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Compare Hybrid vs Hybrid+Reranker retrieval."
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)

    strategies = ["hybrid", "hybrid_rerank"]
    results_by_strategy: Dict[str, Dict] = {s: {"hits": 0, "positions": [], "rr": [], "latencies": []} for s in strategies}

    print(f"\n🔬 RAGForge — Reranking Experiment")
    print(f"   Strategies: {' vs '.join(strategies)}")
    print(f"   Top-K: {args.top_k}  |  Questions: {len(qa_pairs)}\n")

    for pair in qa_pairs:
        query = normalize_query(pair["question"])
        expected = set(pair.get("expected_sources", []))

        for strategy in strategies:
            try:
                chunks, meta = retrieve_with_timing(query, top_k=args.top_k, strategy=strategy)
            except Exception as e:
                print(f"   ⚠️  [{strategy}] error: {e}")
                results_by_strategy[strategy]["latencies"].append(0)
                results_by_strategy[strategy]["positions"].append(None)
                results_by_strategy[strategy]["rr"].append(0.0)
                continue

            results_by_strategy[strategy]["latencies"].append(meta["total_ms"])
            pos = first_hit_position(chunks, expected)
            results_by_strategy[strategy]["positions"].append(pos)

            if pos is not None:
                results_by_strategy[strategy]["hits"] += 1
                results_by_strategy[strategy]["rr"].append(1.0 / pos)
            else:
                results_by_strategy[strategy]["rr"].append(0.0)

    # ── Print results ─────────────────────────────────────────────────────────
    total = len(qa_pairs)
    print("\n" + "=" * 72)
    print(f"  Results  (top_k={args.top_k}, {total} question(s))")
    print("=" * 72)
    print(f"\n  {'Strategy':<28} {'Hit@K':>8} {'MRR':>8} {'Avg Pos':>10} {'Avg Latency':>14}")
    print(f"  {'-'*28} {'-'*8} {'-'*8} {'-'*10} {'-'*14}")

    for strategy in strategies:
        r = results_by_strategy[strategy]
        hits = r["hits"]
        hit_rate = hits / total * 100 if total else 0
        mrr = sum(r["rr"]) / len(r["rr"]) if r["rr"] else 0
        valid_positions = [p for p in r["positions"] if p is not None]
        avg_pos = sum(valid_positions) / len(valid_positions) if valid_positions else float("inf")
        avg_lat = round(sum(r["latencies"]) / len(r["latencies"])) if r["latencies"] else 0

        label = "Hybrid (Dense+BM25+RRF)  " if strategy == "hybrid" else "Hybrid + CrossEncoder    "
        print(f"  {label:<28} {hit_rate:>7.1f}% {mrr:>8.3f} {avg_pos:>10.2f} {avg_lat:>11} ms")

    # ── Per-question breakdown ────────────────────────────────────────────────
    print(f"\n\n  Per-question breakdown:\n")
    print(f"  {'#':<3}  {'Question':<42}  {'hybrid pos':>11}  {'rerank pos':>11}  {'Δ pos':>7}")
    print(f"  {'-'*3}  {'-'*42}  {'-'*11}  {'-'*11}  {'-'*7}")

    for i, pair in enumerate(qa_pairs):
        q_short = pair["question"][:42]
        h_pos = results_by_strategy["hybrid"]["positions"][i]
        r_pos = results_by_strategy["hybrid_rerank"]["positions"][i]
        h_str = f"#{h_pos}" if h_pos else "miss"
        r_str = f"#{r_pos}" if r_pos else "miss"

        delta = ""
        if h_pos and r_pos:
            diff = h_pos - r_pos
            if diff > 0:
                delta = f"↑ {diff}"   # reranker improved position
            elif diff < 0:
                delta = f"↓ {abs(diff)}"  # reranker made it worse
            else:
                delta = "="
        elif h_pos and not r_pos:
            delta = "↓ miss"
        elif r_pos and not h_pos:
            delta = "↑ found"

        print(f"  {i+1:<3}  {q_short:<42}  {h_str:>11}  {r_str:>11}  {delta:>7}")

    print("\n" + "=" * 72)
    print("""
  Understanding the results:
  ──────────────────────────
  • Hit@K is the same (or very close): Reranking doesn't change the POOL
    of documents — it reorders them. If the right chunk wasn't in the top-20
    candidates from hybrid search, the reranker can't rescue it.

  • MRR shows whether the reranker improved ORDER: A higher MRR means the
    most relevant chunk is higher in the final list (closer to #1). The LLM
    reads chunks top-to-bottom, so position #1 matters a lot.

  • Avg Position: If hybrid gives you rank #3 and reranker gives you rank #1,
    the generation quality will improve even though Hit@K is identical.

  • Latency: The CrossEncoder adds ~50-200ms per query even when the
    ordering wouldn't have changed anyway. This is the core trade-off.

  Practical rule: Use hybrid_rerank when answer quality matters more than
  speed. Use hybrid when you need sub-100ms retrieval (e.g. real-time apps).
""")


if __name__ == "__main__":
    main()
