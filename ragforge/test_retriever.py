"""
test_retriever.py — Tests for the Retrieval Pipeline
======================================================

Run with:
    pytest test_retriever.py -v

These tests exercise the full retrieval stack:
    embedder → vector_store → retriever

We use an isolated ChromaDB collection (different name from production)
so tests never touch your real data.
"""

import pytest
from typing import List

from src.embedder import embed_documents, embed_query
from src.vector_store import add_chunks, query, clear_collection, get_collection_stats
from src.retriever import retrieve
from src.config import config


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def isolated_collection(monkeypatch):
    """
    Use a separate ChromaDB collection for tests so we never pollute production data.

    autouse=True means this fixture runs before EVERY test in this file.
    After each test, the test collection is cleared.
    """
    # Point to a different collection name for tests
    monkeypatch.setattr(config, "CHROMA_COLLECTION_NAME", "ragforge_test_collection")

    # Also use the same chroma_db directory (it's local) but a different collection
    yield  # Run the test

    # Cleanup: clear the test collection after each test
    clear_collection()


def _make_chunks(texts: List[str], source: str = "test.txt") -> List[dict]:
    """Helper: create chunk dicts from a list of text strings."""
    return [
        {
            "text": text,
            "metadata": {
                "source": source,
                "page": i + 1,
                "chunk_id": i,
                "chunk_size": len(text),
            }
        }
        for i, text in enumerate(texts)
    ]


# ── Embedding tests ───────────────────────────────────────────────────────────

class TestEmbedder:
    """Test that the embedding model produces sensible outputs."""

    def test_embed_single_text(self):
        texts = ["Machine learning is a field of artificial intelligence."]
        vectors = embed_documents(texts)

        assert len(vectors) == 1
        assert len(vectors[0]) == 384  # all-MiniLM-L6-v2 produces 384-dim vectors

    def test_embed_multiple_texts(self):
        texts = ["First sentence.", "Second sentence.", "Third sentence."]
        vectors = embed_documents(texts)

        assert len(vectors) == 3
        assert all(len(v) == 384 for v in vectors)

    def test_embed_empty_list_returns_empty(self):
        vectors = embed_documents([])
        assert vectors == []

    def test_embed_query_returns_384_dim_vector(self):
        vec = embed_query("What is machine learning?")
        assert len(vec) == 384

    def test_embed_query_raises_on_empty_string(self):
        with pytest.raises(ValueError, match="empty"):
            embed_query("")

    def test_similar_texts_have_similar_vectors(self):
        """Semantically similar texts should have high cosine similarity."""
        vec1 = embed_query("What is machine learning?")
        vec2 = embed_query("Explain artificial intelligence and machine learning.")
        vec3 = embed_query("What is the recipe for chocolate cake?")

        def cosine_sim(a, b):
            import math
            dot = sum(x * y for x, y in zip(a, b))
            mag_a = math.sqrt(sum(x**2 for x in a))
            mag_b = math.sqrt(sum(x**2 for x in b))
            return dot / (mag_a * mag_b)

        sim_related = cosine_sim(vec1, vec2)
        sim_unrelated = cosine_sim(vec1, vec3)

        # Related texts should be more similar than unrelated ones
        assert sim_related > sim_unrelated


# ── Vector store tests ────────────────────────────────────────────────────────

