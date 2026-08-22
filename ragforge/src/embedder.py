"""
src/embedder.py — Text Embedding Module
========================================

CHANGE IN THIS REVISION
-------------------------
- embed_query() is now wrapped with functools.lru_cache. If the same
  question is asked twice in a session (very common while testing), the
  second call skips re-running the model entirely. Cheap, safe win —
  queries are short strings so the cache stays tiny.
- _get_model() now wraps the load in try/except with a clearer error if the
  model can't be downloaded (e.g. no internet on first run).
"""

import logging
from functools import lru_cache
from typing import List

from sentence_transformers import SentenceTransformer

from src.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("RAGForge.Embedder")

_model = None  # SentenceTransformer instance, loaded on first use (singleton)


def _get_model() -> SentenceTransformer:
    """Return the embedding model, loading it on first call."""
    global _model

    if _model is None:
        logger.info(f"Loading embedding model: '{config.EMBEDDING_MODEL}'")
        logger.info("(This may take a few seconds on first load — model is ~80 MB)")

        try:
            _model = SentenceTransformer(config.EMBEDDING_MODEL)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{config.EMBEDDING_MODEL}': {e}\n"
                "Check your internet connection (first load downloads the model "
                "from Hugging Face) and that sentence-transformers is installed."
            ) from e

        logger.info("Embedding model loaded successfully.")
        logger.info(f"Vector dimensions: {_model.get_sentence_embedding_dimension()}")

    return _model


def embed_documents(texts: List[str]) -> List[List[float]]:
    """Embed a list of text strings into vectors (used during ingestion)."""
    if not texts:
        return []

    model = _get_model()
    logger.info(f"Embedding {len(texts)} chunk(s)...")

    embeddings = model.encode(
        texts,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).tolist()

    logger.info(f"Done. Generated {len(embeddings)} embeddings.")
    return embeddings


@lru_cache(maxsize=256)
def _embed_query_cached(query: str) -> tuple:
    """
    Internal cached embed step. Returns a tuple (hashable, required by
    lru_cache) instead of a list — embed_query() converts it back to a list.
    """
    model = _get_model()
    vec = model.encode([query], convert_to_numpy=True)[0].tolist()
    return tuple(vec)


def embed_query(query: str) -> List[float]:
    """
    Embed a single user query string into a vector (used during retrieval).

    Repeated identical queries within a session are served from cache —
    skips the model.encode() call entirely on a cache hit.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    return list(_embed_query_cached(query.strip()))


if __name__ == "__main__":
    print("=" * 60)
    print("RAGForge — Embedding Test")
    print("=" * 60)

    sample_texts = [
        "Machine learning is a subset of artificial intelligence.",
        "Neural networks are inspired by the human brain.",
        "The sky is blue and the grass is green.",
    ]

    print("\nEmbedding 3 sample texts...")
    vectors = embed_documents(sample_texts)

    for text, vec in zip(sample_texts, vectors):
        print(f"  Text   : '{text[:60]}...'")
        print(f"  Vector : [{vec[0]:.4f}, {vec[1]:.4f}, ..., {vec[-1]:.4f}]  (dim={len(vec)})")
        print()

    print("Embedding a query twice (second call should be cached / instant)...")
    query_vec = embed_query("What is machine learning?")
    query_vec_again = embed_query("What is machine learning?")
    print(f"  Cache working: {query_vec == query_vec_again}")

    import math
    dot = sum(a * b for a, b in zip(query_vec, vectors[0]))
    mag_q = math.sqrt(sum(x**2 for x in query_vec))
    mag_d = math.sqrt(sum(x**2 for x in vectors[0]))
    cosine_sim = dot / (mag_q * mag_d)
    print(f"\nCosine similarity (query vs 'Machine learning is...'): {cosine_sim:.4f}")
