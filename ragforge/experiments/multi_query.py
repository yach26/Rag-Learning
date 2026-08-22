"""
experiments/multi_query.py — Step 4: Multi-Query Retrieval Experiment
========================================================================

Benchmarks "Hybrid + Rerank" (single query) vs "Multi-Query" (multiple queries).

Multi-Query generates 3 alternative phrasings of the original query, runs
hybrid retrieval for all 4 queries, pools/deduplicates the chunks, and
finally reranks them against the original query.

Why do this?
- Recall Boost: Different phrasings catch different keywords. If the user
  asks "database slow", but the doc says "PostgreSQL performance tuning",
  a multi-query generated alternative ("database performance problems")
  might bridge the vocabulary gap.

Trade-offs:
- Latency: LLM generation + 4x retrieval calls + larger reranking pool.
- Cost: Token generation costs.

Usage:
    cd ragforge
    venv\\Scripts\\python experiments/multi_query.py --top-k 5
"""

import argparse
import json
import sys
import time
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


def main():
    parser = argparse.ArgumentParser(
        description="Compare Single Query (hybrid_rerank) vs Multi-Query."
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)

    strategies = ["hybrid_rerank", "multi_query"]
    results: Dict[str, Dict] = {s: {"hits": 0, "latencies": [], "total_ms": 0} for s in strategies}

    print(f"\n🔬 RAGForge — Multi-Query Experiment")
    print(f"   Strategies: Single Query vs Multi-Query")
    print(f"   Top-K: {args.top_k}  |  Questions: {len(qa_pairs)}\n")

    for pair in qa_pairs:
        query = normalize_query(pair["question"])
        expected = set(pair.get("expected_sources", []))

        for strategy in strategies:
            t0 = time.perf_counter()
            try:
                chunks, meta = retrieve_with_timing(query, top_k=args.top_k, strategy=strategy)
                latency = round((time.perf_counter() - t0) * 1000)
                results[strategy]["latencies"].append(latency)
                
                retrieved_sources = {r.get("source", "") for r in chunks}
                if retrieved_sources & expected:
                    results[strategy]["hits"] += 1
            except Exception as e:
                print(f"   ⚠️  [{strategy}] error on '{query[:40]}': {e}")
                results[strategy]["latencies"].append(0)
                
            results[strategy]["total_ms"] += round((time.perf_counter() - t0) * 1000)

    # ── Print results ─────────────────────────────────────────────────────────
    total = len(qa_pairs)
    print("\n" + "=" * 72)
    print(f"  Results  (top_k={args.top_k}, {total} question(s))")
    print("=" * 72)
    print(f"\n  {'Strategy':<20} {'Hit@K':>8} {'Hits':>8} {'Avg Total Latency':>20}")
    print(f"  {'-'*20} {'-'*8} {'-'*8} {'-'*20}")

    for strategy in strategies:
        r = results[strategy]
        hits = r["hits"]
        hit_rate = hits / total * 100 if total else 0
        avg_lat = round(sum(r["latencies"]) / len(r["latencies"])) if r["latencies"] else 0
        
        label = "Single (Hybrid+RR)" if strategy == "hybrid_rerank" else "Multi-Query"
        print(f"  {label:<20} {hit_rate:>7.1f}% {hits:>4}/{total:<3} {avg_lat:>17} ms")

    print("\n" + "=" * 72)
    print("""
  Understanding the results:
  ──────────────────────────
  • Hit Rate: Multi-Query should increase Hit@K for hard questions where the 
    user phrasing didn't match document phrasing.
    
  • Latency: Multi-Query adds an LLM call to generate questions AND runs 
    the retriever multiple times. Expect it to be significantly slower 
    (often 1-3 seconds).

  Practical rule: Multi-Query is a heavy-weight technique. Use it only when
  maximizing recall on difficult, vague questions is more important than speed.
""")


if __name__ == "__main__":
    main()
