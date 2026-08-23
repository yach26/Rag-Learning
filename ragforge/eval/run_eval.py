"""
eval/run_eval.py — Retrieval Evaluation Harness
================================================

Measures retrieval accuracy (hit rate) against hand-written Q&A pairs
before and after each Phase 2 change. Run this BEFORE and AFTER every
modification to prove improvements instead of eyeballing them.

Usage:
    python eval/run_eval.py
    python eval/run_eval.py --top-k 5
    python eval/run_eval.py --qa-file eval/qa_pairs.json --top-k 8

A "hit" = at least one retrieved chunk's source AND page match the
expected_sources/expected_pages for that question.

Output:
    ✓  Q1  "What is the main topic..."  → hit   (source: doc.pdf, page 1)
    ✗  Q2  "What penalties..."          → miss  (got: intro.pdf p.1, p.2)
    ─────────────────────────────────────────────────────────────
    Hit rate @ k=4: 4/5  (80.0%)

No LLM call is made — this is pure retrieval evaluation.
"""

import argparse
import json
import sys
from pathlib import Path

# Allow running from project root: python eval/run_eval.py
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def load_qa_pairs(qa_file: Path) -> list:
    if not qa_file.exists():
        print(f"ERROR: QA file not found: '{qa_file}'")
        print("Create it at eval/qa_pairs.json — see the template there.")
        sys.exit(1)

    with qa_file.open("r", encoding="utf-8") as f:
        pairs = json.load(f)

    # Filter out comment-only entries
    pairs = [p for p in pairs if "_comment" not in p]

    if not pairs:
        print("ERROR: qa_pairs.json contains no valid Q&A pairs.")
        print("Add real questions from your documents and expected sources/pages.")
        sys.exit(1)

    return pairs


def is_hit(retrieved_chunks: list, expected_sources: list, expected_pages: list) -> tuple:
    """
    Returns (hit: bool, matched_info: str).
    A hit requires matching source filename AND page number.
    """
    for chunk in retrieved_chunks:
        src = str(chunk.get("source", "")).strip()
        try:
            page = int(chunk.get("page", -1))
        except (ValueError, TypeError):
            page = -1

        if src in expected_sources and page in expected_pages:
            return True, f"{src} p.{page}"

    # Summarise what was retrieved for debugging
    retrieved_info = ", ".join(
        f"{c.get('source', '?')} p.{c.get('page', '?')}"
        for c in retrieved_chunks[:3]
    )
    return False, retrieved_info


def run_eval(qa_file: Path, top_k: int, judge: bool = False, strategy: str = "hybrid_rerank") -> None:
    from src.retriever import retrieve

    pairs = load_qa_pairs(qa_file)

    print("=" * 65)
    print(f"RAGForge — Retrieval Eval  |  strategy={strategy}  |  top-k={top_k}  |  {len(pairs)} question(s)")
    print("=" * 65)

    hits = 0
    judged = 0
    faithful = 0
    relevance_scores = []

    for i, pair in enumerate(pairs, start=1):
        question = pair.get("question", "").strip()
        expected_sources = pair.get("expected_sources", [])
        expected_pages = [int(p) for p in pair.get("expected_pages", [])]

        if not question:
            print(f"  Q{i:02d}  [SKIP] No question text.")
            continue

        try:
            retrieved = retrieve(question, top_k=top_k, strategy=strategy)
        except Exception as e:
            print(f"  Q{i:02d}  [ERROR] Retrieval failed: {e}")
            continue

        hit, info = is_hit(retrieved, expected_sources, expected_pages)
        tag = "[HIT]" if hit else "[MISS]"
        label = "hit " if hit else "miss"
        question_preview = question[:55] + "..." if len(question) > 55 else question

        print(f"  {tag}  Q{i:02d}  \"{question_preview}\"")
        print(f"         → {label}  ({info})")

        if hit:
            hits += 1

        if judge:
            try:
                from src.generator import generate_answer
                from experiments.evaluator import grade_response

                answer = generate_answer(question, retrieved)
                evaluation = grade_response(question, retrieved, answer)
                judged += 1
                relevance_scores.append(evaluation["relevance"])
                if evaluation["faithfulness"]:
                    faithful += 1
                faith = "YES" if evaluation["faithfulness"] else "NO"
                print(
                    f"         → relevance={evaluation['relevance']}/5  "
                    f"faithfulness={faith}"
                )
            except Exception as e:
                print(f"         → [JUDGE ERROR] {e}")

    total = len(pairs)
    rate = (hits / total * 100) if total > 0 else 0.0

    print()
    print("─" * 65)
    print(f"  Hit rate @ k={top_k}: {hits}/{total}  ({rate:.1f}%)")
    if judge and judged:
        avg_rel = sum(relevance_scores) / len(relevance_scores)
        faith_pct = (faithful / judged) * 100
        print(f"  Avg context relevance: {avg_rel:.1f}/5")
        print(f"  Answer faithfulness:   {faith_pct:.1f}% ({faithful}/{judged})")
        from src.metrics import metrics
        snap = metrics.snapshot()
        print(
            f"  Tokens / est. cost:    {snap['prompt_tokens']}+{snap['completion_tokens']} "
            f"(${snap['estimated_cost_usd']:.4f})"
        )
    print("─" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="RAGForge retrieval evaluation harness."
    )
    parser.add_argument(
        "--qa-file",
        type=Path,
        default=PROJECT_ROOT / "eval" / "qa_pairs.json",
        help="Path to the Q&A pairs JSON file (default: eval/qa_pairs.json)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Number of chunks to retrieve per question (default: config.TOP_K)",
    )
    parser.add_argument(
        "--strategy",
        type=str,
        default="hybrid_rerank",
        help="Retrieval strategy to evaluate",
    )
    parser.add_argument(
        "--judge",
        action="store_true",
        help="Also run LLM-as-judge faithfulness / context relevance (uses Groq)",
    )
    args = parser.parse_args()

    from src.config import config
    top_k = args.top_k if args.top_k is not None else config.TOP_K

    run_eval(args.qa_file, top_k, judge=args.judge, strategy=args.strategy)


if __name__ == "__main__":
    main()
