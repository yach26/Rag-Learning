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


def run_eval(qa_file: Path, top_k: int) -> None:
    from src.retriever import retrieve

    pairs = load_qa_pairs(qa_file)

    print("=" * 65)
    print(f"RAGForge — Retrieval Eval  |  top-k={top_k}  |  {len(pairs)} question(s)")
    print("=" * 65)

    hits = 0
    for i, pair in enumerate(pairs, start=1):
        question = pair.get("question", "").strip()
        expected_sources = pair.get("expected_sources", [])
        expected_pages = [int(p) for p in pair.get("expected_pages", [])]

        if not question:
            print(f"  Q{i:02d}  [SKIP] No question text.")
            continue

        try:
            retrieved = retrieve(question, top_k=top_k)
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

    total = len(pairs)
    rate = (hits / total * 100) if total > 0 else 0.0

    print()
    print("─" * 65)
    print(f"  Hit rate @ k={top_k}: {hits}/{total}  ({rate:.1f}%)")
    print("─" * 65)
    print()
    print("Tip: run before/after each Phase 2 change to measure progress.")
    print("     python eval/run_eval.py --top-k 4")


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
    args = parser.parse_args()

    # Late import so --help works without a ChromaDB connection
    from src.config import config
    top_k = args.top_k if args.top_k is not None else config.TOP_K

    run_eval(args.qa_file, top_k)


if __name__ == "__main__":
    main()
