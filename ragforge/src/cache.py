"""
src/cache.py — Semantic / Exact Match Query Cache
===================================================

To combat the latency of advanced RAG pipelines (especially HyDE and
Multi-Query), we can cache the final generated answers.

If a user asks the exact same question (or a semantically identical one
if we normalize it), we can return the cached answer instantly, bypassing
retrieval and LLM generation entirely.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from src.config import config
from src.query.rewrite import normalize_query

logger = logging.getLogger("RAGForge.Cache")

CACHE_FILE_PATH = config.PROJECT_ROOT / "data" / "query_cache.json"

def _load_cache() -> dict:
    if not CACHE_FILE_PATH.exists():
        return {}
    try:
        with CACHE_FILE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load cache: {e}")
        return {}

def _save_cache(cache_data: dict) -> None:
    CACHE_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with CACHE_FILE_PATH.open("w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save cache: {e}")

def get_cached_answer(query: str, strategy: str) -> Optional[str]:
    """
    Look up a query in the cache. We cache by normalized query string + strategy.
    Because different strategies yield different answers.
    """
    normalized = normalize_query(query)
    cache = _load_cache()
    
    key = f"{normalized}_{strategy}"
    if key in cache:
        logger.info(f"Cache hit for query: '{query}'")
        return cache[key]
        
    return None

def set_cached_answer(query: str, strategy: str, answer: str) -> None:
    """Save an answer to the cache."""
    normalized = normalize_query(query)
    cache = _load_cache()
    
    key = f"{normalized}_{strategy}"
    cache[key] = answer
    
    _save_cache(cache)
    logger.info(f"Cached answer for query: '{query}'")

def clear_cache() -> None:
    """Clear all cached answers."""
    if CACHE_FILE_PATH.exists():
        CACHE_FILE_PATH.unlink()
        logger.info("Cache cleared.")
