"""
experiments/query_transformation.py — Step 3: Query Transformation Experiment
=============================================================================

Benchmarks the effect of query transformations on retrieval quality.

Specifically compares:
1. Raw Query (baseline)
2. Normalised Query (spellchecked)
3. Expanded Query (LLM-generated synonyms added)

*Note: Conversational rewriting (resolving "it", "that", etc.) requires multi-turn
history and isn't easily benchmarked in a single-turn QA dataset. This script
focuses on spelling normalisation and vocabulary expansion.*

Why compare these?
- Spellchecking: Small embedding models drop off a cliff when given a typo.
- Expansion: "caching" vs "memory cache". Semantic search handles synonyms well,
  but BM25 completely fails. Expansion boosts BM25 recall massively.
- Trade-off: Expansion adds an LLM call latency (~500ms) BEFORE retrieval even starts.

Usage:
    cd ragforge
    venv\\Scripts\\python experiments/query_transformation.py --top-k 5
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
from src.query.expansion import expand_query


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
        description="Compare Query Transformation techniques."
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)

    # We will use "hybrid" strategy as the base retriever for all queries,
    # so we are isolating the effect of the QUERY transformation, not the retrieval algo.
    base_strategy = "hybrid"

    transformations = ["raw", "normalised", "expanded"]
    results: Dict[str, Dict] = {t: {"hits": 0, "latencies": [], "total_ms": 0} for t in transformations}

    print(f"\n🔬 RAGForge — Query Transformation Experiment")
    print(f"   Base Retrieval: {base_strategy}")
    print(f"   Top-K: {args.top_k}  |  Questions: {len(qa_pairs)}\n")

    for pair in qa_pairs:
        raw_query = pair["question"]
        expected = set(pair.get("expected_sources", []))

        # 1. Raw
        t0 = time.perf_counter()
        try:
            chunks_raw, meta_raw = retrieve_with_timing(raw_query, top_k=args.top_k, strategy=base_strategy)
            results["raw"]["latencies"].append(meta_raw["total_ms"])
            if {r.get("source", "") for r in chunks_raw} & expected:
                results["raw"]["hits"] += 1
        except Exception:
            results["raw"]["latencies"].append(0)
        results["raw"]["total_ms"] += round((time.perf_counter() - t0) * 1000)

        # 2. Normalised (Spellcheck)
        t0 = time.perf_counter()
        norm_query = normalize_query(raw_query)
        try:
            chunks_norm, meta_norm = retrieve_with_timing(norm_query, top_k=args.top_k, strategy=base_strategy)
            # We measure total pipeline latency (transformation + retrieval)
            latency = round((time.perf_counter() - t0) * 1000)
            results["normalised"]["latencies"].append(latency)
            if {r.get("source", "") for r in chunks_norm} & expected:
                results["normalised"]["hits"] += 1
        except Exception:
            results["normalised"]["latencies"].append(0)
        results["normalised"]["total_ms"] += round((time.perf_counter() - t0) * 1000)

        # 3. Expanded
        t0 = time.perf_counter()
        exp_query = expand_query(norm_query)
        try:
            chunks_exp, meta_exp = retrieve_with_timing(exp_query, top_k=args.top_k, strategy=base_strategy)
            latency = round((time.perf_counter() - t0) * 1000)
            results["expanded"]["latencies"].append(latency)
            if {r.get("source", "") for r in chunks_exp} & expected:
                results["expanded"]["hits"] += 1
        except Exception:
            results["expanded"]["latencies"].append(0)
        results["expanded"]["total_ms"] += round((time.perf_counter() - t0) * 1000)

    # ── Print results ─────────────────────────────────────────────────────────
    total = len(qa_pairs)
    print("\n" + "=" * 72)
    print(f"  Results  (top_k={args.top_k}, {total} question(s))")
    print("=" * 72)
    print(f"\n  {'Transformation':<18} {'Hit@K':>8} {'Hits':>8} {'Avg Total Latency':>20}")
    print(f"  {'-'*18} {'-'*8} {'-'*8} {'-'*20}")

    for transform in transformations:
        r = results[transform]
        hits = r["hits"]
        hit_rate = hits / total * 100 if total else 0
        avg_lat = round(sum(r["latencies"]) / len(r["latencies"])) if r["latencies"] else 0

        print(f"  {transform.capitalize():<18} {hit_rate:>7.1f}% {hits:>4}/{total:<3} {avg_lat:>17} ms")

    print("\n" + "=" * 72)
    print("""
  Understanding the results:
  ──────────────────────────
  • Raw vs Normalised: Spellchecking is fast (<5ms) and highly protects against
    catastrophic recall failure due to typos. It should always be enabled.

  • Normalised vs Expanded: Expansion can pull in documents that don't share
    the exact vocabulary of the question. However, it requires an LLM call,
    which adds significant latency (~500ms - 1s).

  • Topic Drift: If hit rate drops for 'Expanded', it means the LLM injected
    tangential jargon that confused the retriever, pushing the actual relevant
    document below top-k.

  Practical rule: Use expansion when recalling domain-specific knowledge
  is more important than low latency, OR use a faster, smaller model (like
  a local fastText model or keyword dictionary) instead of an LLM for expansion.
""")


if __name__ == "__main__":
    main()
