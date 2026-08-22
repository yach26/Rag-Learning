"""
src/ingest.py — Document Ingestion Module
==========================================

WHAT PROBLEM DOES THIS SOLVE?
------------------------------
Before we can do anything with RAG, we need text. Documents come in many
formats: PDFs, plain text files, Markdown files. Each format requires a
different extraction strategy. This module handles all of that and gives
the rest of the system a uniform output: a list of "document pages", each
being a dict with "text" and "metadata".

WHY THIS DESIGN?
----------------
We extract text page-by-page for PDFs (to preserve page numbers in metadata),
and treat TXT/Markdown as single-page documents. This lets us later tell the
user EXACTLY which page of which document an answer came from — crucial for
RAG transparency.

WHAT GOES IN → WHAT COMES OUT?
-------------------------------
IN:  A folder path containing PDF, TXT, and/or Markdown files
OUT: A list of dicts, each like:
     {
         "text": "The actual text content...",
         "metadata": {
             "source": "example.pdf",
             "page": 3
         }
     }

INTERNAL FLOW:
--------------
load_documents(folder)
    ↓ scans folder, detects file types
    ├── .pdf  → load_pdf()    → uses PyMuPDF (fitz)
    ├── .txt  → load_txt()    → plain read
    └── .md   → load_markdown() → plain read (Markdown is just text)
    ↓
    returns list of {text, metadata} dicts
"""

import re
from pathlib import Path
from typing import List, Dict, Any

import pymupdf as fitz  # PyMuPDF — using new import path (pymupdf), aliased as fitz for compatibility

from src.config import config


# ── Type alias ────────────────────────────────────────────────────────────────
# A "Document" in our system is simply a dict with text + metadata.
# Using a type alias makes function signatures self-documenting.
Document = Dict[str, Any]


