"""
src/query/multi_query.py — Multi-Query Generation
===================================================

Generates alternative phrasing for a single user query to overcome
vocabulary mismatch and improve recall.

If a user asks "What causes database performance problems?", this
module generates 3-5 variations (e.g. "What causes slow queries?").
The retriever will run a search for EACH variation, merge all results,
deduplicate, and then rerank them.
"""

import logging
from typing import List

from src.config import config

logger = logging.getLogger("RAGForge.MultiQuery")

_MULTI_QUERY_PROMPT = """\
You are an AI language model assistant for a search system.
Your task is to generate 3 alternative versions of the given user query.
The goal is to provide different phrasings and related keywords to improve document retrieval.

Rules:
- Generate exactly 3 alternative queries.
- Do not number them. Just provide one query per line.
- Keep them concise and focused on the same core intent.
- Do not add any introductory or concluding text.
"""


def generate_queries(original_query: str) -> List[str]:
    """
    Generate 3 alternative queries using the LLM.
    Returns a list containing the original query + 3 alternatives.
    If the LLM call fails, returns just [original_query].
    """
    if not original_query or not original_query.strip():
        return [original_query]

    queries = [original_query.strip()]

    try:
        from src.llm import get_llm

        prompt = f"{_MULTI_QUERY_PROMPT}\n\nOriginal Query: {original_query.strip()}\n"
        text = get_llm().complete(prompt).strip()
        
        # Parse output into lines, ignoring empty ones
        for line in text.split("\n"):
            cleaned = line.strip()
            # Strip markdown bullets or numbers if the LLM hallucinated them despite instructions
            if cleaned.startswith("- "):
                cleaned = cleaned[2:]
            elif len(cleaned) > 2 and cleaned[0].isdigit() and cleaned[1] in (".", ")"):
                cleaned = cleaned[2:].strip()
                
            if cleaned and cleaned not in queries:
                queries.append(cleaned)
                
        # Limit to 4 queries total (1 original + 3 alternatives)
        queries = queries[:4]
        
        logger.info(f"Multi-query generated {len(queries)-1} alternatives for: '{original_query}'")
        for i, q in enumerate(queries[1:], 1):
            logger.debug(f"  Alt {i}: {q}")
            
        return queries

    except Exception as e:
        logger.warning(f"Multi-query generation failed ({e}) — using original query only.")
        return queries
