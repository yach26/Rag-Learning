"""
src/retriever.py — Retrieval Module
=====================================

CHANGES IN THIS REVISION (Phase 2) — HYBRID SEARCH + RERANKING
----------------------------------------------------------------
Phase 1 was pure vector search (embed query → Chroma ANN lookup).
Phase 2 replaces the single vector call with:

  1. Vector search → top HYBRID_CANDIDATES chunks from Chroma.
  2. BM25 keyword search → top HYBRID_CANDIDATES chunks from in-memory index.
  3. Reciprocal Rank Fusion (RRF) → merge both ranked lists.
  4. CrossEncoder reranking → rescore top RERANK_CANDIDATES, keep top_k.

Public API is UNCHANGED — callers (app.py, eval/run_eval.py, CLI) pass
the same (user_query, top_k) arguments and get back the same result shape.

Why this order matters:
- Vector search: strong on semantic similarity, weak on exact terms.
- BM25: strong on exact names/keywords, weak on paraphrase.
- RRF: simple, robust fusion — no per-dataset weight tuning needed.
- CrossEncoder: expensive but highly accurate cross-attention rescoring.
  Only runs on the post-RRF shortlist, keeping latency low.
"""

import logging
from typing import Any, Dict, List

from src.config import config
from src.embedder import embed_query
from src.vector_store import query as vector_query

logger = logging.getLogger("RAGForge.Retriever")

RetrievalResult = Dict[str, Any]


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def _reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = config.RRF_K,
) -> List[Dict[str, Any]]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion.

    RRF score = Σ  1 / (k + rank_i)   for each list i that contains the item.

    Parameters
    ----------
    ranked_lists : list of ranked chunk lists (each list ordered best-first).
    k : RRF constant (default 60 — standard from the original paper).

    Returns
    -------
    Merged list sorted by RRF score descending. Duplicate chunks (same
    chunk_id) are deduplicated; the highest-ranked copy's text/metadata
    is kept.
    """
    scores: Dict[str, float] = {}
    chunks_by_id: Dict[str, Dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            # Build a stable dedup key from source + chunk_id.
            source = chunk.get("source", "unknown")
            chunk_id = chunk.get("chunk_id", chunk.get("global_index", 0))
            uid = f"{source}__chunk_{chunk_id}"

            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
            if uid not in chunks_by_id:
                chunks_by_id[uid] = chunk

    merged = sorted(chunks_by_id.values(), key=lambda c: scores[
        f"{c.get('source', 'unknown')}__chunk_{c.get('chunk_id', c.get('global_index', 0))}"
    ], reverse=True)

    return merged


# ── Main retrieve function ────────────────────────────────────────────────────

def retrieve(
    user_query: str,
    top_k: int = config.TOP_K,
) -> List[RetrievalResult]:
    """
    Hybrid retrieval: vector search + BM25 → RRF merge → CrossEncoder rerank.

    Parameters
    ----------
    user_query : str
        The (possibly rewritten) user question.
    top_k : int
        Final number of chunks to return.

    Returns
    -------
    List of chunk dicts, sorted by relevance (best first).
    Each dict has: text, source, page, distance (vector), rerank_score (if reranker used).
    """
    if not user_query or not user_query.strip():
        raise ValueError("Query cannot be empty. Please type a question.")

    logger.info(f"Hybrid retrieve top-{top_k} for: '{user_query[:80]}'")

    candidates = config.HYBRID_CANDIDATES

    # ── 1. Vector search ─────────────────────────────────────────────────────
    query_embedding = embed_query(user_query.strip())
    vector_results = vector_query(query_embedding, top_k=candidates)
    logger.info(f"Vector search: {len(vector_results)} candidate(s)")

    # ── 2. BM25 keyword search ────────────────────────────────────────────────
    bm25_results: List[Dict[str, Any]] = []
    try:
        from src.bm25_store import bm25_query, get_index
        _, all_chunks = get_index()
        ranked_bm25 = bm25_query(user_query.strip(), top_n=candidates)
        bm25_results = [all_chunks[idx] for idx, _score in ranked_bm25]
        logger.info(f"BM25 search: {len(bm25_results)} candidate(s)")
    except Exception as e:
        logger.warning(f"BM25 search failed ({e}) — falling back to vector-only.")

    # ── 3. Reciprocal Rank Fusion ─────────────────────────────────────────────
    ranked_lists = [vector_results]
    if bm25_results:
        ranked_lists.append(bm25_results)

    fused = _reciprocal_rank_fusion(ranked_lists, k=config.RRF_K)
    logger.info(f"After RRF fusion: {len(fused)} unique candidate(s)")

    # ── 4. CrossEncoder reranking ─────────────────────────────────────────────
    rerank_pool = fused[: config.RERANK_CANDIDATES]
    try:
        from src.reranker import rerank
        final = rerank(user_query.strip(), rerank_pool, top_k=top_k)
        logger.info(f"After reranking: {len(final)} chunk(s) returned")
    except Exception as e:
        logger.warning(f"Reranking failed ({e}) — using RRF order.")
        final = rerank_pool[:top_k]

    return final


# ── Display helper (unchanged) ────────────────────────────────────────────────

def format_results_for_display(results: List[RetrievalResult]) -> str:
    if not results:
        return "No results found."

    lines = []
    for i, result in enumerate(results, start=1):
        lines.append(f"\n{'─' * 50}")
        lines.append(f"Result #{i}")
        lines.append(f"  Source  : {result.get('source', 'unknown')}")
        lines.append(f"  Page    : {result.get('page', '?')}")
        lines.append(f"  Distance: {result.get('distance', '?')} (lower = more similar)")
        if "rerank_score" in result:
            lines.append(f"  Rerank  : {result['rerank_score']} (higher = more relevant)")
        lines.append(f"  Preview : {result['text'][:300]}...")

    lines.append(f"\n{'─' * 50}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("RAGForge — Retrieval Test (Hybrid)")
    print("=" * 60)
    print("(Make sure you've run 'python -m src.ingest' first!)\n")

    test_query = input("Enter a test query: ").strip()
    if not test_query:
        print("No query entered. Exiting.")
        exit()

    try:
        results = retrieve(test_query, top_k=config.TOP_K)
        print(format_results_for_display(results))
    except RuntimeError as e:
        print(f"\nERROR: {e}")
