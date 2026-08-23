"""
src/config.py — Central configuration for RAGForge
====================================================

CHANGES IN THIS REVISION (Phase 2)
-------------------------------------
- HASH_STORE_PATH: path for incremental-ingestion MD5 hash map.
- HYBRID_CANDIDATES / BM25_WEIGHT / RRF_K: hybrid BM25+vector search.
- RERANKER_MODEL / RERANK_CANDIDATES / USE_RERANKER: CrossEncoder rerank.
- USE_OCR_FALLBACK / OCR_DPI: pytesseract OCR for scanned PDF pages.
- CONVERSATION_HISTORY_TURNS: how many prior turns to include in prompts
  and pass to the query rewriter.

Phase 1 changes kept:
- STREAM_RESPONSES: stream Gemini tokens to UI.
- TOP_K / TOP_K_MAX: retrieval depth defaults.
- MAX_CHUNK_PREVIEW_CHARS: UI preview length.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


class Config:
    # ── Paths ────────────────────────────────────────────────────────────────
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DOCUMENTS_DIR: Path = PROJECT_ROOT / "data" / "documents"
    CHROMA_DB_DIR: Path = PROJECT_ROOT / "chroma_db"

    # Phase 2: Incremental ingestion hash store
    HASH_STORE_PATH: Path = PROJECT_ROOT / "data" / ".file_hashes.json"

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    CHROMA_COLLECTION_NAME: str = "ragforge_documents"

    # ── Embedding Model ──────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── Chunking ─────────────────────────────────────────────────────────────
    CHUNK_SIZE: int = 2000       # characters (~500 tokens)
    CHUNK_OVERLAP: int = 200     # characters

    # ── Retrieval ────────────────────────────────────────────────────────────
    # Default top_k. Increased to 8 to handle multi-page summary questions.
    TOP_K: int = 8
    TOP_K_MAX: int = 25          # UI slider ceiling

    # Phase 2: Hybrid search — fetch this many candidates from each ranker
    # before merging with Reciprocal Rank Fusion, then reranking.
    HYBRID_CANDIDATES: int = 20

    # Reciprocal Rank Fusion constant (standard value = 60).
    RRF_K: int = 60

    # ── Reranking ────────────────────────────────────────────────────────────
    # CrossEncoder model for reranking — CPU-friendly, ~85 MB download.
    RERANKER_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # How many hybrid candidates to pipe into the reranker.
    # Must be <= HYBRID_CANDIDATES. Final answer uses TOP_K.
    RERANK_CANDIDATES: int = 20

    # Set to False to skip reranking (useful for ablation / debugging).
    USE_RERANKER: bool = True

    # ── Conversation ─────────────────────────────────────────────────────────
    # How many prior conversation turns (user+assistant pairs) to include
    # in the query rewriter and in the generation prompt.
    CONVERSATION_HISTORY_TURNS: int = 3

    # ── OCR ──────────────────────────────────────────────────────────────────
    # Route empty PDF pages through pytesseract for scanned/image-only PDFs.
    # Requires Tesseract binary: winget install UB-Mannheim.TesseractOCR
    USE_OCR_FALLBACK: bool = True

    # Page render DPI for OCR — 200 is a good speed/quality balance.
    # Use 300 for small-print or dense technical documents.
    OCR_DPI: int = 200

    # ── LLM / Generation ────────────────────────────────────────────────────
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # gemini-2.0-flash: strong reasoning, fast output.
    # gemini-2.0-flash-lite: noticeably cheaper & lower-latency if you want
    #   to test basic queries and don't need top-tier reasoning.
    #   reasoning headroom. Swap via LLM_MODEL in your .env — no code change.
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

    # Stream tokens to the UI as they're generated instead of waiting for
    # the full response. Doesn't reduce total latency much, but removes the
    # "did it freeze?" dead air almost entirely.
    STREAM_RESPONSES: bool = True

    # ── UI ───────────────────────────────────────────────────────────────────
    MAX_CHUNK_PREVIEW_CHARS: int = 800


config = Config()
