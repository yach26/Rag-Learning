"""
src/guardrails.py — Input and Output Guardrails
=================================================

Basic guardrails to protect the RAG system from prompt injection
and to ensure outputs are safe.

In a production system, these might be handled by a specialized
model (like Llama Guard) or a comprehensive framework (like NeMo Guardrails).
For this benchmark, we use fast local regex to keep latency low.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("RAGForge.Guardrails")

# Common prompt injection patterns
_INJECTION_PATTERNS = [
    r"ignore all previous",
    r"ignore previous",
    r"system prompt",
    r"you are now a",
    r"disregard",
    r"bypass",
    r"forget everything",
]

# Simple toxic/blocked words list (example)
_BLOCKED_WORDS = [
    r"\bidiot\b",
    r"\bstupid\b",
    r"\bdumb\b",
    # Add more as needed for production
]

def check_input(query: str) -> Tuple[bool, str]:
    """
    Checks the user query for prompt injection attacks.
    Returns (is_safe, error_message).
    """
    query_lower = query.lower()
    
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, query_lower):
            logger.warning(f"Input Guardrail Blocked (Injection): '{query}'")
            return False, "Your query triggered a security guardrail. Please ask a direct question about the documents."
            
    return True, ""

def check_output(answer: str) -> Tuple[bool, str]:
    """
    Checks the LLM output for toxic or blocked content.
    Returns (is_safe, error_message).
    """
    answer_lower = answer.lower()
    
    for pattern in _BLOCKED_WORDS:
        if re.search(pattern, answer_lower):
            logger.warning(f"Output Guardrail Blocked (Toxic): {pattern}")
            return False, "The generated response triggered a safety guardrail and was blocked."
            
    return True, ""