# ── Text Cleaning ─────────────────────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Remove excessive whitespace from extracted text.

    WHY: PDF extraction often produces double spaces, trailing spaces,
    and sequences of blank lines. Clean text = smaller chunks = better embeddings.

    We do NOT strip all formatting — we preserve paragraph breaks (double newlines)
    because they signal topic boundaries, which helps chunking later.
    """
    # Replace multiple spaces/tabs with a single space
    text = re.sub(r"[ \t]+", " ", text)

    # Replace 3+ consecutive newlines with exactly 2 (one blank line)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Strip leading/trailing whitespace from the whole document
    text = text.strip()

    return text


# ── Format-specific loaders ───────────────────────────────────────────────────

def load_pdf(file_path: Path) -> List[Document]:
    """
    Extract text from a PDF file, one dict per page.

    WHY PAGE-BY-PAGE?
    -----------------
    Keeping page boundaries lets us tell the user "this answer comes from
    page 7 of research_paper.pdf" — far more useful than just the filename.

    PyMuPDF (fitz) is used because it:
    - Is fast and accurate
    - Handles complex PDF layouts
    - Is pure Python + C (no Java dependency unlike some alternatives)

    Args:
        file_path: Path to the .pdf file

    Returns:
        List of Documents, one per page. Pages with no text are skipped.

    Raises:
        RuntimeError: If the PDF cannot be opened or is corrupted.
    """
    print(f"  [PDF] Extracting: {file_path.name}")
    pages: List[Document] = []

    try:
        document = fitz.open(str(file_path))
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF '{file_path.name}': {e}") from e

    total_pages = len(document)
    print(f"  [PDF] Found {total_pages} page(s)")

    for page_number, page in enumerate(document, start=1):
        try:
            raw_text = page.get_text()
        except Exception as e:
            print(f"  [PDF] WARNING: Could not extract page {page_number}: {e}")
            continue

        text = clean_text(raw_text)

        # Skip empty pages (cover pages, image-only pages, etc.)
        if not text:
            print(f"  [PDF] Skipping page {page_number} (empty after cleaning)")
            continue

        pages.append({
            "text": text,
            "metadata": {
                "source": file_path.name,
                "page": page_number,
            }
        })

    document.close()
    print(f"  [PDF] Extracted {len(pages)} non-empty page(s) from {file_path.name}")
    return pages


def load_txt(file_path: Path) -> List[Document]:
    """
    Load a plain text file as a single document.

    TXT files have no page structure, so we use page=1 for all chunks
    that come from this file.

    Args:
        file_path: Path to the .txt file

    Returns:
        List with a single Document dict.

    Raises:
        RuntimeError: If the file cannot be read.
    """
    print(f"  [TXT] Extracting: {file_path.name}")

    try:
        raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to read TXT '{file_path.name}': {e}") from e

    text = clean_text(raw_text)

    if not text:
        print(f"  [TXT] WARNING: '{file_path.name}' is empty after cleaning — skipping")
        return []

    print(f"  [TXT] Extracted {len(text)} characters from {file_path.name}")
    return [{
        "text": text,
        "metadata": {
            "source": file_path.name,
            "page": 1,
        }
    }]


def load_markdown(file_path: Path) -> List[Document]:
    """
    Load a Markdown (.md) file as a single document.

    Markdown is just plain text with formatting syntax (# headers, **bold**,
    etc.). We keep the raw Markdown text — the embedding model handles it fine,
    and we don't need to render it.

    Args:
        file_path: Path to the .md file

    Returns:
        List with a single Document dict.
    """
    print(f"  [MD] Extracting: {file_path.name}")

    try:
        raw_text = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise RuntimeError(f"Failed to read Markdown '{file_path.name}': {e}") from e

    text = clean_text(raw_text)

    if not text:
        print(f"  [MD] WARNING: '{file_path.name}' is empty after cleaning — skipping")
        return []

    print(f"  [MD] Extracted {len(text)} characters from {file_path.name}")
    return [{
        "text": text,
        "metadata": {
            "source": file_path.name,
            "page": 1,
        }
    }]


# ── Dispatcher ────────────────────────────────────────────────────────────────

# Maps file extension → loader function
LOADERS = {
    ".pdf": load_pdf,
    ".txt": load_txt,
    ".md": load_markdown,
}


def load_single_file(file_path: Path) -> List[Document]:
    """
    Load a single file by detecting its type and calling the appropriate loader.

    Args:
        file_path: Path to any supported document file.

    Returns:
        List of Document dicts.

    Raises:
        ValueError: If the file extension is not supported.
    """
    extension = file_path.suffix.lower()

    if extension not in LOADERS:
        raise ValueError(
            f"Unsupported file type '{extension}' for file '{file_path.name}'. "
            f"Supported types: {list(LOADERS.keys())}"
        )

    loader_fn = LOADERS[extension]
    return loader_fn(file_path)


def load_documents(folder_path: Path | None = None) -> List[Document]:
    """
    Scan a folder and load all supported documents.

    This is the main entry point for the ingestion step. It:
    1. Checks the folder exists
    2. Finds all PDF, TXT, and Markdown files
    3. Loads each one
    4. Returns all pages/documents as a flat list

    Args:
        folder_path: Directory containing documents. Defaults to config.DOCUMENTS_DIR.

    Returns:
        Flat list of all Document dicts across all files.

    Raises:
        FileNotFoundError: If the documents folder doesn't exist.
        RuntimeError: If zero documents are found.
    """
    if folder_path is None:
        folder_path = config.DOCUMENTS_DIR

    # ── Validate folder ───────────────────────────────────────────────────────
    if not folder_path.exists():
        raise FileNotFoundError(
            f"Documents directory not found: '{folder_path}'\n"
            f"Please create it and add your documents there."
        )

    if not folder_path.is_dir():
        raise NotADirectoryError(f"'{folder_path}' is not a directory.")

    # ── Find supported files ──────────────────────────────────────────────────
    supported_extensions = set(LOADERS.keys())
    all_files = [
        f for f in sorted(folder_path.iterdir())
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]

    print(f"\nFound {len(all_files)} document(s) in '{folder_path}'")

    if not all_files:
        raise RuntimeError(
            f"No supported documents found in '{folder_path}'.\n"
            f"Add PDF, TXT, or Markdown files and try again."
        )

    # ── Load each file ────────────────────────────────────────────────────────
    all_documents: List[Document] = []
    failed_files: List[str] = []

    for i, file_path in enumerate(all_files, start=1):
        print(f"\n[{i}/{len(all_files)}] Processing: {file_path.name}")
        try:
            documents = load_single_file(file_path)
            all_documents.extend(documents)
        except (ValueError, RuntimeError) as e:
            # Log the error but continue with other files
            print(f"  ERROR: {e}")
            failed_files.append(file_path.name)

    if failed_files:
        print(f"\nWARNING: Failed to load {len(failed_files)} file(s): {failed_files}")

    print(f"\nIngestion complete: {len(all_documents)} page(s)/document(s) loaded total")
    return all_documents


# ── CLI Entry Point ───────────────────────────────────────────────────────────
# Running:  python -m src.ingest
# Executes the FULL ingestion pipeline:
#   load docs → chunk → embed → store in ChromaDB
#
# This is what you run once (or whenever you add new documents).
# After this, you can query without re-embedding.

def run_ingestion_pipeline() -> None:
    """
    Execute the complete ingestion pipeline end-to-end.

    PIPELINE FLOW:
    --------------
    load_documents()        ← reads PDF/TXT/MD files
          ↓
    chunk_documents()       ← splits into overlapping chunks
          ↓
    embed_documents()       ← generates vectors for each chunk
          ↓
    add_chunks()            ← stores chunks + vectors in ChromaDB
    """
    from src.chunker import chunk_documents, print_chunking_stats
    from src.embedder import embed_documents
    from src.vector_store import add_chunks, get_collection_stats

    print("=" * 60)
    print("RAGForge — Full Ingestion Pipeline")
    print("=" * 60)

    # ── Step 1: Load documents ────────────────────────────────────────────────
    print("\n[Step 1/4] Loading documents...")
    documents = load_documents()
    print(f"  -> Loaded {len(documents)} page(s)/document(s)")

    # -- Step 2: Chunk documents -----------------------------------------------
    print("\n[Step 2/4] Chunking documents...")
    chunks = chunk_documents(documents)
    print_chunking_stats(chunks)
    print(f"  -> Created {len(chunks)} chunk(s)")

    if not chunks:
        print("ERROR: No chunks created. Check your documents.")
        return

    # -- Step 3: Generate embeddings -------------------------------------------
    print("\n[Step 3/4] Generating embeddings...")
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_documents(texts)
    print(f"  -> Generated {len(embeddings)} embedding vectors")

    # -- Step 4: Store in ChromaDB ---------------------------------------------
    print("\n[Step 4/4] Storing in ChromaDB...")
    add_chunks(chunks, embeddings)

    stats = get_collection_stats()
    print(f"  -> ChromaDB now contains {stats['total_chunks']} total chunk(s)")

    print("\n" + "=" * 60)
    print("✓ Ingestion complete! You can now start the UI:")
    print("    streamlit run app.py")
    print("=" * 60)


if __name__ == "__main__":
    run_ingestion_pipeline()