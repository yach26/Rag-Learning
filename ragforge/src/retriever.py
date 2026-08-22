"""
src/retriever.py — Retrieval Module (Phase 3 refactor)
=======================================================

Phase 3 key change: the retrieve() function now accepts a `strategy`
parameter so every retrieval mode can be exercised and measured
*independently*. This is fundamental to Phase 3's goal of understanding
trade-offs, not just enabling features.

Supported strategies:
─────────────────────
  "dense"           — Vector search only (all-MiniLM-L6-v2 + Chroma ANN)
  "bm25"            — Keyword search only (BM25Okapi)
  "hybrid"          — Dense + BM25 merged with Reciprocal Rank Fusion (no reranker)
  "hybrid_rerank"   — Hybrid + CrossEncoder reranking (Phase 2 default behaviour)

Why isolate strategies?
  • You can benchmark "dense" vs "bm25" vs "hybrid" vs "hybrid_rerank" with
    the same query and observe exactly how each affects the ranked result list.
  • Each layer adds latency — measuring them individually shows *where* the
    time goes and whether the accuracy trade-off is worth it.
  • The app.py UI uses this to let you switch strategies without touching code.

Architecture for each strategy:

  "dense":
    query → embed → Chroma ANN → Top-K

  "bm25":
    query → tokenise → BM25Okapi.get_scores → Top-K

  "hybrid":
    dense_results + bm25_results → Reciprocal Rank Fusion → Top-K

  "hybrid_rerank":
    hybrid_results → CrossEncoder → Top-K   [Phase 2 behaviour]

Return format (all strategies):
  Each chunk dict contains:
    - text, source, page          (always)
    - distance                    (dense / hybrid / hybrid_rerank)
    - bm25_score                  (bm25)
    - rerank_score                (hybrid_rerank only)
    - retrieval_method            (new in Phase 3 — which strategy produced it)

The return also includes a `_meta` dict (popped by callers that don't need it)
with timing breakdown for the experiment harness.
"""

import logging
import time
from typing import Any, Dict, List, Literal, Optional, Tuple

from src.config import config
from src.embedder import embed_query
from src.vector_store import query as vector_query

logger = logging.getLogger("RAGForge.Retriever")

# Type alias for clarity
RetrievalResult = Dict[str, Any]
Strategy = Literal["dense", "bm25", "hybrid", "hybrid_rerank"]


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = config.RRF_K,
) -> List[Dict[str, Any]]:
    """
    Merge multiple ranked result lists using Reciprocal Rank Fusion (RRF).

    RRF was introduced in Cormack, Clarke & Buettcher (SIGIR 2009).
    The key insight is that *rank position* is more robust than raw
    similarity scores, which are not comparable across different retrieval
    systems (a Chroma distance of 0.2 and a BM25 score of 14.0 are
    apples-and-oranges; their relative ranks are not).

    Formula:
        RRF(d) = Σᵢ  1 / (k + rankᵢ(d))

    Where:
        d       = a specific document / chunk
        rankᵢ   = its rank position in ranked list i (1-indexed)
        k       = a constant (default 60, per the original paper) that
                  smooths out the curve and prevents very high-ranked items
                  from dominating too heavily.

    Parameters
    ----------
    ranked_lists : list of ranked chunk lists, each ordered best-first.
    k            : RRF smoothing constant (60 recommended).

    Returns
    -------
    Merged list deduplicated and sorted by RRF score descending.
    The chunk data from the *first* ranked list that contained the item
    is preserved (avoids overwriting distance metadata with BM25 metadata).
    """
    scores: Dict[str, float] = {}
    chunks_by_id: Dict[str, Dict[str, Any]] = {}

    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            source = chunk.get("source", "unknown")
            chunk_id = chunk.get("chunk_id", chunk.get("global_index", 0))
            uid = f"{source}__chunk_{chunk_id}"

            scores[uid] = scores.get(uid, 0.0) + 1.0 / (k + rank)
            if uid not in chunks_by_id:
                chunks_by_id[uid] = chunk

    merged = sorted(
        chunks_by_id.values(),
        key=lambda c: scores[
            f"{c.get('source', 'unknown')}__chunk_{c.get('chunk_id', c.get('global_index', 0))}"
        ],
        reverse=True,
    )
    return merged


# ── Individual search functions (independently testable) ──────────────────────

