"""
src/vector_store.py — ChromaDB Vector Store Module
====================================================

CHANGES IN THIS REVISION (Phase 2)
-------------------------------------
- delete_chunks_for_source(source): deletes all chunks belonging to a
  given source file. Used by incremental ingestion to purge stale chunks
  before re-embedding a changed file.
- get_all_chunks(): returns ALL stored chunks as a list of dicts (text +
  metadata). Used by bm25_store.py to build the in-memory BM25 index.

Phase 1 items preserved:
- list_sources(): returns set of distinct source filenames.
- Stable, per-file chunk IDs via _make_chunk_id().
- Upsert semantics so re-ingesting changed files doesn't duplicate.
"""

import logging
from typing import List, Dict, Any, Set

import chromadb
from chromadb.config import Settings

from src.config import config

logger = logging.getLogger("RAGForge.VectorStore")

_client = None
_collection = None


def _get_collection() -> chromadb.Collection:
    global _client, _collection

    if _collection is None:
        db_path = str(config.CHROMA_DB_DIR)
        logger.info(f"Connecting to ChromaDB at: '{db_path}'")

        _client = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )

        _collection = _client.get_or_create_collection(
            name=config.CHROMA_COLLECTION_NAME,
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
    Deterministic ID: source filename + LOCAL (per-file) chunk_id.
    Stable across re-ingestion runs regardless of what other files exist,
    as long as this file's content and chunking params don't change.
    """
    source = metadata.get("source", "unknown")
    chunk_id = metadata.get("chunk_id", 0)
    safe_source = source.replace(" ", "_")
    return f"{safe_source}__chunk_{chunk_id:04d}"


def add_chunks(
    chunks: List[Dict[str, Any]],
    embeddings: List[List[float]],
) -> None:
    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Mismatch: {len(chunks)} chunks but {len(embeddings)} embeddings."
        )

    if not chunks:
        logger.warning("add_chunks() called with empty list — nothing to store.")
        return

    collection = _get_collection()

    ids: List[str] = []
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for chunk, embedding in zip(chunks, embeddings):
        chunk_id = _make_chunk_id(chunk["metadata"])
        ids.append(chunk_id)
        texts.append(chunk["text"])

        safe_metadata = {
            k: (str(v) if not isinstance(v, (str, int, float, bool)) else v)
            for k, v in chunk["metadata"].items()
        }
        metadatas.append(safe_metadata)

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
    collection = _get_collection()

    total_chunks = collection.count()
    if total_chunks == 0:
        raise RuntimeError(
            "The vector store is empty. "
            "Please run ingestion first: python -m src.ingest"
        )

    actual_top_k = min(top_k, total_chunks)

    raw_results = collection.query(
        query_embeddings=[query_embedding],
        n_results=actual_top_k,
        include=["documents", "metadatas", "distances"],
    )

    documents = raw_results["documents"][0]
    metadatas = raw_results["metadatas"][0]
    distances = raw_results["distances"][0]

    results: List[Dict[str, Any]] = []
    for text, metadata, distance in zip(documents, metadatas, distances):
        results.append({
            "text": text,
            "distance": round(distance, 4),
            **metadata,
        })

    return results


def get_collection_stats() -> Dict[str, Any]:
    collection = _get_collection()
    return {
        "collection_name": config.CHROMA_COLLECTION_NAME,
        "total_chunks": collection.count(),
        "db_path": str(config.CHROMA_DB_DIR),
    }


def list_sources() -> Set[str]:
    """
    Return the set of distinct source filenames currently stored.
    Phase 2's incremental ingestion uses this to decide which files in
    data/documents/ are already indexed and can be skipped.
    """
    collection = _get_collection()
    if collection.count() == 0:
        return set()

    all_records = collection.get(include=["metadatas"])
    return {m.get("source") for m in all_records["metadatas"] if m.get("source")}


def delete_chunks_for_source(source: str) -> None:
    """
    Delete ALL chunks belonging to a given source filename.

    Called by incremental ingestion before re-embedding a file whose
    content has changed, so stale chunks don't accumulate in ChromaDB.

    Parameters
    ----------
    source : str
        The `source` field value used in chunk metadata (e.g. "report.pdf").
    """
    collection = _get_collection()
    try:
        collection.delete(where={"source": source})
        logger.info(f"Deleted all chunks for source: '{source}'")
    except Exception as e:
        logger.warning(f"Could not delete chunks for '{source}': {e}")


def get_all_chunks() -> List[Dict[str, Any]]:
    """
    Return ALL stored chunks as a list of dicts with "text" and metadata fields.

    Used by bm25_store.py to build the in-memory BM25 keyword index.
    Fetches in a single Chroma .get() call — efficient for typical
    collection sizes (<100K chunks).

    Returns
    -------
    list of {"text": str, "source": str, "page": int/str, ...}
    """
    collection = _get_collection()
    if collection.count() == 0:
        return []

    raw = collection.get(include=["documents", "metadatas"])
    chunks = []
    for text, metadata in zip(raw["documents"], raw["metadatas"]):
        entry = {"text": text}
        entry.update(metadata)
        chunks.append(entry)

    logger.info(f"get_all_chunks(): returned {len(chunks)} chunk(s)")
    return chunks


def clear_collection() -> None:
    global _collection
    if _client is not None:
        try:
            _client.delete_collection(config.CHROMA_COLLECTION_NAME)
        except Exception:
            pass
        _collection = None
        logger.info("Collection cleared.")


if __name__ == "__main__":
    print("=" * 60)
    print("RAGForge — Vector Store Test")
    print("=" * 60)

    stats = get_collection_stats()
    print(f"\nCollection : {stats['collection_name']}")
    print(f"Total chunks stored: {stats['total_chunks']}")
    print(f"DB location: {stats['db_path']}")
    print(f"Indexed sources: {sorted(list_sources())}")
