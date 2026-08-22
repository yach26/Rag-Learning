"""
src/query/expansion.py — Query Expansion
=========================================

Query expansion addresses a fundamental limitation of semantic search:
vocabulary mismatch. If the user asks about "caching" but the documents
use terms like "memory cache", "hit rate", "LRU", and "invalidation",
the vector distance might be further apart than expected.

This module uses an LLM to generate highly relevant synonyms, related
concepts, and jargon for the given query. These terms are then appended
to the original query before embedding/BM25.

Why do this?
- Increases Recall: Brings in documents that use different terminology.
- Helps BM25: BM25 strictly relies on exact token overlap. Adding synonyms
  massively boosts BM25 performance.

Trade-offs:
- Latency: Adds an LLM call before retrieval (~500ms - 1s).
- Precision drop (sometimes): Adding too many tangential keywords can pull
  in irrelevant documents ("topic drift").
"""

import logging
from typing import List

from src.config import config

logger = logging.getLogger("RAGForge.QueryExpansion")

_EXPANSION_SYSTEM_PROMPT = """\
You are an expert search term generator for a RAG system.
Given a user's query, your task is to output a space-separated list of 5-8 highly relevant keywords, synonyms, or related domain jargon.
These words will be appended to the user's query to improve keyword search (BM25) and semantic search recall.

Rules:
- DO NOT answer the question.
- DO NOT use punctuation, commas, or bullet points. Just a single string of space-separated words.
- DO NOT repeat words already in the user's query.
- Output ONLY the generated keywords.
"""


def expand_query(query: str) -> str:
    """
    Expand a query with related terminology.

    Example:
        Input: "How does caching work?"
        Output: "How does caching work? cache invalidation memory performance LRU hit miss"

    Returns the original query + expanded terms. If the LLM call fails,
    returns the original query unchanged.
    """
    if not query or not query.strip():
        return query

    try:
        from src.generator import _get_client
        client = _get_client()

        prompt = (
            f"{_EXPANSION_SYSTEM_PROMPT}\n\n"
            f"User Query: {query.strip()}\n\n"
            f"Keywords:"
        )
        
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
        )
        
        keywords = response.text.strip().replace("\n", " ").replace(",", " ")
        
        # Clean up multiple spaces
        keywords = " ".join(keywords.split())
        
        if not keywords:
            return query
            
        expanded = f"{query.strip()} {keywords}"
        logger.info(f"Query expanded:\n  Original: '{query}'\n  Expanded: '{expanded}'")
        return expanded

    except Exception as e:
        logger.warning(f"Query expansion failed ({e}) — using original query.")
        return query
