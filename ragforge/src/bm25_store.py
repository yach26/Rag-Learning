"""
src/bm25_store.py — SQLite FTS5 keyword index (scalable)
=========================================================

Replaces rank-bm25 to remove the in-memory load bottleneck.
Uses SQLite's FTS5 extension for fast on-disk keyword search.
"""

from __future__ import annotations

import logging
import sqlite3
import re
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import json

from src.config import config

logger = logging.getLogger("RAGForge.BM25Store")

_db_path = config.PROJECT_ROOT / "data" / "sparse_index.db"
_all_chunks_cache: List[Dict[str, Any]] = []

def _get_conn():
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_db_path))
    conn.row_factory = sqlite3.Row
    return conn

def _init_db(conn):
    conn.execute("DROP TABLE IF EXISTS chunks_fts;")
    conn.execute("DROP TABLE IF EXISTS chunk_metadata;")
    conn.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5(text, tokenize='porter');"
    )
    conn.execute(
        "CREATE TABLE chunk_metadata (rowid INTEGER PRIMARY KEY, chunk_json TEXT);"
    )
    conn.commit()

def _collection_count() -> int:
    from src.vector_store import get_collection_stats
    return int(get_collection_stats()["total_chunks"])

def build_index(chunks: List[Dict[str, Any]], fingerprint: Optional[int] = None) -> None:
    logger.info("Building SQLite FTS5 index over %s chunk(s)...", len(chunks))
    
    conn = _get_conn()
    _init_db(conn)
    
    cursor = conn.cursor()
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        # Insert explicitly with rowid=i so that it matches Python list indexing (0-based)
        cursor.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (i, text))
        cursor.execute("INSERT INTO chunk_metadata (rowid, chunk_json) VALUES (?, ?)", (i, json.dumps(chunk)))
        
    conn.commit()
    conn.close()
    
    global _all_chunks_cache
    _all_chunks_cache = chunks
    logger.info("SQLite FTS5 index built.")

def get_index() -> Tuple[Any, List[Dict[str, Any]]]:
    # Returns (None, chunks) to satisfy legacy retriever callers
    global _all_chunks_cache
    
    try:
        fingerprint = _collection_count()
    except Exception:
        fingerprint = 0
        
    if not _db_path.exists():
        from src.vector_store import get_all_chunks
        chunks = get_all_chunks()
        if not chunks:
            raise RuntimeError("BM25 index is empty — no chunks in vector store.")
        build_index(chunks)
    elif not _all_chunks_cache:
        conn = _get_conn()
        try:
            rows = conn.execute("SELECT chunk_json FROM chunk_metadata ORDER BY rowid").fetchall()
            _all_chunks_cache = [json.loads(row["chunk_json"]) for row in rows]
        except sqlite3.OperationalError:
            _all_chunks_cache = []
        conn.close()
        
        if len(_all_chunks_cache) != fingerprint:
            logger.info("FTS count mismatch with Chroma. Rebuilding...")
            from src.vector_store import get_all_chunks
            chunks = get_all_chunks()
            if chunks:
                build_index(chunks)
            else:
                _all_chunks_cache = []
            
    return None, _all_chunks_cache

def bm25_query(query: str, top_n: int) -> List[Tuple[int, float]]:
    clean_query = re.sub(r'[^a-zA-Z0-9\s]', ' ', query).strip()
    if not clean_query:
        return []
        
    # Split by spaces and join with OR for standard keyword search behavior
    fts_query = " OR ".join(clean_query.split())
    
    conn = _get_conn()
    try:
        # FTS5 bm25() returns negative values (more negative = better score)
        # We multiply by -1 to get positive scores for compatibility
        cursor = conn.execute(
            "SELECT rowid, bm25(chunks_fts) * -1 as score FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY score DESC LIMIT ?",
            (fts_query, top_n)
        )
        results = [(row["rowid"], row["score"]) for row in cursor.fetchall()]
    except sqlite3.OperationalError as e:
        logger.warning(f"FTS query error '{fts_query}': {e}")
        results = []
    finally:
        conn.close()
        
    return results

def invalidate_index() -> None:
    global _all_chunks_cache
    _all_chunks_cache = []
    if _db_path.exists():
        try:
            _db_path.unlink()
        except OSError:
            pass
    logger.info("SQLite FTS5 index invalidated.")

