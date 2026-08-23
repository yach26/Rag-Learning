"""tests/test_cache.py"""

from src.cache import clear_cache, get_cached_answer, set_cached_answer


def test_cache_roundtrip(tmp_path, monkeypatch):
    from src import cache as cache_mod

    monkeypatch.setattr(cache_mod, "CACHE_FILE_PATH", tmp_path / "query_cache.json")
    clear_cache()
    assert get_cached_answer("What is RAG?", "dense") is None
    set_cached_answer("What is RAG?", "dense", "Retrieval-Augmented Generation")
    assert get_cached_answer("What is RAG?", "dense") == "Retrieval-Augmented Generation"
    assert get_cached_answer("What is RAG?", "bm25") is None
    clear_cache()
    assert get_cached_answer("What is RAG?", "dense") is None
