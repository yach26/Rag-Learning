"""tests/test_rrf.py"""

from src.retriever import reciprocal_rank_fusion


def _chunk(source, chunk_id, text):
    return {"source": source, "chunk_id": chunk_id, "text": text, "page": 1}


def test_rrf_promotes_consensus_docs():
    dense = [
        _chunk("a.pdf", 0, "only dense"),
        _chunk("b.pdf", 0, "shared"),
    ]
    bm25 = [
        _chunk("b.pdf", 0, "shared"),
        _chunk("c.pdf", 0, "only bm25"),
    ]
    fused = reciprocal_rank_fusion([dense, bm25], k=60)
    assert fused[0]["text"] == "shared"
    ids = {(c["source"], c["chunk_id"]) for c in fused}
    assert ("a.pdf", 0) in ids
    assert ("c.pdf", 0) in ids


def test_rrf_empty_lists():
    assert reciprocal_rank_fusion([[], []], k=60) == []
