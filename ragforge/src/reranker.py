"""
src/reranker.py — CrossEncoder Reranking
==========================================

After hybrid search produces ~15-20 candidates, this module rescores
every (query, chunk_text) pair using a CrossEncoder that sees both
strings simultaneously — it can model cross-attention between them,
which a bi-encoder (like all-MiniLM-L6-v2) cannot.

Model: cross-encoder/ms-marco-MiniLM-L-6-v2
- Trained on MS MARCO passage ranking, generalises well to most domains.
- ~22 M parameters — runs on CPU in ~50–200 ms for 20 pairs.
- Downloaded from Hugging Face on first use (~85 MB), cached locally.

Why reranking matters:
- Vector search + BM25 fetch "probably relevant" chunks.
- The CrossEncoder provides a more precise relevance signal —
  it consistently moves the most relevant chunk to position #1.
- Academic results (BEIR benchmark): +5–15% NDCG over bi-encoder alone.
"""

import logging
from typing import Any, Dict, List, Optional

from src.config import config

logger = logging.getLogger("RAGForge.Reranker")

_cross_encoder: Optional[Any] = None  # CrossEncoder singleton


def _get_cross_encoder():
    """Load CrossEncoder model on first call (singleton)."""
    global _cross_encoder

    if _cross_encoder is None:
        try:
            from sentence_transformers import CrossEncoder
        except ImportError:
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers"
            )

        logger.info(f"Loading CrossEncoder: '{config.RERANKER_MODEL}'")
        logger.info("(First load downloads ~85 MB from Hugging Face)")
        try:
            _cross_encoder = CrossEncoder(config.RERANKER_MODEL)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load CrossEncoder '{config.RERANKER_MODEL}': {e}"
            ) from e
        logger.info("CrossEncoder loaded successfully.")

    return _cross_encoder


def rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int,
) -> List[Dict[str, Any]]:
    """
    Score each (query, chunk_text) pair with the CrossEncoder and return
    the top_k chunks sorted by rerank score descending.

    Each returned chunk gets a `rerank_score` field added to its dict
    (visible in the UI's retrieved-context expander).

    Parameters
    ----------
    query : str
        The (possibly rewritten) user query.
    chunks : list of chunk dicts
        Candidates from hybrid search — typically 15–20 items.
    top_k : int
        How many to keep after reranking.

    Returns
    -------
    list of chunk dicts, trimmed to top_k, sorted by rerank_score desc.
    """
    if not chunks:
        return []

    if not config.USE_RERANKER:
        # Reranker disabled — just trim to top_k.
        return chunks[:top_k]

    try:
        model = _get_cross_encoder()
        pairs = [(query, chunk.get("text", "")) for chunk in chunks]
        scores = model.predict(pairs)

        # Attach score to each chunk and sort.
        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = round(float(score), 4)

        reranked = sorted(chunks, key=lambda c: c.get("rerank_score", 0.0), reverse=True)
        logger.info(
            f"Reranked {len(chunks)} candidates → keeping top {top_k}. "
            f"Top score: {reranked[0].get('rerank_score', '?')}"
        )
        return reranked[:top_k]

    except Exception as e:
        logger.warning(f"Reranking failed ({e}) — returning original order.")
        return chunks[:top_k]
