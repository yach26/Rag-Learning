"""
src/ingest.py — Document Ingestion Module
==========================================

CHANGES IN THIS REVISION (Phase 2)
-------------------------------------
1. INCREMENTAL INGESTION (hash-based skip):
   - Each file's content is MD5-hashed before loading.
   - Hash is compared against the stored hash map (.file_hashes.json).
   - Unchanged files are skipped entirely — no re-loading, chunking, or
     embedding. Changed/new files have their old chunks purged first, then
     re-embedded fresh. This makes repeated `python -m src.ingest` runs
     near-instant for large unchanged document sets.

2. OCR FALLBACK (pytesseract):
   - Pages that come back empty after PyMuPDF text extraction are now
     routed through pytesseract if config.USE_OCR_FALLBACK is True.
   - Requires the Tesseract binary:
       Windows: winget install UB-Mannheim.TesseractOCR
       macOS:   brew install tesseract
       Linux:   apt install tesseract-ocr
   - Graceful degradation: if pytesseract or Tesseract is not installed,
     a clear warning is printed and the empty page is silently skipped —
     ingestion never crashes because of a missing OCR dependency.

Phase 1 items preserved:
- Empty-page summary warning (0-of-N pages had text → likely scanned PDF).
- load_txt(), load_markdown(), load_documents() unchanged interfaces.
- clear warning docstring on the empty-page/OCR gap.
"""

import re
from pathlib import Path
from typing import List, Dict, Any

import pymupdf as fitz

from src.config import config

Document = Dict[str, Any]

# Warn once per session if pytesseract/Tesseract is unavailable.
_OCR_AVAILABLE: bool | None = None  # None = not yet checked


def _check_ocr_available() -> bool:
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is not None:
        return _OCR_AVAILABLE
    try:
        import pytesseract
        from PIL import Image  # noqa: F401
        pytesseract.get_tesseract_version()
        _OCR_AVAILABLE = True
    except Exception:
        _OCR_AVAILABLE = False
        print(
            "  [OCR] WARNING: pytesseract or Tesseract binary not found — "
            "OCR fallback disabled for this session.\n"
            "       Install: winget install UB-Mannheim.TesseractOCR  "
            "(then restart)"
        )
    return _OCR_AVAILABLE


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()
    return text


def _ocr_page(page: fitz.Page) -> str:
    """
    Render a PyMuPDF page to a PIL image and run pytesseract on it.
    Returns cleaned extracted text, or "" if OCR fails or is unavailable.
    """
    if not _check_ocr_available():
        return ""
    try:
        import pytesseract
        from PIL import Image

        pix = page.get_pixmap(dpi=config.OCR_DPI)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        raw = pytesseract.image_to_string(img)
        return clean_text(raw)
    except Exception as e:
        print(f"  [OCR] WARNING: OCR failed for page: {e}")
        return ""


def load_pdf(file_path: Path) -> List[Document]:
    print(f"  [PDF] Extracting: {file_path.name}")
    pages: List[Document] = []

    try:
        document = fitz.open(str(file_path))
    except Exception as e:
        raise RuntimeError(f"Failed to open PDF '{file_path.name}': {e}") from e

    total_pages = len(document)
    print(f"  [PDF] Found {total_pages} page(s)")

    ocr_pages = 0

    for page_number, page in enumerate(document, start=1):
        try:
            raw_text = page.get_text()
        except Exception as e:
            print(f"  [PDF] WARNING: Could not extract page {page_number}: {e}")
            continue

        text = clean_text(raw_text)

        if not text:
            if config.USE_OCR_FALLBACK:
                # Route empty pages through pytesseract.
                text = _ocr_page(page)
                if text:
                    ocr_pages += 1
                    print(f"  [OCR] Page {page_number} recovered via OCR ({len(text)} chars)")

        if not text:
            continue  # still empty after OCR attempt — skip

        pages.append({
            "text": text,
            "metadata": {
                "source": file_path.name,
                "page": page_number,
            }
        })

    document.close()

    if not pages and total_pages > 0:
        print(
            f"  [PDF] WARNING: 0 of {total_pages} page(s) had extractable text. "
            f"'{file_path.name}' is likely a scanned/image-only PDF. "
            + (
                "OCR was attempted but also yielded no text — "
                "check Tesseract installation."
                if config.USE_OCR_FALLBACK
                else "Enable USE_OCR_FALLBACK=True in config to activate OCR."
            )
        )
    else:
        ocr_note = f" ({ocr_pages} via OCR)" if ocr_pages else ""
        print(
            f"  [PDF] Extracted {len(pages)} non-empty page(s)"
            f"{ocr_note} from {file_path.name}"
        )

    return pages


