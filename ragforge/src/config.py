"""
src/config.py — Central configuration for RAGForge
====================================================

WHY THIS FILE EXISTS
--------------------
Without a config file, you'd scatter magic numbers and file paths throughout
your code. If you want to change the chunk size, you'd have to hunt down every
place it's used. By putting everything here, you change ONE value and it
propagates everywhere.

This is also where we load environment variables from the .env file so that
the rest of the codebase never has to call os.getenv() directly.

HOW TO USE
----------
    from src.config import config
    print(config.CHUNK_SIZE)
    print(config.LLM_API_KEY)
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env file ──────────────────────────────────────────────────────────
# This looks for a .env file starting from the project root.
# If you run scripts from inside the ragforge/ directory, Path.cwd() is correct.
# If you ever run from a subdirectory, update this path accordingly.
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


class Config:
    """
    All configuration lives here as class attributes.
    Accessing config.CHUNK_SIZE is explicit and easy to find.
    """

    # ── Paths ────────────────────────────────────────────────────────────────
    # Root of the ragforge project (the folder containing src/, data/, etc.)
    PROJECT_ROOT: Path = Path(__file__).parent.parent

    # Where user documents are stored (PDF, TXT, Markdown)
    DOCUMENTS_DIR: Path = PROJECT_ROOT / "data" / "documents"

    # Where ChromaDB will persist its data on disk
    CHROMA_DB_DIR: Path = PROJECT_ROOT / "chroma_db"

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    # The name of the ChromaDB collection we'll store all chunks in.
    # Think of a "collection" like a table in a relational database.
    CHROMA_COLLECTION_NAME: str = "ragforge_documents"

    # ── Embedding Model ──────────────────────────────────────────────────────
    # sentence-transformers model to use for embedding text into vectors.
    #
    # all-MiniLM-L6-v2 is a great beginner model:
    #   - Small: ~80 MB download
    #   - Fast: runs on CPU in milliseconds
    #   - Good quality: 384-dimensional vectors
    #   - Free: runs entirely locally, no API key needed
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── Chunking ─────────────────────────────────────────────────────────────
    # CHUNK_SIZE: How many characters per chunk.
    #
    # A quick mental model:
    #   1 token ≈ 4 characters (in English)
    #   500 tokens ≈ 2000 characters
    #
    # Why 2000 chars? It's a good balance:
    #   - Large enough to contain complete thoughts and sentences
    #   - Small enough that the LLM gets focused, relevant context
    CHUNK_SIZE: int = 2000       # characters

    # CHUNK_OVERLAP: How many characters from the end of one chunk
    # are repeated at the start of the next chunk.
    #
    # Why overlap? Imagine a sentence that falls exactly on the boundary
    # between two chunks. Without overlap, neither chunk contains the full
    # thought. With overlap, at least one chunk will have it complete.
    CHUNK_OVERLAP: int = 200     # characters

    # ── Retrieval ────────────────────────────────────────────────────────────
    # How many chunks to retrieve from ChromaDB for each user query.
    # More chunks = more context for the LLM, but also more tokens = slower + costlier.
    TOP_K: int = 5

    # ── LLM / Generation ────────────────────────────────────────────────────
    # API key loaded from .env — never hardcoded here.
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

    # Which Gemini model to use. gemini-3.6-flash is the current recommended model.
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.6-flash")


# Single shared instance — import this everywhere:
#   from src.config import config
config = Config()
