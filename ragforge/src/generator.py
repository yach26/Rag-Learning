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
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_not_exception_type
import groq

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
6. **FORMATTING**: Always structure your answer beautifully using Markdown (bullet points, bold text, headers, and code blocks if applicable) to make it easy to read.

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
6. **FORMATTING**: Always structure your answer beautifully using Markdown (bullet points, bold text, headers, and code blocks if applicable) to make it easy to read.

Context:
{context}

Recent conversation:
{history}

Current question:
{question}

Answer:"""

EVALUATOR_PROMPT = """You are a critical reviewer evaluating a RAG (Retrieval-Augmented Generation) system.
Look at the user's question, the retrieved context, and the drafted answer.
Does the answer fully and accurately address the user's question using ONLY the provided context?

Rules:
- If the drafted answer hallucinates (uses information not in the context), output 'NO'.
- If the drafted answer is completely unrelated to the user's query, output 'NO'.
- If the drafted answer is correct but says "I don't have enough information" and you agree there is NO information, output 'YES' (it correctly admitted failure).
- Output exactly 'YES' or 'NO', followed by a one-sentence justification.

Context:
{context}

Question:
{question}

Drafted Answer:
{draft}

Evaluation (YES/NO):"""


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
    if not config.GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. "
            "Please add it to your .env file.\n"
            "Get a free key at: https://console.groq.com/keys"
        )

_client_instance = None

class GroqGeminiAdapter:
    def __init__(self, api_key):
        import groq
        self.client = groq.Groq(api_key=api_key)
        self.models = self.ModelsAdapter(self.client)
        
    class ModelsAdapter:
        def __init__(self, client):
            self.client = client
            
        def generate_content(self, model, contents, **kwargs):
            response = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": contents}]
            )
            class FakeResponse:
                def __init__(self, text):
                    self.text = text
            return FakeResponse(response.choices[0].message.content)
            
        def generate_content_stream(self, model, contents, **kwargs):
            stream = self.client.chat.completions.create(
                model=config.LLM_MODEL,
                messages=[{"role": "user", "content": contents}],
                stream=True
            )
            class FakeStreamEvent:
                def __init__(self, text):
                    self.text = text
            for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield FakeStreamEvent(content)

def _get_client():
    global _client_instance
    if _client_instance is None:
        _require_api_key()
        _client_instance = GroqGeminiAdapter(api_key=config.GROQ_API_KEY)
    return _client_instance


# ── Generation functions ──────────────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_not_exception_type(groq.RateLimitError),
    before_sleep=lambda retry_state: logger.warning(f"Retrying LLM call in {retry_state.next_action.sleep}s...")
)
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
        logger.info(f"Calling LLM API (model: {config.LLM_MODEL})...")
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        raise RuntimeError(
            f"LLM API call failed: {e}\nCheck your API key and internet connection."
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
        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_not_exception_type(groq.RateLimitError)
        )
        def _get_stream():
            client = _get_client()
            return client.models.generate_content_stream(
                model=config.LLM_MODEL,
                contents=prompt,
            )
            
        try:
            logger.info(f"Calling LLM API (streaming, model: {config.LLM_MODEL})...")
            stream = _get_stream()
            
            for event in stream:
                if getattr(event, "text", None):
                    yield event.text
        except Exception as e:
            # Surface mid-stream failures as visible text rather than
            # crashing the whole UI silently.
            yield f"\n\nResponse cut off — stream error: {e}"

    return _iterate()


def generate_answer_with_correction(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Iterator[str]:
    """
    Self-Correcting RAG:
    1. Generates a draft answer (non-streaming, hidden from user).
    2. Evaluates its own draft.
    3. If YES, yields the draft. If NO, yields a fallback message.
    Yields status updates along the way so the UI isn't completely dead.
    """
    _require_api_key()

    yield "*Drafting initial answer...*\n\n"

    try:
        draft_answer = generate_answer(query, retrieved_chunks, conversation_history)

        yield "*Evaluating answer quality...*\n\n"
        
        # Build evaluator prompt
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            context_parts.append(f"[Source {i}]\n{chunk.get('text', '')}")
        context_text = "\n\n".join(context_parts)
        
        eval_prompt = EVALUATOR_PROMPT.format(
            context=context_text,
            question=query.strip(),
            draft=draft_answer.strip()
        )
        
        client = _get_client()
        response = client.models.generate_content(
            model=config.LLM_MODEL,
            contents=eval_prompt,
        )
        eval_result = response.text.strip().upper()
        
        if eval_result.startswith("YES"):
            yield draft_answer
        else:
            yield (
                "I couldn't generate a confident answer based on the provided context.\n\n"
                f"**Draft:** {draft_answer}\n\n"
                f"**Evaluation:** {eval_result}"
            )

    except Exception as e:
        yield f"\n\nSelf-correction failed: {e}"


if __name__ == "__main__":
    from src.retriever import retrieve, format_results_for_display

    print("=" * 60)
    print("RAGForge — Generation Test")
    print("=" * 60)
    print("(Requires: ingested documents + valid GROQ_API_KEY in .env)\n")

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
