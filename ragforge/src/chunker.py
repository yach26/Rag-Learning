"""
src/chunker.py — Text Chunking Module
======================================

WHAT PROBLEM DOES THIS SOLVE?
------------------------------
Embedding models have a maximum input size (usually 256–512 tokens for
all-MiniLM-L6-v2). Even if they didn't, embedding an entire 200-page PDF as
one vector is useless — it would average out all the meaning into a muddy blob.

We need to split documents into small, focused chunks so that:
1. Each chunk fits within the embedding model's context window
2. Each chunk represents a specific, focused topic or idea
3. Retrieval can pinpoint WHICH part of a document is relevant

WHY CHARACTER-BASED SPLITTING? (Phase 1)
-----------------------------------------
Three ways to measure text size:

  CHARACTERS: "Hello" = 5 chars. Simple. No model needed. What we use here.
  WORDS:      "Hello world" = 2 words. Better approximation, but "supercalifragilistic"
              and "I" both count as 1 word despite very different sizes.
  TOKENS:     What LLMs actually count. "Hello" might be 1 token, "supercalifragilistic"
              might be 3-4 tokens. Requires loading a tokenizer to count accurately.

For Phase 1, characters are fine. The rule of thumb:
    1 token ≈ 4 characters (English text)
    500 tokens ≈ 2000 characters  ← our default CHUNK_SIZE

WHAT IS OVERLAP AND WHY DO WE NEED IT?
---------------------------------------
Imagine this text:

    "...The model was trained on... [CHUNK BOUNDARY] ...ImageNet dataset..."

Without overlap, the phrase "trained on ImageNet" is split between two chunks.
A query about "ImageNet training" might miss it entirely.

With overlap, the END of chunk N is REPEATED at the START of chunk N+1:

    Chunk 1: "...The model was trained on..."          ← ends here
    Chunk 2: "...trained on ImageNet dataset..."       ← repeats the overlap
                ↑ this repeated part is the "overlap"

The user query "What dataset was the model trained on?" now has a complete
sentence to match against in chunk 2.

INTERNAL FLOW:
--------------
chunk_documents(documents)
    → for each document:
        chunk_text(text, chunk_size, overlap)
            → sliding window over character positions
            → yields text slices
        → each slice becomes a chunk with inherited + new metadata
    → returns flat list of chunks

WHAT GOES IN → WHAT COMES OUT:
-------------------------------
IN:  list of {text, metadata} dicts (output from ingest.py)
OUT: list of {text, metadata} dicts, where metadata now also has chunk_id

Example chunk:
{
    "text": "Machine learning is a subset of artificial intelligence...",
    "metadata": {
        "source": "ml_intro.pdf",
        "page": 2,
        "chunk_id": 7
    }
}
"""

from typing import List, Dict, Any

from src.config import config


# ── Type alias ────────────────────────────────────────────────────────────────
Document = Dict[str, Any]
Chunk = Dict[str, Any]


def chunk_text(
    text: str,
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> List[str]:
    """
    Split a single string into overlapping chunks using a sliding window.

    This is the core algorithm. Think of it like a window moving across the text:

        Text: "AAAAAABBBBBBBCCCCCCDDDDDD"
              |-- chunk 1 --|
                    |-- chunk 2 --|
                          |-- chunk 3 --|

    The overlap is how much of chunk N is repeated in chunk N+1.

    Args:
        text:       The full text string to split.
        chunk_size: Maximum number of characters per chunk.
        overlap:    Number of characters to repeat between consecutive chunks.

    Returns:
        List of text strings, each at most chunk_size characters.

    Notes:
        - If text is shorter than chunk_size, returns [text] (a single chunk).
        - Chunks are purely character-based — no sentence boundary detection.
          This is intentional for Phase 1 simplicity.
    """
    if not text:
        return []

    # If the whole text fits in one chunk, return it as-is
    if len(text) <= chunk_size:
        return [text]

    chunks: List[str] = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)

        # Move the start forward by (chunk_size - overlap)
        # This ensures the next chunk "backs up" by overlap characters
        step = chunk_size - overlap
        start += step

        # Safety check: if step is 0 or negative, we'd loop forever
        if step <= 0:
            break

    return chunks


def chunk_documents(
    documents: List[Document],
    chunk_size: int = config.CHUNK_SIZE,
    overlap: int = config.CHUNK_OVERLAP,
) -> List[Chunk]:
    """
    Chunk all documents and attach metadata to each chunk.

    This is the main entry point for the chunking step.
    It processes every document and assigns a global chunk_id to each chunk
    so we can uniquely identify it in ChromaDB later.

    Args:
        documents:  List of Document dicts (output from ingest.py)
        chunk_size: Characters per chunk (default from config)
        overlap:    Characters of overlap (default from config)

    Returns:
        Flat list of Chunk dicts with text + extended metadata.

    Example:
        Input:  [{"text": "long text...", "metadata": {"source": "x.pdf", "page": 1}}]
        Output: [
            {"text": "long te...", "metadata": {"source": "x.pdf", "page": 1, "chunk_id": 0}},
            {"text": "ext...",     "metadata": {"source": "x.pdf", "page": 1, "chunk_id": 1}},
        ]
    """
    all_chunks: List[Chunk] = []
    global_chunk_id = 0  # Unique ID across ALL chunks from ALL documents

    for doc in documents:
        text = doc["text"]
        source_metadata = doc["metadata"]  # e.g., {"source": "paper.pdf", "page": 3}

        text_chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        for chunk_text_piece in text_chunks:
            # Skip any empty chunk (can happen with edge cases in the text)
            if not chunk_text_piece.strip():
                continue

            chunk: Chunk = {
                "text": chunk_text_piece,
                "metadata": {
                    # Inherit source metadata from the parent document
                    **source_metadata,
                    # Add chunk-specific metadata
                    "chunk_id": global_chunk_id,
                    "chunk_size": len(chunk_text_piece),
                }
            }
            all_chunks.append(chunk)
            global_chunk_id += 1

    return all_chunks


def print_chunking_stats(chunks: List[Chunk]) -> None:
    """
    Print a summary of the chunking results.
    Useful for debugging and understanding the output.
    """
    if not chunks:
        print("No chunks created.")
        return

    sizes = [len(c["text"]) for c in chunks]
    sources = set(c["metadata"]["source"] for c in chunks)

    print(f"\n── Chunking Stats ──────────────────────────────")
    print(f"  Total chunks    : {len(chunks)}")
    print(f"  Source files    : {len(sources)}")
    print(f"  Avg chunk size  : {sum(sizes) // len(sizes)} chars")
    print(f"  Min chunk size  : {min(sizes)} chars")
    print(f"  Max chunk size  : {max(sizes)} chars")
    print(f"────────────────────────────────────────────────")


# ── CLI Entry Point ───────────────────────────────────────────────────────────
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
        print(f"\nChunk ID : {chunk['metadata']['chunk_id']}")
        print(f"Source   : {chunk['metadata']['source']}")
        print(f"Page     : {chunk['metadata']['page']}")
        print(f"Size     : {chunk['metadata']['chunk_size']} chars")
        print(f"Text     : {chunk['text'][:300]}...")
