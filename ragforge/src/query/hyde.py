"""
src/query/hyde.py — Hypothetical Document Embeddings
======================================================

HyDE (Hypothetical Document Embeddings) transforms a query space into
a document space before retrieval.

Instead of embedding the question (e.g. "What is caching?"), we use an
LLM to generate a fake, hypothetical answer ("Caching is a mechanism...").
Even if the LLM hallucinates facts, the *vocabulary* and *structure* of
the fake document will closely match the real documents in the vector store.

We embed the fake document, retrieve the nearest real documents, and
then rerank them against the ORIGINAL query.

Strengths: Massive boost in dense retrieval recall, completely bypasses
the "question-to-answer" semantic gap in vector spaces.
Weaknesses: Very high latency (requires a long LLM generation before retrieval).
"""

import logging

from src.config import config

logger = logging.getLogger("RAGForge.HyDE")

_HYDE_PROMPT = """\
Please write a short, concise paragraph answering the following question. 
It is okay if you do not know the exact facts — generate a plausible, hypothetical answer 
using the vocabulary and structure that a real document on this topic would use.

Question: {query}

Hypothetical Answer:"""


def generate_hypothetical_document(query: str) -> str:
    """
    Generate a hypothetical document answering the query.
    If the LLM call fails, returns the original query.
    """
    if not query or not query.strip():
        return query

    try:
        from src.generator import _get_client
        client = _get_client()

        prompt = _HYDE_PROMPT.format(query=query.strip())

        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
        )

        fake_doc = response.text.strip()
        
        if not fake_doc:
            return query
            
        logger.info(f"HyDE generated fake document (len={len(fake_doc)}) for: '{query}'")
        logger.debug(f"Fake doc preview: {fake_doc[:100]}...")
            
        return fake_doc

    except Exception as e:
        logger.warning(f"HyDE generation failed ({e}) — using original query.")
        return query
