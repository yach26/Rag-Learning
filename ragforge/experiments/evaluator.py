"""
experiments/evaluator.py — Step 11: LLM-as-a-Judge Evaluation
===============================================================

Instead of manual testing, we use a powerful LLM to grade the RAG pipeline.
This script tests a given retrieval strategy on the qa_pairs.json dataset.

Grades on two dimensions:
1. Context Relevance: Did the retrieved chunks actually contain the answer? (1-5)
2. Faithfulness: Is the generated answer fully supported by the chunks? (YES/NO)

Usage:
    cd ragforge
    venv\\Scripts\\python experiments/evaluator.py --strategy hybrid_rerank
"""

import argparse
import json
import sys
import re
from pathlib import Path
from typing import Dict, List, Any

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.retriever import retrieve_with_timing
from src.query.rewrite import normalize_query
from src.generator import generate_answer, _get_client
from src.config import config

_EVAL_PROMPT = """\
You are an expert evaluator grading a RAG (Retrieval-Augmented Generation) system.
Please evaluate the provided Context and Answer for a given User Question.

1. CONTEXT RELEVANCE (Score 1-5):
   Does the provided context contain sufficient information to answer the question?
   1 = Completely irrelevant
   5 = Contains the exact, complete answer

2. FAITHFULNESS (YES/NO):
   Does the generated answer rely ONLY on the provided context? (If the answer correctly says "I cannot answer this based on the context", grade it YES because it did not hallucinate).

Output your evaluation exactly in this format:
RELEVANCE: <score>
FAITHFULNESS: <YES or NO>
REASON: <One sentence explanation>

Question:
{question}

Context:
{context}

Answer:
{answer}
"""

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

def grade_response(question: str, chunks: List[Dict], answer: str) -> Dict[str, Any]:
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        context_parts.append(f"[Source {i}]\n{chunk.get('text', '')}")
    context_text = "\n\n".join(context_parts)
    
    prompt = _EVAL_PROMPT.format(question=question, context=context_text, answer=answer)
    
    try:
        client = _get_client()
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
        )
        output = response.text.strip()
        
        rel_match = re.search(r"RELEVANCE:\s*([1-5])", output, re.IGNORECASE)
        faith_match = re.search(r"FAITHFULNESS:\s*(YES|NO)", output, re.IGNORECASE)
        reason_match = re.search(r"REASON:\s*(.*)", output, re.IGNORECASE)
        
        return {
            "relevance": int(rel_match.group(1)) if rel_match else 1,
            "faithfulness": True if (faith_match and faith_match.group(1).upper() == "YES") else False,
            "reason": reason_match.group(1) if reason_match else output.replace("\n", " "),
            "raw": output
        }
    except Exception as e:
        return {"relevance": 1, "faithfulness": False, "reason": f"Eval failed: {e}", "raw": ""}

def main():
    parser = argparse.ArgumentParser(description="LLM-as-a-Judge Evaluator")
    parser.add_argument("--strategy", type=str, default="hybrid_rerank")
    parser.add_argument("--top-k", type=int, default=3)
    args = parser.parse_args()

    qa_path = PROJECT_ROOT / "eval" / "qa_pairs.json"
    qa_pairs = load_qa_pairs(qa_path)
    
    print(f"\n🔬 RAGForge — Automated Evaluation")
    print(f"   Strategy: {args.strategy}")
    print(f"   Questions: {len(qa_pairs)}\n")

    scores = {"relevance": [], "faithful_count": 0}

    for i, pair in enumerate(qa_pairs):
        query = normalize_query(pair["question"])
        print(f"[{i+1}/{len(qa_pairs)}] '{query[:40]}...'")
        
        try:
            chunks, _ = retrieve_with_timing(query, top_k=args.top_k, strategy=args.strategy)
            answer = generate_answer(query, chunks)
            
            evaluation = grade_response(query, chunks, answer)
            
            scores["relevance"].append(evaluation["relevance"])
            if evaluation["faithfulness"]:
                scores["faithful_count"] += 1
                
            faith_icon = "✅" if evaluation["faithfulness"] else "❌"
            print(f"    ↳ Rel: {evaluation['relevance']}/5 | Faithful: {faith_icon} | {evaluation['reason'][:60]}...")
        except Exception as e:
            print(f"    ↳ ⚠️ Error: {e}")

    # Print summary
    if scores["relevance"]:
        avg_rel = sum(scores["relevance"]) / len(scores["relevance"])
        faith_pct = (scores["faithful_count"] / len(scores["relevance"])) * 100
        print("\n" + "=" * 50)
        print("  FINAL GRADES")
        print("=" * 50)
        print(f"  Avg Context Relevance: {avg_rel:.1f} / 5.0")
        print(f"  Answer Faithfulness:   {faith_pct:.1f}%")
        print("=" * 50)
        print("\nNote: A perfect system scores 5.0 Relevance and 100% Faithfulness.")
    else:
        print("\nNo successful evaluations.")

if __name__ == "__main__":
    main()
