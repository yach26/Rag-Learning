"""
src/config.py — Central configuration for RAGForge
====================================================
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


class Config:
    # ── Paths ────────────────────────────────────────────────────────────────
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    DOCUMENTS_DIR: Path = PROJECT_ROOT / "data" / "documents"
    CHROMA_DB_DIR: Path = PROJECT_ROOT / "chroma_db"

    HASH_STORE_PATH: Path = PROJECT_ROOT / "data" / ".file_hashes.json"
    BM25_INDEX_PATH: Path = PROJECT_ROOT / "data" / ".bm25_index.pkl"

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

    # Groq chat model ID (not Gemini). openai/gpt-oss-20b is Groq's
    # documented default-class model as of 2026. Override with LLM_MODEL.
    LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    MAX_QUERY_CHARS: int = _env_int("MAX_QUERY_CHARS", 4000)
    MAX_UPLOAD_BYTES: int = _env_int("MAX_UPLOAD_BYTES", 20 * 1024 * 1024)
    MAX_PDF_PAGES: int = _env_int("MAX_PDF_PAGES", 200)
    MAX_PDF_SCAN_BYTES: int = _env_int("MAX_PDF_SCAN_BYTES", 2 * 1024 * 1024)
    USE_LLM_GUARDRAIL: bool = _env_bool("USE_LLM_GUARDRAIL", False)

    API_AUTH_TOKEN: str = os.getenv("API_AUTH_TOKEN", "")
    API_RATE_LIMIT_PER_MIN: int = _env_int("API_RATE_LIMIT_PER_MIN", 30)

    # Stream tokens to the UI as they're generated instead of waiting for
    # the full response. Doesn't reduce total latency much, but removes the
    # "did it freeze?" dead air almost entirely.
    STREAM_RESPONSES: bool = True

    # ── UI ───────────────────────────────────────────────────────────────────
    MAX_CHUNK_PREVIEW_CHARS: int = 800


config = Config()