def search_dense(query: str, top_k: int) -> Tuple[List[RetrievalResult], float]:
    """
    Pure dense vector search via ChromaDB.

    Returns (results, latency_ms).

    How it works:
      1. The user's query is converted to a 384-dim vector using all-MiniLM-L6-v2.
      2. ChromaDB performs Approximate Nearest Neighbour (ANN) search using the
         HNSW index to find the top-k closest vectors by cosine distance.
      3. Each result includes a `distance` score (lower = more similar).

    Strengths:  Captures semantic meaning — "fast car" matches "quick vehicle".
    Weaknesses: Can miss exact keyword matches. Sensitive to typos and OOV terms.
    Latency:    Fast — ANN search in ChromaDB is sub-10ms for typical collections.
    """
    t0 = time.perf_counter()
    query_embedding = embed_query(query)
    results = vector_query(query_embedding, top_k=top_k)
    for r in results:
        r["retrieval_method"] = "dense"
    latency_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(f"[dense] {len(results)} results in {latency_ms}ms")
    return results, latency_ms


def search_bm25(query: str, top_k: int) -> Tuple[List[RetrievalResult], float]:
    """
    Pure BM25 keyword search over the in-memory index.

    Returns (results, latency_ms).

    How it works:
      BM25 (Best Match 25) is a probabilistic ranking function from the
      Okapi BM25 family. It scores each document by:

        BM25(q, d) = Σᵢ IDF(qᵢ) × f(qᵢ, d) × (k1 + 1)
                         ──────────────────────────────
                         f(qᵢ, d) + k1 × (1 - b + b × |d|/avgdl)

      Where:
        - IDF(qᵢ)   = Inverse Document Frequency (rare terms get higher weight)
        - f(qᵢ, d)  = term frequency in document d
        - k1, b     = tuning parameters (default: k1=1.5, b=0.75)
        - |d|/avgdl = normalise for document length

      The key difference from TF-IDF: BM25 saturates TF (doubling term
      frequency doesn't double the score), which models real relevance better.

    Strengths:  Exact keyword matches, technical terms, model numbers, names.
    Weaknesses: Can't understand paraphrases or synonyms.
    Latency:    Very fast — pure CPU math, no GPU needed. ~1-5ms.
    """
    from src.bm25_store import bm25_query, get_index

    t0 = time.perf_counter()
    _, all_chunks = get_index()
    ranked = bm25_query(query, top_n=top_k)

    results = []
    for idx, score in ranked:
        chunk = dict(all_chunks[idx])  # copy to avoid mutating shared state
        chunk["bm25_score"] = round(float(score), 4)
        chunk["retrieval_method"] = "bm25"
        results.append(chunk)

    latency_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(f"[bm25] {len(results)} results in {latency_ms}ms")
    return results, latency_ms


# ── Main retrieve function ────────────────────────────────────────────────────

