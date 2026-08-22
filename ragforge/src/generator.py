"""
src/generator.py — LLM Generation Module
==========================================

CHANGES IN THIS REVISION (Phase 2) — CONVERSATION-AWARE GENERATION
---------------------------------------------------------------------
build_prompt(), generate_answer(), and generate_answer_stream() now
accept an optional `conversation_history` parameter (list of
{"role": str, "content": str} dicts from st.session_state.messages).

When history is provided, the last CONVERSATION_HISTORY_TURNS turns
(user+assistant pairs) are injected between the context and the
current question so Gemini can resolve references like "what about
the second one?" or "can you expand on that?" even without query
rewriting.

Design:
- History is formatted as compact "User: … / Assistant: …" text blocks.
- The PROMPT_TEMPLATE with history is only used when history is non-empty
  — otherwise falls back to the original stateless template, so all
  existing tests pass without modification.
- Both streaming and non-streaming paths receive history identically.

Phase 1 items preserved:
- STREAM_RESPONSES flag.
- generate_answer() non-streaming (for CLI / eval scripts).
- generate_answer_stream() streaming (for Streamlit).
- All error handling / API key guards.
"""

import logging
from typing import Dict, Iterator, List, Any, Optional

from src.config import config

logger = logging.getLogger("RAGForge.Generator")


# ── Prompt templates ──────────────────────────────────────────────────────────

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


PROMPT_TEMPLATE_WITH_HISTORY = """You are a helpful assistant that answers questions using ONLY the provided document context.

IMPORTANT RULES:
1. Use ONLY the information in the Context section below.
2. If the answer cannot be found in the provided context, say exactly:
   "I don't have enough information in the provided documents to answer this question."
3. Do NOT invent facts or use your pre-trained knowledge to fill in gaps.
4. Be concise and direct. Quote specific details from the context when helpful.
5. If the context only partially answers the question, share what is available and note what is missing.

Context:
{context}

Recent conversation:
{history}

Current question:
{question}

Answer:"""


def _format_history(
    history: List[Dict[str, str]],
    max_turns: int,
) -> str:
    """Format the last `max_turns` conversation turns as readable text."""
    # Take the last max_turns*2 messages (each turn = 1 user + 1 assistant).
    recent = history[-(max_turns * 2):]
    lines = []
    for msg in recent:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "").strip()
        if content:
            # Trim very long messages to avoid bloating the prompt.
            if len(content) > 400:
                content = content[:400] + "…"
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_prompt(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Build the full prompt string for the LLM.

    Parameters
    ----------
    query : str
        The current (possibly rewritten) user question.
    retrieved_chunks : list
        Chunks returned by retriever.retrieve().
    conversation_history : list, optional
        Full st.session_state.messages list. When provided, the last
        CONVERSATION_HISTORY_TURNS turns are included in the prompt so
        the LLM can resolve follow-up references.
    """
    if not retrieved_chunks:
        context_text = "[No relevant context found in documents]"
    else:
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "?")
            text = chunk.get("text", "")
            context_parts.append(
                f"[Source {i}: {source}, page {page}]\n{text}"
            )
        context_text = "\n\n".join(context_parts)

    if conversation_history:
        history_text = _format_history(
            conversation_history,
            max_turns=config.CONVERSATION_HISTORY_TURNS,
        )
        if history_text:
            return PROMPT_TEMPLATE_WITH_HISTORY.format(
                context=context_text,
                history=history_text,
                question=query.strip(),
            )

    # No history or empty history — use the original stateless template.
    return PROMPT_TEMPLATE.format(context=context_text, question=query.strip())


# ── API helpers ───────────────────────────────────────────────────────────────

def _require_api_key() -> None:
    if not config.LLM_API_KEY:
        raise ValueError(
            "LLM_API_KEY is not set. "
            "Please add it to your .env file.\n"
            "Get a free key at: https://aistudio.google.com/apikey"
        )


_client_instance = None

def _get_client():
    global _client_instance
    if _client_instance is None:
        try:
            from google import genai
        except ImportError:
            raise RuntimeError(
                "google-genai package not installed. Run: pip install google-genai"
            )
        _client_instance = genai.Client(api_key=config.LLM_API_KEY)
    return _client_instance


# ── Generation functions ──────────────────────────────────────────────────────

def generate_answer(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Non-streaming: returns the full answer as a single string."""
    _require_api_key()
    prompt = build_prompt(query, retrieved_chunks, conversation_history)
    logger.info(f"Prompt length: {len(prompt)} characters")

    try:
        client = _get_client()
        logger.info(f"Calling Gemini API (model: {config.LLM_MODEL})...")
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        raise RuntimeError(
            f"Gemini API call failed: {e}\nCheck your API key and internet connection."
        ) from e


def generate_answer_stream(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Iterator[str]:
    """
    Streaming version: yields text chunks as Gemini generates them.
    The Client is created inside the generator to ensure its lifecycle 
    matches the stream iteration exactly, preventing "client closed" errors 
    in Streamlit's threaded environment.
    """
    _require_api_key()
    prompt = build_prompt(query, retrieved_chunks, conversation_history)
    logger.info(f"Prompt length: {len(prompt)} characters")

    def _iterate():
        try:
            # Import locally to avoid issues
            from google import genai
            client = genai.Client(api_key=config.LLM_API_KEY)
            
            logger.info(f"Calling Gemini API (streaming, model: {config.LLM_MODEL})...")
            stream = client.models.generate_content_stream(
                model=config.LLM_MODEL,
                contents=prompt,
            )
            
            for event in stream:
                if getattr(event, "text", None):
                    yield event.text
        except Exception as e:
            # Surface mid-stream failures as visible text rather than
            # crashing the whole UI silently.
            yield f"\n\n⚠️ *Response cut off — stream error: {e}*"

    return _iterate()


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
