"""
src/retriever.py — Retrieval Module
=====================================

WHAT PROBLEM DOES THIS SOLVE?
------------------------------
Given a user's question (a string), find the most relevant document chunks
stored in ChromaDB. This is the "R" in RAG — Retrieval.

The retriever bridges the embedder and the vector store:
1. Takes a raw text query from the user
2. Converts it to a vector using the SAME model used during ingestion
3. Searches ChromaDB for the nearest chunk vectors
4. Returns the matching chunks with their metadata

WHY MUST QUERY AND DOCUMENT USE THE SAME MODEL?
------------------------------------------------
Imagine embedding space as a map. The embedding model decides where on the
map each text lives. If you embedded documents with Model A, all chunks have
coordinates on "Model A's map". If you now embed a query with Model B,
the query lands on "Model B's map" — a completely different space.

Searching for nearby points across two different maps is meaningless.

Always use the same model for both. Our config.EMBEDDING_MODEL ensures this.

WHAT IS COSINE DISTANCE?
--------------------------
ChromaDB returns distances, not similarities. With cosine space:

    distance = 1 - cosine_similarity

    distance = 0.0  →  identical meaning (perfect match)
    distance = 0.5  →  somewhat similar
    distance = 1.0  →  completely different
    distance = 2.0  →  opposite meaning (rare in practice)

So LOWER distance = MORE relevant. We sort results ascending by distance.

INTERNAL FLOW:
--------------
retrieve("What is machine learning?")
    ↓
embed_query("What is machine learning?")
    ↓  [0.12, -0.45, 0.78, ...] (384 floats)
    ↓
query(embedding, top_k=5)
    ↓  ChromaDB returns 5 nearest chunks
    ↓
[{text, source, page, distance}, ...]
"""

import logging
from typing import List, Dict, Any

from src.config import config
from src.embedder import embed_query
from src.vector_store import query as vector_query

logger = logging.getLogger("RAGForge.Retriever")


# ── Type alias ────────────────────────────────────────────────────────────────
RetrievalResult = Dict[str, Any]


def retrieve(
    user_query: str,
    top_k: int = config.TOP_K,
) -> List[RetrievalResult]:
    """
    Retrieve the most relevant document chunks for a user query.

    This is the main retrieval function. Call this from the UI or generator.

    Args:
        user_query: The user's question as a plain text string.
        top_k:      Number of results to return. Default from config.

    Returns:
        List of result dicts sorted by relevance (most relevant first):
        [
            {
                "text":     "The actual chunk text...",
                "source":   "research_paper.pdf",
                "page":     3,
                "chunk_id": 12,
                "distance": 0.18
            },
            ...
        ]

    Raises:
        ValueError: If the query is empty.
        RuntimeError: If the vector store is empty (ingestion not run).
    """
    if not user_query or not user_query.strip():
        raise ValueError("Query cannot be empty. Please type a question.")

    logger.info(f"Retrieving top-{top_k} chunks for: '{user_query[:80]}'")

    # Step 1: Embed the query
    query_embedding = embed_query(user_query.strip())

    # Step 2: Search ChromaDB
    results = vector_query(query_embedding, top_k=top_k)

    logger.info(f"Retrieved {len(results)} chunk(s)")

    return results


def format_results_for_display(results: List[RetrievalResult]) -> str:
    """
    Format retrieval results as a human-readable string for debugging.

    Useful when running the retriever standalone to check what it found.

    Args:
        results: Output from retrieve()

    Returns:
        Formatted string showing each result's metadata and a text preview.
    """
    if not results:
        return "No results found."

    lines = []
    for i, result in enumerate(results, start=1):
        lines.append(f"\n{'─' * 50}")
        lines.append(f"Result #{i}")
        lines.append(f"  Source  : {result.get('source', 'unknown')}")
        lines.append(f"  Page    : {result.get('page', '?')}")
        lines.append(f"  Distance: {result.get('distance', '?')} (lower = more similar)")
        lines.append(f"  Preview : {result['text'][:300]}...")

    lines.append(f"\n{'─' * 50}")
    return "\n".join(lines)


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("RAGForge — Retrieval Test")
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
