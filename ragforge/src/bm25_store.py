"""
src/bm25_store.py — BM25 Keyword Index for Hybrid Search
==========================================================

Provides a lightweight BM25 keyword index built over all chunks
currently in ChromaDB. Used alongside vector search in hybrid retrieval
(see retriever.py → Reciprocal Rank Fusion).

Why BM25 alongside all-MiniLM-L6-v2?
- all-MiniLM-L6-v2 is excellent at semantic similarity but weak on
  exact-match keyword queries (names, model numbers, legal terms, etc.).
- BM25 is term-frequency based and excels precisely where dense vectors
  struggle — exact lexical matches.
- Combining both via RRF almost always outperforms either alone.

Design:
- Index is held in-memory as a module-level singleton, rebuilt once per
  Python session on the first retrieve() call.
- Rebuild is fast (<1 s at typical chunk counts) and avoids stale-index
  issues — if you re-ingest, restart the app and the index auto-rebuilds.
- If you ever exceed ~100K chunks and rebuild time matters, wrap
  _bm25_index and _all_chunks in a pickle cache invalidated by
  collection.count() change detection.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("RAGForge.BM25Store")

# Module-level singletons — built once per session on first query.
_bm25_index = None          # rank_bm25.BM25Okapi instance
_all_chunks: List[Dict[str, Any]] = []  # parallel list to the BM25 corpus


def _tokenise(text: str) -> List[str]:
    """
    Simple whitespace + punctuation tokeniser.
    Lowercases and strips non-alphanumeric characters to improve recall.
    rank_bm25 handles TF-IDF weighting; we just need clean tokens.
    """
    text = text.lower()
    tokens = re.findall(r"[a-z0-9]+", text)
    return tokens


def build_index(chunks: List[Dict[str, Any]]) -> None:
    """
    Build (or rebuild) the in-memory BM25 index from a list of chunk dicts.
    Each dict must have a "text" key.

    Called automatically by get_index() on first use; you can also call it
    explicitly after ingestion to pre-warm the index.
    """
    global _bm25_index, _all_chunks

    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        raise RuntimeError(
            "rank-bm25 is not installed. Run: pip install rank-bm25"
        )

    logger.info(f"Building BM25 index over {len(chunks)} chunk(s)...")
    _all_chunks = chunks
    corpus = [_tokenise(c.get("text", "")) for c in chunks]
    _bm25_index = BM25Okapi(corpus)
    logger.info("BM25 index built.")


def get_index() -> Tuple[Any, List[Dict[str, Any]]]:
    """
    Return (bm25_index, all_chunks), building from ChromaDB if not yet done.
    Thread-safe for single-threaded Streamlit use (no locking needed).
    """
    global _bm25_index, _all_chunks

    if _bm25_index is None:
        from src.vector_store import get_all_chunks
        chunks = get_all_chunks()
        if not chunks:
            raise RuntimeError(
                "BM25 index is empty — no chunks in vector store. "
                "Run ingestion first: python -m src.ingest"
            )
        build_index(chunks)

    return _bm25_index, _all_chunks


def bm25_query(
    query: str,
    top_n: int,
) -> List[Tuple[int, float]]:
    """
    Score all chunks against `query` using BM25 and return the top-n as
    (chunk_index, score) pairs sorted by score descending.

    Parameters
    ----------
    query : str
        The search query.
    top_n : int
        Number of results to return.

    Returns
    -------
    List of (chunk_index, bm25_score) — index into _all_chunks.
    """
    index, chunks = get_index()
    tokens = _tokenise(query)
    scores = index.get_scores(tokens)

    # Pair each index with its score, sort descending, take top-n.
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


def invalidate_index() -> None:
    """
    Clear the in-memory index so it is rebuilt on the next query.
    Call this after any ingestion run that changes the chunk set.
    """
    global _bm25_index, _all_chunks
    _bm25_index = None
    _all_chunks = []
    logger.info("BM25 index invalidated — will rebuild on next query.")
