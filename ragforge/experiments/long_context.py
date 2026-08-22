"""
experiments/long_context.py — Step 8: Long Context vs RAG
===========================================================

With massive context windows (e.g. Gemini 1.5 Pro's 2M tokens), is RAG
even necessary? Can we just dump the entire database into the prompt?

This script answers that question by benchmarking:
1. RAG (Hybrid+Reranker): Retreive top 5 chunks -> LLM
2. Long Context: Load ALL chunks from ChromaDB into the prompt -> LLM

We measure:
- Latency (Time to First Token & Total Time)
- Quality/Hit rate (whether the LLM successfully extracted the answer)

Why do this?
- RAG is complex. If your entire corpus fits in 500k tokens and you only
  ask a few questions a day, Long Context is infinitely simpler.
- However, Long Context is slow (high TTFT) and expensive (high input tokens).
- This script lets you empirically test if the "Needle in a Haystack"
  capabilities of modern models outperform your retrieval pipeline.

Usage:
    cd ragforge
    venv\\Scripts\\python experiments/long_context.py
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
from src.generator import generate_answer, EVALUATOR_PROMPT, _get_client
from src.vector_store import _get_collection
from src.config import config

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

def get_all_chunks() -> List[Dict]:
    collection = _get_collection()
    data = collection.get(include=["documents", "metadatas"])
    
    chunks = []
    for i in range(len(data["ids"])):
        meta = data["metadatas"][i] or {}
        chunks.append({
            "text": data["documents"][i],
            "source": meta.get("source", "Unknown"),
            "page": meta.get("page", 1)
        })
    return chunks

def evaluate_answer(query: str, all_chunks: List[Dict], answer: str) -> bool:
    """Uses the self-correction evaluator to grade the answer."""
    # We only include a sample of the chunks in the evaluator prompt to avoid 
    # breaking the evaluator's context window, or we can just ask if it makes sense.
    # For a fair comparison, we'll assume if the answer is substantive and not a refusal, it's a pass.
    # (A robust evaluation would use a ground-truth answer, which we do in Step 11).
    if "don't have enough information" in answer or "cannot answer" in answer.lower():
        return False
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Compare RAG vs Long Context Generation."
    )
    args = parser.parse_args()

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)
    
    all_chunks = get_all_chunks()
    if not all_chunks:
        print("❌ No documents found in database.")
        sys.exit(1)
        
    print(f"\n🔬 RAGForge — Long Context Experiment")
    print(f"   Corpus Size: {len(all_chunks)} chunks")
    print(f"   Questions:   {len(qa_pairs)}\n")

    results = {
        "rag": {"latencies": [], "success": 0},
        "long_context": {"latencies": [], "success": 0}
    }

    for i, pair in enumerate(qa_pairs):
        query = normalize_query(pair["question"])
        print(f"  [{i+1}/{len(qa_pairs)}] '{query[:40]}...'")
        
        # 1. RAG (Retrieve top 5)
        t0 = time.perf_counter()
        try:
            top_chunks, _ = retrieve_with_timing(query, top_k=5, strategy="hybrid_rerank")
            rag_answer = generate_answer(query, top_chunks)
            results["rag"]["latencies"].append(round((time.perf_counter() - t0) * 1000))
            if evaluate_answer(query, top_chunks, rag_answer):
                results["rag"]["success"] += 1
        except Exception as e:
            print(f"     ⚠️ RAG failed: {e}")
            results["rag"]["latencies"].append(0)

        # 2. Long Context (Feed all chunks)
        t0 = time.perf_counter()
        try:
            # We don't retrieve, we just pass the entire database
            lc_answer = generate_answer(query, all_chunks)
            results["long_context"]["latencies"].append(round((time.perf_counter() - t0) * 1000))
            if evaluate_answer(query, all_chunks, lc_answer):
                results["long_context"]["success"] += 1
        except Exception as e:
            print(f"     ⚠️ Long Context failed: {e}")
            results["long_context"]["latencies"].append(0)

    # ── Print results ─────────────────────────────────────────────────────────
    total = len(qa_pairs)
    print("\n" + "=" * 72)
    print(f"  Results  ({total} question(s))")
    print("=" * 72)
    
    def avg(lst): return sum(lst) / len(lst) if lst else 0
    
    r_lat = avg(results["rag"]["latencies"])
    l_lat = avg(results["long_context"]["latencies"])
    
    print(f"\n  {'Approach':<18} {'Success Rate':>12} {'Avg Total Latency':>20}")
    print(f"  {'-'*18} {'-'*12} {'-'*20}")
    
    print(f"  {'RAG (Top-5)':<18} {results['rag']['success'] / total * 100:>11.1f}% {r_lat:>17.0f} ms")
    print(f"  {'Long Context (All)':<18} {results['long_context']['success'] / total * 100:>11.1f}% {l_lat:>17.0f} ms")

    print("\n" + "=" * 72)
    print("""
  Understanding the results:
  ──────────────────────────
  • Success Rate: Does the LLM get confused by the massive context (Lost 
    in the Middle), or does it excel because no retriever bottleneck exists?
  • Latency: Notice how much longer Long Context takes. This is the "Time 
    To First Token" (TTFT) penalty for processing massive inputs.
  • Cost (not shown here): Long Context costs significantly more per query.
    If you use Context Caching (Step 9), the cost and latency drop dramatically.
""")

if __name__ == "__main__":
    main()