def load_txt(file_path: Path) -> List[Document]:
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
        "metadata": {"source": file_path.name, "page": 1}
    }]


def load_markdown(file_path: Path) -> List[Document]:
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
        "metadata": {"source": file_path.name, "page": 1}
    }]


LOADERS = {
    ".pdf": load_pdf,
    ".txt": load_txt,
    ".md": load_markdown,
}


def load_single_file(file_path: Path) -> List[Document]:
    extension = file_path.suffix.lower()

    if extension not in LOADERS:
        raise ValueError(
            f"Unsupported file type '{extension}' for file '{file_path.name}'. "
            f"Supported types: {list(LOADERS.keys())}"
        )

    return LOADERS[extension](file_path)


def load_documents(folder_path: Path | None = None) -> List[Document]:
    if folder_path is None:
        folder_path = config.DOCUMENTS_DIR

    if not folder_path.exists():
        raise FileNotFoundError(
            f"Documents directory not found: '{folder_path}'\n"
            f"Please create it and add your documents there."
        )

    if not folder_path.is_dir():
        raise NotADirectoryError(f"'{folder_path}' is not a directory.")

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

    all_documents: List[Document] = []
    failed_files: List[str] = []
    empty_files: List[str] = []

    for i, file_path in enumerate(all_files, start=1):
        print(f"\n[{i}/{len(all_files)}] Processing: {file_path.name}")
        try:
            documents = load_single_file(file_path)
            if not documents:
                empty_files.append(file_path.name)
            all_documents.extend(documents)
        except (ValueError, RuntimeError) as e:
            print(f"  ERROR: {e}")
            failed_files.append(file_path.name)

    if failed_files:
        print(f"\nWARNING: Failed to load {len(failed_files)} file(s): {failed_files}")
    if empty_files:
        print(
            f"\nWARNING: {len(empty_files)} file(s) produced NO extractable text "
            f"(likely scanned PDFs) and were skipped: {empty_files}"
        )

    print(f"\nIngestion complete: {len(all_documents)} page(s)/document(s) loaded total")
    return all_documents


