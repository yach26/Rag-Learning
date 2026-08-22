"""
src/vector_store.py — ChromaDB Vector Store Module
====================================================

WHAT PROBLEM DOES THIS SOLVE?
------------------------------
We have hundreds (or thousands) of chunk embeddings — 384-dimensional vectors.
We need to:
1. Store them persistently (survive program restarts)
2. Search them FAST to find the most similar chunk to a query vector

A naive approach would be to store vectors in a list and compute cosine
similarity against every single one for every query. For 10,000 chunks,
that's 10,000 comparisons per query — O(n). Fine for a demo, but it doesn't scale.

ChromaDB uses approximate nearest neighbour (ANN) indexing internally to
find similar vectors in sub-linear time. But for us, the important thing is
that it's dead simple to use and runs fully locally with zero configuration.

WHAT IS CHROMADB?
-----------------
ChromaDB is an open-source, embedded vector database (like SQLite, but for vectors).

Key concepts:
  ┌─────────────────────────────────────────────────────────┐
  │  Collection  ≈  a table in a relational database        │
  │  Document    ≈  a row (but here "document" = a chunk)   │
  │  Embedding   ≈  the vector stored for each row          │
  │  Metadata    ≈  extra columns (source, page, chunk_id)  │
  │  ID          ≈  primary key (must be unique strings)    │
  └─────────────────────────────────────────────────────────┘

WHY PERSISTENT? (./chroma_db directory)
----------------------------------------
Without persistence, you'd have to re-embed all your documents every time
you restart the app. With persistence, ChromaDB saves its index to disk
and loads it instantly on startup. The ./chroma_db folder IS the database.

DEDUPLICATION STRATEGY
-----------------------
ChromaDB will raise an error if you try to add the same ID twice. We generate
chunk IDs from the source filename and chunk_id metadata, so running ingestion
twice on the same documents won't create duplicates — we use upsert() instead
of add(), which overwrites existing entries with the same ID.

INTERNAL FLOW:
--------------
add_chunks(chunks, embeddings)
    → validate lengths match
    → build IDs from metadata
    → collection.upsert(ids, embeddings, documents, metadatas)

query(query_embedding, top_k)
    → collection.query(query_embeddings=[...], n_results=top_k)
    → returns {documents, metadatas, distances}
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from chromadb.config import Settings

from src.config import config

logger = logging.getLogger("RAGForge.VectorStore")


# ── Singleton ChromaDB client ─────────────────────────────────────────────────
# Like the embedder model, we create the ChromaDB client once and reuse it.
_client = None       # chromadb PersistentClient
_collection = None   # chromadb Collection


def _get_collection() -> chromadb.Collection:
    """
    Return the ChromaDB collection, initializing the client on first call.

    The collection is the object we interact with for all read/write operations.
    Think of it as our "table" that holds all chunk vectors.
    """
    global _client, _collection

    if _collection is None:
        db_path = str(config.CHROMA_DB_DIR)
        logger.info(f"Connecting to ChromaDB at: '{db_path}'")

        # PersistentClient saves data to disk automatically.
        # Every write is flushed to the chroma_db/ directory.
        _client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),  # No usage tracking
        )

        # get_or_create_collection: if the collection already exists from a
        # previous run, we open it. If not, we create a fresh one.
        _collection = _client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
            # cosine similarity is the standard for text embeddings.
            # It measures the angle between vectors, not their magnitude.
            metadata={"hnsw:space": "cosine"},
        )

        count = _collection.count()
        logger.info(
            f"Collection '{config.CHROMA_COLLECTION_NAME}' ready "
            f"(contains {count} existing chunks)"
        )

    return _collection


def _make_chunk_id(metadata: Dict[str, Any]) -> str:
    """
    Generate a deterministic, unique ID for a chunk based on its metadata.

    WHY DETERMINISTIC IDs?
    ----------------------
    If we use random IDs (like UUID), running ingestion twice would create
    duplicate chunks (different IDs, same content). With deterministic IDs
    derived from source + chunk_id, the same chunk always gets the same ID,
    so upsert() simply overwrites the old version.

    Format: "source_filename__chunk_42"
    Example: "research_paper.pdf__chunk_007"
    """
    source = metadata.get("source", "unknown")
    chunk_id = metadata.get("chunk_id", 0)
    # Replace spaces in filenames to keep IDs clean
    safe_source = source.replace(" ", "_")
    return f"{safe_source}__chunk_{chunk_id:04d}"


def add_chunks(
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
) -> None:
    """
    Add or update chunks in the ChromaDB collection.

    This is called during ingestion after we have:
    - chunks: the text + metadata dicts from chunker.py
    - embeddings: the vectors from embedder.py

    Args:
        chunks:     List of chunk dicts (each has "text" and "metadata")
        embeddings: Parallel list of embedding vectors — embeddings[i] is the
                    vector for chunks[i].

    Raises:
        ValueError: If chunks and embeddings have different lengths.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings. "
            "Every chunk must have exactly one embedding."
        )

    if not chunks:
        logger.warning("add_chunks() called with empty list — nothing to store.")
        return

    collection = _get_collection()

    # Build the parallel lists that ChromaDB's API expects
    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for chunk, embedding in zip(chunks, embeddings):
        chunk_id = _make_chunk_id(chunk["metadata"])
        ids.append(chunk_id)
        texts.append(chunk["text"])

        # ChromaDB metadata values must be str, int, float, or bool.
        # Convert Path objects or anything else to string just in case.
        safe_metadata = {
            k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
            for k, v in chunk["metadata"].items()
        }
        metadatas.append(safe_metadata)

    # upsert = insert if new, update if ID already exists
    # This prevents duplicates when re-running ingestion
    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metadatas,
    )

    logger.info(f"Stored {len(chunks)} chunk(s) in ChromaDB (upserted).")


