"""
experiments/graph_rag.py — Step 7: Graph RAG
=============================================

Benchmarks "Dense" vs "Graph-Augmented Dense".

Why do this?
- Vector search (dense) is great for concepts but terrible at specific 
  entities (people, product IDs, orgs).
- Standard Graph databases (Neo4j) are heavy and hard to maintain.
- This script tests a lightweight alternative: offline entity extraction
  saved to a simple JSON map.

During retrieval, we extract entities from the query, instantly look up
their exact chunk IDs in the JSON map, and force those chunks into the 
context window alongside the dense retrieval chunks.

Trade-offs:
- 100% recall for specific entities mentioned in the query.
- Adds an LLM call at query time to extract entities.
- The offline graph building step requires running the LLM over every 
  single chunk in the database.

Usage:
    cd ragforge
    
    # Optional: ensure graph is built first (takes a few minutes depending on DB size)
    python -m src.graph_builder
    
    venv\\Scripts\\python experiments/graph_rag.py --top-k 5
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
        description="Compare Dense vs Graph-Augmented retrieval."
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    
    graph_path = PROJECT_ROOT / "data" / "entity_graph.json"
    if not graph_path.exists():
        print(f"\n❌ Error: Graph file not found at {graph_path}")
        print("   You must build the graph first!")
        print("   Run: python -m src.graph_builder")
        sys.exit(1)

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)

    strategies = ["dense", "graph_augmented"]
    results: Dict[str, Dict] = {s: {"hits": 0, "latencies": [], "total_ms": 0} for s in strategies}

    print(f"\n🔬 RAGForge — Graph RAG Experiment")
    print(f"   Strategies: Dense vs Graph-Augmented Dense")
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
        
        label = "Dense (Baseline)" if strategy == "dense" else "Graph-Augmented"
        print(f"  {label:<20} {hit_rate:>7.1f}% {hits:>4}/{total:<3} {avg_lat:>17} ms")

    print("\n" + "=" * 72)
    print("""
  Understanding the results:
  ──────────────────────────
  • Graph-Augmentation guarantees that if an entity is mentioned in the 
    query, every chunk containing that entity is injected into the candidate 
    pool before reranking.
  • This prevents the "lost in the middle" or "vector mismatch" problem for 
    highly specific names, acronyms, or product numbers.
  • Latency: High, because it requires an LLM call to extract entities 
    from the query, plus the CrossEncoder reranker.
""")

if __name__ == "__main__":
    main()
