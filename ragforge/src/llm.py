"""
src/llm.py — Native Groq chat client
======================================

Replaces the Gemini-shaped adapter. Callers use complete() / complete_stream()
against Groq's OpenAI-compatible chat API.

Default model is Groq's documented chat ID `openai/gpt-oss-20b`
(override with LLM_MODEL in .env).
"""

from __future__ import annotations

import logging
from typing import Iterator, Optional

import groq
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential

from src.config import config
from src.metrics import metrics

logger = logging.getLogger("RAGForge.LLM")

_llm_instance: Optional["GroqLLM"] = None


class GroqLLM:
    """Thin wrapper around groq.Groq with usage tracking."""

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. Add it to your .env file.\n"
                "Get a free key at: https://console.groq.com/keys"
            )
        self.model = model
        self.client = groq.Groq(api_key=api_key)

    def _record_usage(self, response) -> None:
        usage = getattr(response, "usage", None)
        if usage is None:
            return
        prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
        completion = int(getattr(usage, "completion_tokens", 0) or 0)
        metrics.record_llm_call(self.model, prompt, completion)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_not_exception_type(groq.RateLimitError),
        before_sleep=lambda retry_state: logger.warning(
            "Retrying Groq call in %ss...", retry_state.next_action.sleep
        ),
    )
    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
    ) -> str:
        kwargs = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        logger.info("Groq complete() model=%s prompt_chars=%s", self.model, len(prompt))
        response = self.client.chat.completions.create(**kwargs)
        self._record_usage(response)
        content = response.choices[0].message.content
        return content or ""

    def complete_stream(
        self,
        prompt: str,
        *,
        temperature: float = 0.1,
    ) -> Iterator[str]:
        logger.info("Groq stream() model=%s prompt_chars=%s", self.model, len(prompt))
        stream = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            stream=True,
            stream_options={"include_usage": True},
        )
        for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage:
                prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                if prompt_tokens > 0 or completion_tokens > 0:
                    metrics.record_llm_call(self.model, prompt_tokens, completion_tokens)
            
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    yield content


def get_llm() -> GroqLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = GroqLLM(api_key=config.GROQ_API_KEY, model=config.LLM_MODEL)
    return _llm_instance


def reset_llm() -> None:
    global _llm_instance
    _llm_instance = None
