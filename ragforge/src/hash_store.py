"""
src/hash_store.py — File Hash Persistence for Incremental Ingestion
====================================================================

Stores a JSON map of {filename -> md5_hex} at HASH_STORE_PATH.
Used by the ingestion pipeline to skip re-embedding files whose content
hasn't changed since the last run.

Design notes:
- md5_file() streams in 64 KB blocks — safe for large PDFs.
- The hash is keyed by the file's basename (not full path) to match
  the `source` field already used in chunk metadata.
- The JSON file lives in data/ next to the documents folder so it
  persists across sessions but is easy to delete if you want a full
  re-ingest (just delete .file_hashes.json).
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict

from src.config import config

logger = logging.getLogger("RAGForge.HashStore")


def md5_file(path: Path) -> str:
    """
    Return the MD5 hex digest of a file, reading in 64 KB blocks.
    Note: MD5 is used intentionally here for fast change detection, 
    not for cryptographic security.
    """
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            block = f.read(65536)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def load_hashes() -> Dict[str, str]:
    """
    Load the stored hash map from disk.
    Returns an empty dict if the file doesn't exist yet (first run).
    """
    path = config.HASH_STORE_PATH
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            logger.warning("Hash store file is malformed — starting fresh.")
            return {}
        return data
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not load hash store: {e} — starting fresh.")
        return {}


def save_hashes(hashes: Dict[str, str]) -> None:
    """Persist the hash map to disk, creating parent directories if needed."""
    path = config.HASH_STORE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(hashes, f, indent=2, sort_keys=True)
    logger.info(f"Hash store saved: {len(hashes)} entr(ies) at '{path}'")
