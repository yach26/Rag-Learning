"""
src/generator.py — LLM Generation Module
==========================================

WHAT PROBLEM DOES THIS SOLVE?
------------------------------
We have retrieved the most relevant chunks from our documents. Now we need to:
1. Combine those chunks into a single "context" text block
2. Build a prompt that instructs the LLM on how to use that context
3. Call the LLM API and get back a generated answer

This is the "G" in RAG — Generation.

WHY DO WE NEED A PROMPT TEMPLATE?
-----------------------------------
Without careful prompting, LLMs will:
- Answer from their training data (ignoring our documents)
- Hallucinate facts that sound plausible but aren't in the context
- Mix document information with pre-trained knowledge

Our prompt explicitly tells the model:
  "Use ONLY the provided context. If you don't know, say so."

This is called "grounding" — anchoring the model's output to a specific source.

WHY GOOGLE GEMINI?
------------------
- gemini-2.0-flash is fast and has a generous free tier
- No credit card required for the free tier
- Simple REST API via the google-generativeai Python SDK
- Handles long contexts well (important for RAG with multiple chunks)

WHAT THE LLM ACTUALLY RECEIVES:
---------------------------------
It receives a single string (the prompt) like this:

    You are a helpful assistant...
    Use ONLY the provided context...

    Context:
    [Chunk 1 text]

    [Chunk 2 text]

    [Chunk 3 text]

    Question:
    What is the main topic?

The LLM reads this entire string and generates a completion.
It doesn't "see" our vector database — it only sees plain text.

INTERNAL FLOW:
--------------
generate_answer(query, retrieved_chunks)
    ↓
build_prompt(query, chunks)          ← constructs the full prompt string
    ↓
call_gemini_api(prompt)             ← sends to Google's API
    ↓
answer: str                          ← the LLM's response
"""

import logging
from typing import List, Dict, Any

from src.config import config

logger = logging.getLogger("RAGForge.Generator")


# ── Prompt Template ───────────────────────────────────────────────────────────
# This is the instruction we give the LLM. Every answer is grounded here.
# The {context} and {question} placeholders are filled in at runtime.

PROMPT_TEMPLATE = """You are a helpful assistant that answers questions using ONLY the provided document context.

IMPORTANT RULES:
1. Use ONLY the information in the Context section below.
2. If the answer cannot be found in the provided context, say exactly:
   "I don't have enough information in the provided documents to answer this question."
3. Do NOT invent facts or use your pre-trained knowledge to fill in gaps.
4. Be concise and direct. Quote specific details from the context when helpful.
5. If the context only partially answers the question, share what is available and note what is missing.

Context:
{context}

Question:
{question}

Answer:"""


def build_prompt(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    Assemble the final prompt by combining retrieved chunks and the user query.

    Each chunk is labelled with its source and page number so the LLM can
    reference them in its answer if needed.

    Args:
        query:            The user's question.
        retrieved_chunks: List of result dicts from retriever.retrieve().

    Returns:
        A single prompt string ready to send to the LLM.
    """
    if not retrieved_chunks:
        # No context available — the LLM will answer from nothing
        context_text = "[No relevant context found in documents]"
    else:
        # Format each chunk as a labeled section
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            text = chunk.get("text", "")
            context_parts.append(
                f"[Source {i}: {source}, page {page}]\n{text}"
            )
        context_text = "\n\n".join(context_parts)

    prompt = PROMPT_TEMPLATE.format(
        context=context_text,
        question=query.strip(),
    )
    return prompt


def generate_answer(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
) -> str:
    """
    Generate an answer to the user's query using the retrieved document context.

    This ties together prompt construction and LLM API calls.

    Args:
        query:            The user's original question.
        retrieved_chunks: Top-k chunks from retriever.retrieve().

    Returns:
        The LLM's answer as a string.

    Raises:
        ValueError: If the API key is not configured.
        RuntimeError: If the LLM API call fails.
    """
    # ── Validate API key ──────────────────────────────────────────────────────
    if not config.LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY is not set. "
            "Please add it to your .env file.\n"
            "Get a free key at: https://aistudio.google.com/apikey"
        )

    # ── Build the prompt ──────────────────────────────────────────────────────
    prompt = build_prompt(query, retrieved_chunks)
    logger.info(f"Prompt length: {len(prompt)} characters")

    # ── Call Google Gemini API ────────────────────────────────────────────────
    return _call_gemini(prompt)


def _call_gemini(prompt: str) -> str:
    """
    Send a prompt to the Google Gemini API and return the response text.

    Uses the new google-genai SDK (google.genai).
    The model is configured via:
        config.LLM_MODEL  (default: "gemini-2.5-flash")
        config.LLM_API_KEY

    Args:
        prompt: The fully assembled prompt string.

    Returns:
        The model's response text.

    Raises:
        RuntimeError: If the API returns an error.
    """
    try:
        from google import genai
    except ImportError:
        raise RuntimeError(
            "google-genai package not installed. "
            "Run: pip install google-genai"
        )

    try:
        # Create a client with our API key
        client = genai.Client(api_key=config.LLM_API_KEY)

        logger.info(f"Calling Gemini API (model: {config.LLM_MODEL})...")

        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
        )

        answer = response.text
        logger.info("Gemini API response received.")
        return answer

    except Exception as e:
        raise RuntimeError(
            f"Gemini API call failed: {e}\n"
            "Check your API key and internet connection."
        ) from e


# ── CLI Entry Point ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    from src.retriever import retrieve, format_results_for_display

    print("=" * 60)
    print("RAGForge — Generation Test")
    print("=" * 60)
    print("(Requires: ingested documents + valid LLM_API_KEY in .env)\n")

    query = input("Enter your question: ").strip()
    if not query:
        print("No query entered. Exiting.")
        exit()

    print("\n[1/2] Retrieving relevant chunks...")
    try:
        chunks = retrieve(query)
        print(format_results_for_display(chunks))
    except RuntimeError as e:
        print(f"ERROR: {e}")
        exit()

    print("\n[2/2] Generating answer...")
    try:
        answer = generate_answer(query, chunks)
        print("\n" + "=" * 60)
        print("ANSWER:")
        print("=" * 60)
        print(answer)
    except (ValueError, RuntimeError) as e:
        print(f"ERROR: {e}")