def run_ingestion_pipeline() -> None:
    from src.chunker import chunk_documents, print_chunking_stats
    from src.embedder import embed_documents
    from src.vector_store import add_chunks, get_collection_stats, delete_chunks_for_source
    from src.hash_store import load_hashes, save_hashes, md5_file
    from src.bm25_store import invalidate_index

    print("=" * 60)
    print("RAGForge — Full Ingestion Pipeline (Phase 2)")
    print("=" * 60)

    # ── Discover files ────────────────────────────────────────────────────────
    folder_path = config.DOCUMENTS_DIR
    if not folder_path.exists():
        raise FileNotFoundError(
            f"Documents directory not found: '{folder_path}'\n"
            f"Please create it and add your documents there."
        )

    supported_extensions = set(LOADERS.keys())
    all_files = [
        f for f in sorted(folder_path.iterdir())
        if f.is_file() and f.suffix.lower() in supported_extensions
    ]

    if not all_files:
        raise RuntimeError(
            f"No supported documents found in '{folder_path}'.\n"
            f"Add PDF, TXT, or Markdown files and try again."
        )

    # ── Load stored hashes ────────────────────────────────────────────────────
    print("\n[Step 0/4] Checking file hashes for incremental ingestion...")
    stored_hashes = load_hashes()
    new_hashes: dict = {}

    files_to_process: list = []
    skipped: list = []

    for file_path in all_files:
        current_hash = md5_file(file_path)
        new_hashes[file_path.name] = current_hash

        if stored_hashes.get(file_path.name) == current_hash:
            print(f"  [SKIP] {file_path.name} — unchanged (hash match)")
            skipped.append(file_path.name)
        else:
            action = "NEW" if file_path.name not in stored_hashes else "CHANGED"
            print(f"  [{action}] {file_path.name} — will re-embed")
            files_to_process.append(file_path)

    if not files_to_process:
        print("\n[OK] All files are unchanged — nothing to re-embed.")
        stats = get_collection_stats()
        print(f"  ChromaDB still contains {stats['total_chunks']} chunk(s).")
        print("=" * 60)
        return

    print(f"\n  {len(files_to_process)} file(s) to process, {len(skipped)} skipped.")

    # ── Purge stale chunks for changed files ──────────────────────────────────
    print("\n[Step 1/4] Purging stale chunks for changed files...")
    for file_path in files_to_process:
        if file_path.name in stored_hashes:
            # File existed before — delete its old chunks before re-adding.
            delete_chunks_for_source(file_path.name)

    # ── Load documents ────────────────────────────────────────────────────────
    print("\n[Step 2/4] Loading changed/new documents...")
    all_documents: List[Document] = []
    failed_files: list = []

    for i, file_path in enumerate(files_to_process, start=1):
        print(f"\n  [{i}/{len(files_to_process)}] {file_path.name}")
        try:
            docs = load_single_file(file_path)
            all_documents.extend(docs)
        except (ValueError, RuntimeError) as e:
            print(f"  ERROR: {e}")
            failed_files.append(file_path.name)
            # Don't update hash for failed files so they're retried next run.
            new_hashes.pop(file_path.name, None)

    if not all_documents:
        print("ERROR: No documents could be loaded from the changed files.")
        return

    # ── Chunk ─────────────────────────────────────────────────────────────────
    print("\n[Step 3/4] Chunking documents...")
    chunks = chunk_documents(all_documents)
    print_chunking_stats(chunks)
    print(f"  -> Created {len(chunks)} chunk(s)")

    if not chunks:
        print("ERROR: No chunks created. Check your documents.")
        return

    # ── Embed + store ─────────────────────────────────────────────────────────
    print("\n[Step 4/4] Generating embeddings and storing in ChromaDB...")
    texts = [chunk["text"] for chunk in chunks]
    embeddings = embed_documents(texts)
    print(f"  -> Generated {len(embeddings)} embedding vectors")
    add_chunks(chunks, embeddings)

    # ── Save updated hashes ───────────────────────────────────────────────────
    # Merge: keep hashes for skipped files, update for processed ones.
    final_hashes = {**stored_hashes, **new_hashes}
    # Remove hashes for files no longer in the folder.
    existing_names = {f.name for f in all_files}
    final_hashes = {k: v for k, v in final_hashes.items() if k in existing_names}
    save_hashes(final_hashes)

    # ── Invalidate BM25 index so it rebuilds with new data ───────────────────
    invalidate_index()

    stats = get_collection_stats()
    print(f"\n  ChromaDB now contains {stats['total_chunks']} total chunk(s)")

    print("\n" + "=" * 60)
    print("[OK] Ingestion complete!")
    if skipped:
        print(f"  Skipped (unchanged): {skipped}")
    if failed_files:
        print(f"  Failed: {failed_files}")
    print("  Start the UI:  streamlit run app.py")
    print("=" * 60)


if __name__ == "__main__":
    run_ingestion_pipeline()
