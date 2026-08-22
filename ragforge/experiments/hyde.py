"""
experiments/hyde.py — Step 5: HyDE (Hypothetical Document Embeddings)
=======================================================================

Benchmarks "Dense" vs "HyDE".

HyDE solves the fundamental semantic gap in vector search: Questions
and Answers don't look alike in embedding space. A question uses question
words ("What is", "How do I"), while an answer uses declarative facts.

HyDE uses an LLM to generate a fake "perfect" answer to the question.
We embed the *fake answer* (which looks like a real document) instead of
the question. Then we retrieve the nearest real documents.

Why do this?
- Massive boost in dense retrieval recall for conceptual questions.
- Does not rely on exact keywords (unlike BM25).

Trade-offs:
- Very slow. Generating a whole paragraph takes much longer than generating
  3 short questions (Multi-Query) or 5 keywords (Expansion).
- If the LLM doesn't know the topic *at all*, the hallucination might use
  the wrong vocabulary, pulling the retriever in the wrong direction.

Usage:
    cd ragforge
    venv\\Scripts\\python experiments/hyde.py --top-k 5
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List

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
        description="Compare Dense vs HyDE retrieval."
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)

    strategies = ["dense", "hyde"]
    results: Dict[str, Dict] = {s: {"hits": 0, "latencies": [], "total_ms": 0} for s in strategies}

    print(f"\n🔬 RAGForge — HyDE Experiment")
    print(f"   Strategies: Dense vs HyDE")
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
        
        label = "Dense (Baseline)" if strategy == "dense" else "HyDE"
        print(f"  {label:<20} {hit_rate:>7.1f}% {hits:>4}/{total:<3} {avg_lat:>17} ms")

    print("\n" + "=" * 72)
    print("""
  Understanding the results:
  ──────────────────────────
  • Hit Rate: HyDE often dramatically outperforms raw Dense retrieval for 
    vague, conceptual questions because the fake document's embedding maps
    much closer to the real documents than a short question embedding does.
    
  • Latency: HyDE requires generating a full paragraph before retrieval begins.
    This makes it the slowest transformation technique (~1-3 seconds).

  Practical rule: Use HyDE when recall on conceptual queries is poor and
  users can tolerate multi-second retrieval latency, or when you are using 
  a fast, small, self-hosted LLM specifically for the HyDE generation step.
""")


if __name__ == "__main__":
    main()