def query(
    query_embedding: List[float],
    top_k: int = config.TOP_K,
) -> List[Dict[str, Any]]:
    """
    Find the top-k most similar chunks to a query embedding.

    This is called during retrieval. ChromaDB performs the vector similarity
    search internally using its ANN index.

    Args:
        query_embedding: The embedding vector for the user's query.
        top_k:           How many results to return.

    Returns:
        List of result dicts, sorted by similarity (closest first):
        [
            {
                "text":     "The actual chunk text...",
                "source":   "paper.pdf",
                "page":     3,
                "chunk_id": 12,
                "distance": 0.18   ← lower = more similar (cosine distance)
            },
            ...
        ]

    Raises:
        RuntimeError: If the collection is empty.
    """
    collection = _get_collection()

    total_chunks = collection.count()
    if total_chunks == 0:
        raise RuntimeError(
            "The vector store is empty. "
            "Please run ingestion first: python -m src.ingest"
        )

    # Don't ask for more results than exist in the collection
    actual_top_k = min(top_k, total_chunks)

    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=actual_top_k,
        include=["documents", "metadatas", "distances"],
    )

    # ChromaDB returns results nested in lists (because you can batch queries).
    # We always send one query, so we index [0] to get results for our query.
    documents = raw_results["documents"][0]    # list of text strings
    metadatas = raw_results["metadatas"][0]    # list of metadata dicts
    distances = raw_results["distances"][0]    # list of cosine distances

    # Combine into clean result dicts
    results: List[Dict[str, Any]] = []
    for text, metadata, distance in zip(documents, metadatas, distances):
        results.append({
            "text": text,
            "distance": round(distance, 4),
            # Flatten metadata fields to the top level for easy access
            **metadata,
        })

    return results


def get_collection_stats() -> Dict[str, Any]:
    """Return basic stats about the current collection (for debugging/UI)."""
    collection = _get_collection()
    return {
        "collection_name": config.CHROMA_COLLECTION_NAME,
        "total_chunks": collection.count(),
        "db_path": str(config.CHROMA_DB_DIR),
    }


def clear_collection() -> None:
    """
    Delete and recreate the collection (nuclear option for resetting).
    Used in tests to start with a clean slate.
    """
    global _collection
    if _client is not None:
        try:
            _client.delete_collection(config.CHROMA_COLLECTION_NAME)
        except Exception:
            pass
        _collection = None
        logger.info("Collection cleared.")


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("RAGForge — Vector Store Test")
    print("=" * 60)

    stats = get_collection_stats()
    print(f"\nCollection : {stats['collection_name']}")
    print(f"Total chunks stored: {stats['total_chunks']}")
    print(f"DB location: {stats['db_path']}")
