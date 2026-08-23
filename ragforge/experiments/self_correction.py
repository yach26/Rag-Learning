"""
experiments/self_correction.py — Step 6: Self-Correcting RAG
==============================================================

Benchmarks standard generation vs self-correcting generation.

Standard Generation:
1. Retrieve chunks
2. LLM answers using chunks

Self-Correcting Generation:
1. Retrieve chunks
2. LLM generates draft answer
3. LLM evaluates draft: "Does this fully address the question using ONLY context?"
4. If Yes -> return draft
5. If No -> return fallback / tell user it failed safely instead of hallucinating.

Why do this?
- Reduces hallucination to near zero.
- Prevents the system from confidently giving half-answers.

Trade-offs:
- Doubles the LLM cost per query.
- Doubles generation latency.
- Can be overly strict (rejecting answers that are technically correct but
  don't rigidly follow the context rules).

Usage:
    cd ragforge
    venv\\Scripts\\python experiments/self_correction.py --top-k 3
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
from src.generator import generate_answer, EVALUATOR_PROMPT
from src.llm import get_llm
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

def evaluate_draft(query: str, retrieved_chunks: List[Dict], draft: str) -> bool:
    context_parts = []
    for i, chunk in enumerate(retrieved_chunks, start=1):
        context_parts.append(f"[Source {i}]\n{chunk.get('text', '')}")
    context_text = "\n\n".join(context_parts)
    
    eval_prompt = EVALUATOR_PROMPT.format(
        context=context_text,
        question=query.strip(),
        draft=draft.strip()
    )
    
    try:
        return get_llm().complete(eval_prompt).strip().upper().startswith("YES")
    except:
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Compare Basic Generation vs Self-Correcting Generation."
    )
    parser.add_argument("--top-k", type=int, default=3) # smaller top_k to force some failures
    args = parser.parse_args()

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)
    
    print(f"\n🔬 RAGForge — Self-Correction Experiment")
    print(f"   Retrieval strategy: hybrid")
    print(f"   Top-K: {args.top_k}  |  Questions: {len(qa_pairs)}\n")

    results = {
        "basic": {"latencies": []},
        "self_correct": {"latencies": [], "passed": 0, "failed": 0}
    }

    for i, pair in enumerate(qa_pairs):
        query = normalize_query(pair["question"])
        
        # 1. Retrieve (shared)
        try:
            chunks, _ = retrieve_with_timing(query, top_k=args.top_k, strategy="hybrid")
        except Exception as e:
            print(f"   ⚠️  Retrieval error on '{query[:40]}': {e}")
            continue

        # 2. Basic Generation
        t0 = time.perf_counter()
        draft = generate_answer(query, chunks)
        results["basic"]["latencies"].append(round((time.perf_counter() - t0) * 1000))

        # 3. Self-Correction Evaluation step
        t1 = time.perf_counter()
        passed = evaluate_draft(query, chunks, draft)
        results["self_correct"]["latencies"].append(round((time.perf_counter() - t0) * 1000))
        
        if passed:
            results["self_correct"]["passed"] += 1
        else:
            results["self_correct"]["failed"] += 1
            
        print(f"  [{i+1}/{len(qa_pairs)}] '{query[:30]}...' -> {'✅ PASS' if passed else '❌ REJECTED'}")

    # ── Print results ─────────────────────────────────────────────────────────
    total = len(qa_pairs)
    print("\n" + "=" * 72)
    print(f"  Results  (top_k={args.top_k}, {total} question(s))")
    print("=" * 72)
    
    b_lat = sum(results['basic']['latencies']) / len(results['basic']['latencies']) if results['basic']['latencies'] else 0
    sc_lat = sum(results['self_correct']['latencies']) / len(results['self_correct']['latencies']) if results['self_correct']['latencies'] else 0
    
    print(f"\n  Basic Generation avg latency: {b_lat:.0f} ms")
    print(f"  Self-Correcting avg latency:  {sc_lat:.0f} ms")
    print(f"  Latency penalty:              +{sc_lat - b_lat:.0f} ms")
    
    print(f"\n  Drafts that passed: {results['self_correct']['passed']} / {total}")
    print(f"  Drafts rejected:    {results['self_correct']['failed']} / {total}")

    print("\n" + "=" * 72)
    print("""
  Understanding the results:
  ──────────────────────────
  • A rejection means the LLM caught itself hallucinating or admitting 
    it didn't use the provided context properly.
  • You can use this to fall back to a web search, ask the user to clarify,
    or just gracefully say "I can't answer this" instead of lying.
  • The cost is exactly double the API calls and double the latency.
""")

if __name__ == "__main__":
    main()
