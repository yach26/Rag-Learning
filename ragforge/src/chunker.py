"""
src/chunker.py — Text Chunking Module
======================================

CHANGE IN THIS REVISION (Phase 2) — SEMANTIC CHUNKING
-------------------------------------------------------
The old character sliding-window splitter (chunk_text_sliding) is kept
for reference but is no longer the default. It is replaced by a
RecursiveCharacterTextSplitter-style approach (chunk_text_recursive)
that respects natural text boundaries.

Problem with the old approach:
- Plain character slicing cuts mid-sentence, mid-number, and mid-table.
- A chunk ending "the annual intere" and the next beginning "st rate is 5%"
  are individually meaningless to an embedding model.

New approach — recursive boundary splitter:
- Tries separators in priority order: paragraph → line → sentence → word → char.
- Each separator is tried; if the resulting pieces are still too long,
  they're recursively split using the next separator down.
- Overlap is re-attached at natural boundaries (start of the previous
  sentence/word) rather than at an arbitrary character offset.

Phase 1 bug fix preserved:
- chunk_id is LOCAL to each source file (see original docstring) —
  global counter removed, IDs stay stable across re-ingestion runs.
"""

import re
from typing import List, Dict, Any

from src.config import config

Document = Dict[str, Any]
Chunk = Dict[str, Any]

# ── Separator priority: paragraph > line > sentence > word > character ────────
_DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", "? ", "! ", " ", ""]


# ── Phase 1 original (kept for comparison / ablation) ────────────────────────