def retrieve(
    user_query: str,
    top_k: int = config.TOP_K,
    strategy: Strategy = "hybrid_rerank",
) -> List[RetrievalResult]:
    """
    Retrieve the most relevant document chunks for a given query.

    Parameters
    ----------
    user_query : str
        The (possibly rewritten / normalised) user question.
    top_k : int
        Final number of chunks to return.
    strategy : str
        One of: "dense", "bm25", "hybrid", "hybrid_rerank".

        "dense"         → Fast baseline. Use when queries are semantic/conceptual.
        "bm25"          → Fast baseline. Use when queries contain exact keywords.
        "hybrid"        → Best of both worlds, no reranking overhead.
        "hybrid_rerank" → Highest accuracy. Adds ~50-200ms CrossEncoder cost.

    Returns
    -------
    List of chunk dicts sorted by relevance (best first).
    Each chunk includes: text, source, page, retrieval_method, and optional
    distance / bm25_score / rerank_score depending on strategy.
    """
    if not user_query or not user_query.strip():
        raise ValueError("Query cannot be empty.")

    query = user_query.strip()
    logger.info(f"Retrieving top-{top_k} via strategy='{strategy}' for: '{query[:80]}'")

    candidates = config.HYBRID_CANDIDATES

    # ── Dense only ────────────────────────────────────────────────────────────
    if strategy == "dense":
        results, _ = search_dense(query, top_k)
        return results

    # ── BM25 only ─────────────────────────────────────────────────────────────
    if strategy == "bm25":
        results, _ = search_bm25(query, top_k)
        return results

    # ── Hybrid (Dense + BM25 + RRF, no reranking) ────────────────────────────
    if strategy == "hybrid":
        dense_results, d_ms = search_dense(query, candidates)
        try:
            bm25_results, b_ms = search_bm25(query, candidates)
        except Exception as e:
            logger.warning(f"BM25 unavailable ({e}); falling back to dense.")
            bm25_results = []

        lists = [dense_results]
        if bm25_results:
            lists.append(bm25_results)

        fused = reciprocal_rank_fusion(lists, k=config.RRF_K)
        logger.info(f"[hybrid] RRF fused {len(fused)} unique candidates")
        return fused[:top_k]

    # ── Hybrid + Rerank (Phase 2 default) ────────────────────────────────────
    if strategy == "hybrid_rerank":
        dense_results, d_ms = search_dense(query, candidates)
        try:
            bm25_results, b_ms = search_bm25(query, candidates)
        except Exception as e:
            logger.warning(f"BM25 unavailable ({e}); falling back to dense-only for hybrid.")
            bm25_results = []

        lists = [dense_results]
        if bm25_results:
            lists.append(bm25_results)

        fused = reciprocal_rank_fusion(lists, k=config.RRF_K)
        pool = fused[: config.RERANK_CANDIDATES]

        try:
            from src.reranker import rerank
            final = rerank(query, pool, top_k=top_k)
        except Exception as e:
            logger.warning(f"Reranking failed ({e}); using RRF order.")
            final = pool[:top_k]

        return final

    raise ValueError(
        f"Unknown strategy '{strategy}'. "
        "Choose from: dense, bm25, hybrid, hybrid_rerank"
    )


def retrieve_with_timing(
    user_query: str,
    top_k: int = config.TOP_K,
    strategy: Strategy = "hybrid_rerank",
) -> Tuple[List[RetrievalResult], Dict[str, Any]]:
    """
    Same as retrieve() but also returns a timing/metadata dict.

    Useful for:
      - The experiment harness (experiments/hybrid_vs_dense.py)
      - The Streamlit UI debug mode
      - Any future evaluation scripts

    Returns
    -------
    (results, meta) where meta is:
        {
            "strategy":     str,
            "total_ms":     int,
            "num_results":  int,
        }
    """
    t0 = time.perf_counter()
    results = retrieve(user_query, top_k=top_k, strategy=strategy)
    total_ms = round((time.perf_counter() - t0) * 1000)

    meta = {
        "strategy": strategy,
        "total_ms": total_ms,
        "num_results": len(results),
    }
    return results, meta


# ── Display helper ────────────────────────────────────────────────────────────

def format_results_for_display(results: List[RetrievalResult]) -> str:
    if not results:
        return "No results found."

    lines = []
    for i, result in enumerate(results, start=1):
        lines.append(f"\n{'─' * 50}")
        lines.append(f"Result #{i}")
        lines.append(f"  Source  : {result.get('source', 'unknown')}")
        lines.append(f"  Page    : {result.get('page', '?')}")
        lines.append(f"  Method  : {result.get('retrieval_method', '?')}")
        if "distance" in result:
            lines.append(f"  Dist    : {result['distance']} (lower = more similar)")
        if "bm25_score" in result:
            lines.append(f"  BM25    : {result['bm25_score']} (higher = more relevant)")
        if "rerank_score" in result:
            lines.append(f"  Rerank  : {result['rerank_score']} (higher = more relevant)")
        lines.append(f"  Preview : {result['text'][:300]}...")

    lines.append(f"\n{'─' * 50}")
    return "\n".join(lines)


if __name__ == "__main__":
    print("=" * 60)
    print("RAGForge — Retrieval Test (Strategy-aware)")
    print("=" * 60)
    print("Available strategies: dense | bm25 | hybrid | hybrid_rerank\n")

    test_query = input("Enter a test query: ").strip()
    if not test_query:
        print("No query entered. Exiting.")
        exit()

    strategy_input = input("Strategy [hybrid_rerank]: ").strip() or "hybrid_rerank"

    try:
        results, meta = retrieve_with_timing(test_query, top_k=config.TOP_K, strategy=strategy_input)
        print(f"\nStrategy: {meta['strategy']}  |  Time: {meta['total_ms']}ms  |  Results: {meta['num_results']}")
        print(format_results_for_display(results))
    except (RuntimeError, ValueError) as e:
        print(f"\nERROR: {e}")
