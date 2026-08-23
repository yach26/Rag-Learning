"""
src/bm25_store.py — BM25 keyword index (persisted)
===================================================

Index is pickled to data/.bm25_index.pkl and reused when the Chroma
collection count matches. Rebuilds after ingest/purge.
"""

from __future__ import annotations

import logging
import pickle
import re
from typing import Any, Dict, List, Optional, Tuple

from src.config import config

logger = logging.getLogger("RAGForge.BM25Store")

_bm25_index = None
_all_chunks: List[Dict[str, Any]] = []
_index_fingerprint: Optional[int] = None


def _tokenise(text: str) -> List[str]:
    text = text.lower()
    return re.findall(r"[a-z0-9]+", text)


def _collection_count() -> int:
    from src.vector_store import get_collection_stats
    return int(get_collection_stats()["total_chunks"])


def _persist(index, chunks: List[Dict[str, Any]], fingerprint: int) -> None:
    path = config.BM25_INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"fingerprint": fingerprint, "chunks": chunks, "index": index}
    with path.open("wb") as f:
        pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Persisted BM25 index (%s chunks) to %s", len(chunks), path)


def _load_persisted(expected_fingerprint: int):
    path = config.BM25_INDEX_PATH
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            payload = pickle.load(f)
        if payload.get("fingerprint") != expected_fingerprint:
            logger.info("BM25 pickle fingerprint mismatch — rebuilding.")
            return None
        return payload["index"], payload["chunks"]
    except Exception as e:
        logger.warning("Failed to load BM25 pickle (%s) — rebuilding.", e)
        return None


def build_index(chunks: List[Dict[str, Any]], fingerprint: Optional[int] = None) -> None:
    global _bm25_index, _all_chunks, _index_fingerprint

    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        raise RuntimeError("rank-bm25 is not installed. Run: pip install rank-bm25")

    logger.info("Building BM25 index over %s chunk(s)...", len(chunks))
    _all_chunks = chunks
    corpus = [_tokenise(c.get("text", "")) for c in chunks]
    _bm25_index = BM25Okapi(corpus)
    _index_fingerprint = fingerprint if fingerprint is not None else len(chunks)
    try:
        _persist(_bm25_index, _all_chunks, _index_fingerprint)
    except Exception as e:
        logger.warning("Could not persist BM25 index: %s", e)
    logger.info("BM25 index built.")


def get_index() -> Tuple[Any, List[Dict[str, Any]]]:
    global _bm25_index, _all_chunks, _index_fingerprint

    fingerprint = _collection_count()
    if _bm25_index is not None and _index_fingerprint == fingerprint:
        return _bm25_index, _all_chunks

    loaded = _load_persisted(fingerprint)
    if loaded is not None:
        _bm25_index, _all_chunks = loaded
        _index_fingerprint = fingerprint
        logger.info("Loaded persisted BM25 index (%s chunks).", len(_all_chunks))
        return _bm25_index, _all_chunks

    from src.vector_store import get_all_chunks

    chunks = get_all_chunks()
    if not chunks:
        raise RuntimeError(
            "BM25 index is empty — no chunks in vector store. "
            "Run ingestion first: python -m src.ingest"
        )
    build_index(chunks, fingerprint=fingerprint)
    return _bm25_index, _all_chunks


def bm25_query(query: str, top_n: int) -> List[Tuple[int, float]]:
    index, chunks = get_index()
    tokens = _tokenise(query)
    scores = index.get_scores(tokens)
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    return ranked[:top_n]


def invalidate_index() -> None:
    global _bm25_index, _all_chunks, _index_fingerprint
    _bm25_index = None
    _all_chunks = []
    _index_fingerprint = None
    path = config.BM25_INDEX_PATH
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
    logger.info("BM25 index invalidated.")