class TestVectorStore:
    """Test ChromaDB insertion and querying."""

    def test_add_chunks_stores_data(self):
        texts = ["Python is a programming language.", "Machine learning uses algorithms."]
        chunks = _make_chunks(texts)
        embeddings = embed_documents(texts)

        add_chunks(chunks, embeddings)

        stats = get_collection_stats()
        assert stats["total_chunks"] == 2

    def test_query_returns_results(self):
        texts = [
            "Python is a popular programming language.",
            "Machine learning is a branch of AI.",
            "The Eiffel Tower is in Paris.",
        ]
        chunks = _make_chunks(texts)
        embeddings = embed_documents(texts)
        add_chunks(chunks, embeddings)

        query_vec = embed_query("Tell me about Python programming")
        results = query(query_vec, top_k=2)

        assert len(results) == 2

    def test_query_result_has_required_fields(self):
        texts = ["Transformers are a type of neural network architecture."]
        chunks = _make_chunks(texts, source="ml_paper.txt")
        embeddings = embed_documents(texts)
        add_chunks(chunks, embeddings)

        query_vec = embed_query("What is a transformer?")
        results = query(query_vec, top_k=1)

        assert len(results) == 1
        result = results[0]

        assert "text" in result
        assert "source" in result
        assert "page" in result
        assert "distance" in result

    def test_most_relevant_chunk_is_first(self):
        """The most semantically similar chunk should come first (lowest distance)."""
        texts = [
            "Machine learning algorithms learn from data.",
            "The weather today is sunny and warm.",
            "I enjoy cooking Italian food on weekends.",
        ]
        chunks = _make_chunks(texts)
        embeddings = embed_documents(texts)
        add_chunks(chunks, embeddings)

        query_vec = embed_query("How do machine learning models work?")
        results = query(query_vec, top_k=3)

        # The ML chunk should be the most relevant (lowest distance = first result)
        assert "machine learning" in results[0]["text"].lower() or \
               "learn" in results[0]["text"].lower()

    def test_distances_are_sorted_ascending(self):
        """Results should be ordered from most to least relevant (lowest to highest distance)."""
        texts = [
            "Artificial intelligence and machine learning research.",
            "Python programming language features.",
            "Mediterranean cuisine and cooking techniques.",
        ]
        chunks = _make_chunks(texts)
        embeddings = embed_documents(texts)
        add_chunks(chunks, embeddings)

        query_vec = embed_query("Deep learning neural networks")
        results = query(query_vec, top_k=3)

        distances = [r["distance"] for r in results]
        assert distances == sorted(distances)

    def test_upsert_does_not_create_duplicates(self):
        """Running ingestion twice should not double the chunk count."""
        texts = ["Only this chunk should exist."]
        chunks = _make_chunks(texts)
        embeddings = embed_documents(texts)

        # Add twice
        add_chunks(chunks, embeddings)
        add_chunks(chunks, embeddings)

        stats = get_collection_stats()
        assert stats["total_chunks"] == 1  # Not 2

    def test_metadata_source_is_stored_correctly(self):
        texts = ["Test document content."]
        chunks = _make_chunks(texts, source="important_paper.pdf")
        embeddings = embed_documents(texts)
        add_chunks(chunks, embeddings)

        query_vec = embed_query("Test document")
        results = query(query_vec, top_k=1)

        assert results[0]["source"] == "important_paper.pdf"

    def test_query_empty_collection_raises_runtime_error(self):
        # Collection starts empty (cleared by fixture)
        query_vec = embed_query("any query")

        with pytest.raises(RuntimeError, match="empty"):
            query(query_vec, top_k=5)

    def test_top_k_limits_results(self):
        texts = [f"Document number {i}" for i in range(10)]
        chunks = _make_chunks(texts)
        embeddings = embed_documents(texts)
        add_chunks(chunks, embeddings)

        query_vec = embed_query("Document")
        results = query(query_vec, top_k=3)

        assert len(results) == 3


# ── End-to-end retriever test ─────────────────────────────────────────────────

class TestRetriever:
    """End-to-end test of the retrieve() function."""

    def test_retrieve_returns_results_for_relevant_query(self):
        texts = [
            "Natural language processing enables computers to understand text.",
            "Vector databases store high-dimensional embeddings efficiently.",
            "The Andes mountain range spans multiple South American countries.",
        ]
        chunks = _make_chunks(texts)
        embeddings = embed_documents(texts)
        add_chunks(chunks, embeddings)

        results = retrieve("How do computers process language?", top_k=2)

        assert len(results) == 2
        assert "text" in results[0]
        assert "source" in results[0]

    def test_retrieve_raises_on_empty_query(self):
        with pytest.raises(ValueError, match="empty"):
            retrieve("")

    def test_retrieve_raises_on_empty_db(self):
        with pytest.raises(RuntimeError):
            retrieve("any question")
