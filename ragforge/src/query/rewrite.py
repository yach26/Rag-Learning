"""
src/query_rewriter.py — Conversation-Aware Query Rewriting
============================================================

Converts ambiguous follow-up questions into standalone, self-contained
queries before retrieval. Without this, stateless vector search has no
chance of answering questions like:

    "What about the second one?"
    "Can you elaborate on that?"
    "How does it compare to what you said before?"

Strategy:
- Fast, cheap Gemini call (same model, short prompt, non-streaming).
- Heuristic fast-path: if the query looks fully self-contained (long
  enough, no obvious references), skip the API call entirely.
- Complete fail-safe: any exception returns the original query
  unchanged — retrieval never crashes because of a rewrite failure.
"""

import logging
import re
from typing import Dict, List

from src.config import config

logger = logging.getLogger("RAGForge.QueryRewriter")

# Pronouns / references that suggest a follow-up needing context.
_REFERENCE_PATTERN = re.compile(
    r"\b(it|its|that|this|those|these|they|them|their|"
    r"he|she|his|her|the (first|second|third|last|previous|above|"
    r"mentioned|same|other)|what about|tell me more|elaborate|"
    r"explain|how so|why so|and (also|what)|compared to (that|it))\b",
    re.IGNORECASE,
)

_REWRITE_SYSTEM_PROMPT = """\
You are a query rewriter for a document retrieval system.
Given a conversation history and a follow-up question, rewrite the
follow-up into a single, fully self-contained question that can be
understood without the conversation context.

Rules:
- Output ONLY the rewritten question — no explanation, no preamble.
- Keep it concise (one sentence if possible).
- Preserve all specific terms, names, and numbers from the original.
- If the question is already self-contained, return it exactly as-is.
"""


def _format_history(history: List[Dict]) -> str:
    """Format last N turns as a compact string for the rewrite prompt."""
    lines = []
    for msg in history:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _looks_like_followup(query: str) -> bool:
    """
    Cheap heuristic: does this query contain reference words that
    suggest it depends on prior context? Very short queries also get
    rewritten because they're almost certainly follow-ups.
    """
    stripped = query.strip()
    if len(stripped.split()) <= 3:
        return True
    return bool(_REFERENCE_PATTERN.search(stripped))


def rewrite_query(
    user_query: str,
    history: List[Dict],
    max_turns: int = 3,
) -> str:
    """
    Rewrite a potentially ambiguous follow-up question into a standalone
    query using the last `max_turns` conversation turns as context.

    Parameters
    ----------
    user_query : str
        The raw question the user just typed.
    history : list of {"role": str, "content": str}
        Full conversation history (st.session_state.messages or similar).
        Only the last `max_turns * 2` entries are used.
    max_turns : int
        How many prior turns (user+assistant pairs) to include.

    Returns
    -------
    str
        The rewritten (or original) query — always a non-empty string.
    """
    if not user_query or not user_query.strip():
        return user_query

    # Fast-path: no history or query looks self-contained — skip API call.
    recent_history = history[-(max_turns * 2):] if history else []
    if not recent_history or not _looks_like_followup(user_query):
        logger.debug("Query rewrite skipped (self-contained or no history).")
        return user_query

    try:
        from src.generator import _get_client

        client = _get_client()
        history_text = _format_history(recent_history)
        prompt = (
            f"{_REWRITE_SYSTEM_PROMPT}\n\n"
            f"Conversation so far:\n{history_text}\n\n"
            f"Follow-up question: {user_query.strip()}\n\n"
            f"Rewritten standalone question:"
        )
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
        )
        rewritten = response.text.strip()

        # Sanity check: rewrite must not be empty
        if not rewritten:
            logger.warning("Rewriter returned empty string — using original.")
            return user_query

        logger.info(f"Query rewritten: '{user_query}' → '{rewritten}'")
        return rewritten

    except Exception as e:
        # Never crash retrieval because of a rewrite failure.
        logger.warning(f"Query rewrite failed ({e}) — using original query.")
        return user_query


def normalize_query(raw_query: str) -> str:
    """
    Local spellcheck to fix typos before embedding.
    Small embedding models (like all-MiniLM-L6-v2) fail on misspelled queries.
    This fixes word-level typos instantly and for free while protecting acronyms.
    """
    try:
        from spellchecker import SpellChecker
        spell = SpellChecker()
        
        # Add common tech, networking, and CS terms to prevent query corruption
        tech_words = [
            'cyber', 'cybersecurity', 'rag', 'llm', 'api', 'json', 
            'yaml', 'python', 'github', 'openai', 'gemini', 'groq',
            'app', 'repo', 'dev', 'ops', 'devops', 'sql', 'nosql',
            'osi', 'tcp', 'ip', 'http', 'https', 'dns', 'udp', 'mac',
            'lan', 'wan', 'icmp', 'smtp', 'ftp', 'ssh', 'ssl', 'tls'
        ]
        spell.word_frequency.load_words(tech_words)
        
        words = re.findall(r"\b\w+\b", raw_query)
        # Exclude uppercase acronyms (e.g. OSI, TCP, RAG) and tech words from spellcheck
        words_to_check = [
            w for w in words 
            if not (w.isupper() and 2 <= len(w) <= 5) and w.lower() not in tech_words
        ]
        
        misspelled = spell.unknown(words_to_check)
        
        if not misspelled:
            return raw_query
            
        cleaned_query = raw_query
        for word in misspelled:
            correction = spell.correction(word)
            if correction and correction.lower() != word.lower():
                pattern = re.compile(r"\b" + re.escape(word) + r"\b")
                cleaned_query = pattern.sub(correction, cleaned_query)
                
        if cleaned_query != raw_query:
            logger.info(f"Spellcheck fixed typos: '{raw_query}' → '{cleaned_query}'")
            
        return cleaned_query
        
    except ImportError:
        logger.warning("pyspellchecker not installed. Skipping spellcheck.")
        return raw_query
    except Exception as e:
        logger.warning(f"Spellcheck failed ({e}) — using original query.")
        return raw_query
