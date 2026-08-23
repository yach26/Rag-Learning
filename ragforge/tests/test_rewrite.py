"""tests/test_rewrite.py"""

from src.query.rewrite import _looks_like_followup, rewrite_query


def test_followup_heuristic():
    assert _looks_like_followup("what about that?")
    assert _looks_like_followup("and also")
    assert not _looks_like_followup("What is the refund window in the employee handbook?")


def test_rewrite_skips_without_history():
    q = "what about the second one?"
    assert rewrite_query(q, history=[]) == q


def test_rewrite_skips_self_contained_even_with_history():
    q = "What is the refund window in the employee handbook?"
    history = [{"role": "user", "content": "Hello"}, {"role": "assistant", "content": "Hi"}]
    assert rewrite_query(q, history) == q
