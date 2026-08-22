"""
test_chunker.py — Tests for the Chunking Module
=================================================

Run with:
    pytest test_chunker.py -v
"""

import pytest
from src.chunker import chunk_text, chunk_documents


# ── chunk_text tests ──────────────────────────────────────────────────────────

class TestChunkText:
    """Test the core text splitting algorithm."""

    def test_short_text_returns_single_chunk(self):
        text = "Short text."
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_empty_text_returns_empty_list(self):
        chunks = chunk_text("", chunk_size=500, overlap=50)
        assert chunks == []

    def test_long_text_creates_multiple_chunks(self):
        # 1000-char text with chunk_size=300 should produce more than 1 chunk
        text = "A" * 1000
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        assert len(chunks) > 1

    def test_each_chunk_is_at_most_chunk_size(self):
        text = "B" * 2000
        chunk_size = 400
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=50)
        for chunk in chunks:
            assert len(chunk) <= chunk_size

    def test_overlap_means_chunks_share_content(self):
        """The end of chunk N should appear at the start of chunk N+1."""
        text = "C" * 600  # all same char, easy to check overlap
        overlap = 100
        chunk_size = 300
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        # Each chunk should be chunk_size long (except possibly the last)
        assert len(chunks) >= 2

        # The last `overlap` characters of chunk 0 should equal
        # the first `overlap` characters of chunk 1
        end_of_first = chunks[0][-overlap:]
        start_of_second = chunks[1][:overlap]
        assert end_of_first == start_of_second

    def test_exact_chunk_size_text_returns_one_chunk(self):
        text = "X" * 500
        chunks = chunk_text(text, chunk_size=500, overlap=50)
        assert len(chunks) == 1

    def test_text_one_char_over_chunk_size_creates_two_chunks(self):
        chunk_size = 500
        text = "Y" * (chunk_size + 1)
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=50)
        assert len(chunks) == 2

    def test_all_content_is_preserved_in_chunks(self):
        """Every character in the original text should appear in at least one chunk."""
        text = "The quick brown fox jumps over the lazy dog. " * 50
        chunk_size = 200
        overlap = 20
        chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)

        # Reconstruct: de-overlapped content should cover the whole text
        # Simple check: all characters from start and end are present
        assert text[:10] in chunks[0]
        assert text[-10:] in chunks[-1]


# ── chunk_documents tests ─────────────────────────────────────────────────────

class TestChunkDocuments:
    """Test the document-level chunking with metadata."""

    def _make_doc(self, text: str, source: str = "test.txt", page: int = 1) -> dict:
        return {"text": text, "metadata": {"source": source, "page": page}}

    def test_empty_documents_returns_empty_list(self):
        chunks = chunk_documents([])
        assert chunks == []

    def test_creates_chunks_from_single_document(self):
        doc = self._make_doc("A" * 1000)
        chunks = chunk_documents([doc], chunk_size=300, overlap=50)
        assert len(chunks) > 1

    def test_chunk_has_text_and_metadata(self):
        doc = self._make_doc("Hello world. " * 10)
        chunks = chunk_documents([doc], chunk_size=50, overlap=10)

        assert len(chunks) >= 1
        chunk = chunks[0]

        assert "text" in chunk
        assert "metadata" in chunk

    def test_metadata_preserves_source(self):
        doc = self._make_doc("Content here. " * 20, source="paper.pdf")
        chunks = chunk_documents([doc], chunk_size=100, overlap=20)

        for chunk in chunks:
            assert chunk["metadata"]["source"] == "paper.pdf"

    def test_metadata_preserves_page_number(self):
        doc = self._make_doc("Content. " * 30, page=7)
        chunks = chunk_documents([doc], chunk_size=100, overlap=20)

        for chunk in chunks:
            assert chunk["metadata"]["page"] == 7

    def test_chunk_ids_are_unique(self):
        doc = self._make_doc("Content. " * 50)
        chunks = chunk_documents([doc], chunk_size=100, overlap=20)

        chunk_ids = [c["metadata"]["chunk_id"] for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))  # all unique

    def test_chunk_ids_are_sequential(self):
        doc = self._make_doc("Content. " * 50)
        chunks = chunk_documents([doc], chunk_size=100, overlap=20)

        chunk_ids = [c["metadata"]["chunk_id"] for c in chunks]
        assert chunk_ids == list(range(len(chunks)))

    def test_chunk_ids_are_global_across_documents(self):
        """chunk_ids should be unique across multiple documents, not reset per doc."""
        doc1 = self._make_doc("A" * 500, source="doc1.txt")
        doc2 = self._make_doc("B" * 500, source="doc2.txt")

        chunks = chunk_documents([doc1, doc2], chunk_size=200, overlap=20)

        chunk_ids = [c["metadata"]["chunk_id"] for c in chunks]
        # Should be 0, 1, 2, 3, 4... not 0,1,2 then 0,1,2 again
        assert chunk_ids == list(range(len(chunks)))

    def test_short_doc_creates_single_chunk(self):
        doc = self._make_doc("Short document.")
        chunks = chunk_documents([doc], chunk_size=2000, overlap=200)
        assert len(chunks) == 1
        assert chunks[0]["text"] == "Short document."

    def test_chunk_size_is_recorded_in_metadata(self):
        doc = self._make_doc("Hello world. " * 5)
        chunks = chunk_documents([doc], chunk_size=2000, overlap=200)

        chunk = chunks[0]
        assert "chunk_size" in chunk["metadata"]
        assert chunk["metadata"]["chunk_size"] == len(chunk["text"])

    def test_multiple_documents_all_chunked(self):
        docs = [
            self._make_doc("Document one. " * 30, source="one.txt"),
            self._make_doc("Document two. " * 30, source="two.txt"),
            self._make_doc("Document three. " * 30, source="three.txt"),
        ]
        chunks = chunk_documents(docs, chunk_size=200, overlap=20)

        sources = set(c["metadata"]["source"] for c in chunks)
        assert "one.txt" in sources
        assert "two.txt" in sources
        assert "three.txt" in sources