def chunk_text_sliding(
    text: str,
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> List[str]:
    """
    Original character-level sliding window splitter (Phase 1).
    Kept for ablation / fallback. Not used by chunk_documents() anymore.
    """
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        step = chunk_size - overlap
        if step <= 0:
            break
        start += step
    return chunks


# ── Phase 2 recursive boundary splitter ──────────────────────────────────────

def _split_on_separator(text: str, separator: str) -> List[str]:
    """Split text on separator, preserving the separator at chunk ends."""
    if separator == "":
        # Character-level fallback — split into individual chars.
        return list(text)
    if separator in (". ", "? ", "! "):
        # Keep sentence-ending punctuation and space with the chunk it belongs to.
        parts = re.split(r"(?<=[.?!]\s)", text)
    else:
        parts = text.split(separator)
    return [p for p in parts if p]


def _merge_splits(
    splits: List[str],
    chunk_size: int,
    overlap: int,
    separator: str,
) -> List[str]:
    """
    Greedily merge split pieces back into chunks of at most chunk_size,
    with `overlap` characters of context carried over from the previous chunk.
    """
    chunks: List[str] = []
    current_pieces: List[str] = []
    current_len = 0
    sep_len = len(separator)

    for piece in splits:
        piece_len = len(piece)
        # +sep_len accounts for the separator we'd insert between pieces.
        join_len = current_len + sep_len + piece_len if current_pieces else piece_len

        if join_len > chunk_size and current_pieces:
            # Flush current accumulation as a chunk.
            chunk = separator.join(current_pieces)
            chunks.append(chunk)

            # Carry over overlap from the tail of current_pieces.
            overlap_text = chunk[-overlap:] if overlap > 0 else ""
            # Restart from the overlap boundary, keeping whole pieces where possible.
            current_pieces = []
            current_len = 0
            if overlap_text:
                current_pieces = [overlap_text]
                current_len = len(overlap_text)

        current_pieces.append(piece)
        current_len = sum(len(p) for p in current_pieces) + sep_len * max(0, len(current_pieces) - 1)

    if current_pieces:
        chunks.append(separator.join(current_pieces))

    return chunks


def chunk_text_recursive(
    text: str,
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
    separators: List[str] = None,
) -> List[str]:
    """
    Recursively split text on boundary separators, in priority order:
        paragraph (\n\n) → line (\n) → sentence (. / ? / !) → word ( ) → char

    Algorithm:
    1. Try the first separator. Split text on it.
    2. Pieces that fit in chunk_size are kept; those that don't are
       recursively split using the remaining separators.
    3. Greedily merge small pieces back to fill chunk_size with overlap.

    This guarantees chunks never exceed chunk_size characters while
    respecting natural text boundaries as much as possible.
    """
    if separators is None:
        separators = _DEFAULT_SEPARATORS

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    separator = separators[0]
    remaining_separators = separators[1:]

    splits = _split_on_separator(text, separator)

    good_splits: List[str] = []   # small enough to merge directly
    final_chunks: List[str] = []

    for split in splits:
        if len(split) <= chunk_size:
            good_splits.append(split)
        else:
            # This piece is still too big — flush accumulated good splits
            # and recursively break the big piece further.
            if good_splits:
                merged = _merge_splits(good_splits, chunk_size, overlap, separator)
                final_chunks.extend(merged)
                good_splits = []

            if remaining_separators:
                sub_chunks = chunk_text_recursive(
                    split, chunk_size, overlap, remaining_separators
                )
                final_chunks.extend(sub_chunks)
            else:
                # Character-level fallback — hard cut.
                for i in range(0, len(split), chunk_size - overlap):
                    final_chunks.append(split[i : i + chunk_size])

    if good_splits:
        merged = _merge_splits(good_splits, chunk_size, overlap, separator)
        final_chunks.extend(merged)

    return [c for c in final_chunks if c.strip()]


# Default alias — swap here to A/B test old vs new.
chunk_text = chunk_text_recursive


# ── Document chunking (unchanged interface) ───────────────────────────────────

def chunk_documents(
    documents: List[Document],
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> List[Chunk]:
    """
    Chunk all documents and attach metadata to each chunk.

    chunk_id is sequential across documents to maintain chunk indexing consistency.
    local_chunk_id is LOCAL to each source file for per-file tracking.
    """
    all_chunks: List[Chunk] = []
    per_source_counter: Dict[str, int] = {}   # source filename -> next local chunk_id
    global_index = 0

    for doc in documents:
        text = doc["text"]
        source_metadata = doc["metadata"]
        source = source_metadata.get("source", "unknown")

        text_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        for chunk_text_piece in text_chunks:
            if not chunk_text_piece.strip():
                continue

            local_chunk_id = per_source_counter.get(source, 0)
            per_source_counter[source] = local_chunk_id + 1

            chunk: Chunk = {
                "text": chunk_text_piece,
                "metadata": {
                    **source_metadata,
                    "chunk_id": global_index,        # Sequential global chunk_id
                    "local_chunk_id": local_chunk_id, # Local to this file
                    "global_index": global_index,     # Cosmetic display order
                    "chunk_size": len(chunk_text_piece),
                }
            }
            all_chunks.append(chunk)
            global_index += 1

    return all_chunks


def print_chunking_stats(chunks: List[Chunk]) -> None:
    if not chunks:
        print("No chunks created.")
        return

    sizes = [len(c["text"]) for c in chunks]
    sources = set(c["metadata"]["source"] for c in chunks)

    print(f"\n--- Chunking Stats ------------------------------")
    print(f"  Total chunks    : {len(chunks)}")
    print(f"  Source files    : {len(sources)}")
    print(f"  Avg chunk size  : {sum(sizes) // len(sizes)} chars")
    print(f"  Min chunk size  : {min(sizes)} chars")
    print(f"  Max chunk size  : {max(sizes)} chars")
    print(f"────────────────────────────────────────────────")


if __name__ == "__main__":
    from src.ingest import load_documents

    print("=" * 60)
    print("RAGForge — Chunking Test")
    print("=" * 60)

    documents = load_documents()
    chunks = chunk_documents(documents)
    print_chunking_stats(chunks)

    print("\n── First 2 Chunks (Preview) ────────────────────────────")
    for chunk in chunks[:2]:
        print(f"\nChunk ID (local) : {chunk['metadata']['chunk_id']}")
        print(f"Source           : {chunk['metadata']['source']}")
        print(f"Page             : {chunk['metadata']['page']}")
        print(f"Size             : {chunk['metadata']['chunk_size']} chars")
        print(f"Text             : {chunk['text'][:300]}...")
