"""
src/embedder.py — Text Embedding Module
========================================

WHAT IS AN EMBEDDING?
----------------------
An embedding is a list of numbers (a "vector") that represents the *meaning*
of a piece of text. The key idea: texts with similar meanings will have vectors
that point in similar directions in high-dimensional space.

Example:
    "The cat sat on the mat"   → [0.12, -0.45, 0.78, ...]   (384 numbers)
    "A kitten rested on a rug" → [0.11, -0.44, 0.80, ...]   (very similar!)
    "The stock market crashed"  → [0.89, 0.23, -0.56, ...]   (very different)

The numbers themselves have no human-readable meaning — they are learned by the
neural network during training. What matters is the *relationship* between vectors.

WHY 384 DIMENSIONS?
--------------------
all-MiniLM-L6-v2 produces 384-dimensional vectors. More dimensions = more
expressiveness but also more memory and slower computation. 384 is a sweet
spot for a fast, accurate, lightweight model.

HOW DOES SIMILARITY SEARCH WORK?
----------------------------------
When you ask a question, we:
1. Embed the question → get a query vector
2. Compare it to every chunk vector in ChromaDB using cosine similarity:

   cosine_similarity(A, B) = dot(A, B) / (|A| × |B|)

   Result: 1.0 = identical direction, 0.0 = perpendicular, -1.0 = opposite

3. Return the chunks with the highest similarity scores

The embedding model was trained to make semantically similar texts produce
similar vectors, so "What is machine learning?" and "ML is a field of AI" will
be closer to each other than to "What is a soufflé recipe?".

WHY LOAD THE MODEL ONCE?
-------------------------
Loading a neural network model from disk takes 1-5 seconds. If we reloaded
on every query, a user typing 20 questions would wait ~60 seconds just for
model loading. We use a module-level singleton: the model is loaded the first
time embed_documents() or embed_query() is called, then reused forever.

INTERNAL FLOW:
--------------
embed_documents(["chunk 1 text", "chunk 2 text"])
    → _get_model()  (loads model if not already loaded)
    → model.encode(texts)
    → returns list of 384-float lists

embed_query("What is the capital of France?")
    → _get_model()  (model already loaded, instant)
    → model.encode([query])[0]
    → returns single 384-float list
"""

import logging
from typing import List

from sentence_transformers import SentenceTransformer

from src.config import config

# ── Logging setup ─────────────────────────────────────────────────────────────
# Using Python's built-in logging instead of print() for library code.
# This lets the caller control verbosity.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("RAGForge.Embedder")


# ── Singleton model holder ────────────────────────────────────────────────────
# This is a module-level variable. Because Python modules are loaded once,
# this variable persists for the entire lifetime of the running program.
# The first call to _get_model() sets it; subsequent calls just return it.
_model = None  # SentenceTransformer instance, loaded on first use


def _get_model() -> SentenceTransformer:
    """
    Return the embedding model, loading it on first call.

    This is the "lazy singleton" pattern:
    - On the first call: loads the model from disk (~1-5 seconds)
    - On every subsequent call: returns the already-loaded model instantly

    The leading underscore in _get_model signals that this is an internal
    function — callers should use embed_documents() and embed_query() instead.
    """
    global _model

    if _model is None:
        logger.info(f"Loading embedding model: '{config.EMBEDDING_MODEL}'")
        logger.info("(This may take a few seconds on first load — model is ~80 MB)")

        _model = SentenceTransformer(config.EMBEDDING_MODEL)

        logger.info(f"Embedding model loaded successfully.")
        logger.info(f"Vector dimensions: {_model.get_sentence_embedding_dimension()}")

    return _model


def embed_documents(texts: List[str]) -> List[List[float]]:
    """
    Embed a list of text strings into vectors.

    Used during INGESTION to embed all document chunks.
    Processes all texts in a single batch call for efficiency — the model
    can embed many texts in parallel using vectorised operations.

    Args:
        texts: List of text strings to embed. Each string is one chunk.

    Returns:
        List of embedding vectors, one per input text.
        Each vector is a list of 384 floats.

    Example:
        >>> vecs = embed_documents(["Hello world", "Machine learning is fun"])
        >>> len(vecs)        # 2 vectors
        2
        >>> len(vecs[0])     # each is 384-dimensional
        384
    """
    if not texts:
        return []

    model = _get_model()

    logger.info(f"Embedding {len(texts)} chunk(s)...")

    # model.encode() returns a numpy array; .tolist() converts to plain Python lists
    # which is what ChromaDB expects.
    embeddings = model.encode(
        texts,
        show_progress_bar=True,   # Shows a tqdm progress bar for large batches
        convert_to_numpy=True,
    ).tolist()

    logger.info(f"Done. Generated {len(embeddings)} embeddings.")
    return embeddings


def embed_query(query: str) -> List[float]:
    """
    Embed a single user query string into a vector.

    Used during RETRIEVAL. Critically, this uses the SAME model as
    embed_documents() — query and document vectors must be in the same
    "embedding space" for similarity search to work.

    If you embedded documents with model A and queries with model B,
    the similarity scores would be meaningless.

    Args:
        query: The user's question as a plain string.

    Returns:
        A single embedding vector (list of 384 floats).

    Raises:
        ValueError: If the query is empty.
    """
    if not query or not query.strip():
        raise ValueError("Query cannot be empty.")

    model = _get_model()

    # encode() always returns a 2D array, even for a single input.
    # [0] extracts the first (and only) vector.
    embedding = model.encode([query.strip()], convert_to_numpy=True)[0].tolist()
    return embedding


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("RAGForge — Embedding Test")
    print("=" * 60)

    # Test with a few sample sentences
    sample_texts = [
        "Machine learning is a subset of artificial intelligence.",
        "Neural networks are inspired by the human brain.",
        "The sky is blue and the grass is green.",
    ]

    print("\nEmbedding 3 sample texts...")
    vectors = embed_documents(sample_texts)

    print(f"\nResults:")
    for text, vec in zip(sample_texts, vectors):
        print(f"  Text   : '{text[:60]}...'")
        print(f"  Vector : [{vec[0]:.4f}, {vec[1]:.4f}, ..., {vec[-1]:.4f}]  (dim={len(vec)})")
        print()

    # Show that a semantically similar query gets a similar vector
    print("Embedding a query...")
    query_vec = embed_query("What is machine learning?")
    print(f"  Query vector dim: {len(query_vec)}")
    print(f"  First few values: {query_vec[:5]}")

    # Manual cosine similarity between query and first text
    import math
    dot = sum(a * b for a, b in zip(query_vec, vectors[0]))
    mag_q = math.sqrt(sum(x**2 for x in query_vec))
    mag_d = math.sqrt(sum(x**2 for x in vectors[0]))
    cosine_sim = dot / (mag_q * mag_d)

    print(f"\nCosine similarity (query vs 'Machine learning is...'): {cosine_sim:.4f}")
    print("(Expected: close to 1.0 — same topic)")
