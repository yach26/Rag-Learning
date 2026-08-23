"""
src/generator.py — Grounded answer generation via Groq
=======================================================
"""

import logging
from typing import Any, Dict, Iterator, List, Optional

from src.config import config
from src.llm import get_llm

logger = logging.getLogger("RAGForge.Generator")


PROMPT_TEMPLATE = """You are a helpful assistant that answers questions using ONLY the provided document context.

IMPORTANT RULES:
1. Use ONLY the information in the Context section below.
2. If the answer cannot be found in the provided context, say exactly:
   "I don't have enough information in the provided documents to answer this question."
3. Do NOT invent facts or use your pre-trained knowledge to fill in gaps.
4. Be concise and direct. Quote specific details from the context when helpful.
5. If the context only partially answers the question, share what is available and note what is missing.
6. **FORMATTING**: Always structure your answer beautifully using Markdown (bullet points, bold text, headers, and code blocks if applicable) to make it easy to read.
7. **DIAGRAMS & FLOWCHARTS**: If the user asks for a flowchart, sequence diagram, workflow, steps, process, or architecture, emit a valid ```mermaid code block. Always enclose node label text in double quotes inside brackets, e.g., A["Label text with (parentheses)"] --> B["Another label"]. Never put unquoted parentheses () directly inside brackets [].

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
7. **DIAGRAMS & FLOWCHARTS**: If the user asks for a flowchart, sequence diagram, workflow, steps, process, or architecture, emit a valid ```mermaid code block. Always enclose node label text in double quotes inside brackets, e.g., A["Label text with (parentheses)"] --> B["Another label"]. Never put unquoted parentheses () directly inside brackets [].

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
    recent = history[-(max_turns * 2):]
    lines = []
    for msg in recent:
        role = msg.get("role", "user").capitalize()
        content = msg.get("content", "").strip()
        if content:
            if len(content) > 400:
                content = content[:400] + "…"
            lines.append(f"{role}: {content}")
    return "\n".join(lines)


def build_prompt(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
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

    return PROMPT_TEMPLATE.format(context=context_text, question=query.strip())


def generate_answer(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    prompt = build_prompt(query, retrieved_chunks, conversation_history)
    logger.info("Prompt length: %s characters", len(prompt))
    try:
        return get_llm().complete(prompt)
    except Exception as e:
        raise RuntimeError(
            f"LLM API call failed: {e}\nCheck your API key and internet connection."
        ) from e


def generate_answer_stream(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Iterator[str]:
    prompt = build_prompt(query, retrieved_chunks, conversation_history)
    logger.info("Prompt length: %s characters", len(prompt))

    def _iterate():
        try:
            yield from get_llm().complete_stream(prompt)
        except Exception as e:
            yield f"\n\nResponse cut off — stream error: {e}"

    return _iterate()


def generate_answer_with_correction(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    conversation_history: Optional[List[Dict[str, str]]] = None,
) -> Iterator[str]:
    yield "*Drafting initial answer...*\n\n"

    try:
        draft_answer = generate_answer(query, retrieved_chunks, conversation_history)
        yield "*Evaluating answer quality...*\n\n"

        context_parts = []
        for i, chunk in enumerate(retrieved_chunks, start=1):
            context_parts.append(f"[Source {i}]\n{chunk.get('text', '')}")
        context_text = "\n\n".join(context_parts)

        eval_prompt = EVALUATOR_PROMPT.format(
            context=context_text,
            question=query.strip(),
            draft=draft_answer.strip(),
        )
        eval_result = get_llm().complete(eval_prompt).strip().upper()

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
    from src.retriever import format_results_for_display, retrieve

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
