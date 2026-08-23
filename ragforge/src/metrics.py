"""
src/metrics.py — Process-level counters and cost estimates
===========================================================
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Dict

logger = logging.getLogger("RAGForge.Metrics")

# Groq list prices (USD per 1M tokens) for openai/gpt-oss-20b as of 2026.
# Override via config if you swap models.
DEFAULT_INPUT_USD_PER_M = 0.075
DEFAULT_OUTPUT_USD_PER_M = 0.30


@dataclass
class Metrics:
    llm_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    retrievals: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    guardrail_blocks: int = 0
    started_at: float = field(default_factory=time.time)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_llm_call(self, model: str, prompt_tokens: int, completion_tokens: int) -> None:
        with self._lock:
            self.llm_calls += 1
            self.prompt_tokens += prompt_tokens
            self.completion_tokens += completion_tokens
        logger.info(
            "llm_call model=%s prompt_tokens=%s completion_tokens=%s",
            model,
            prompt_tokens,
            completion_tokens,
        )

    def record_retrieval(self) -> None:
        with self._lock:
            self.retrievals += 1

    def record_cache(self, hit: bool) -> None:
        with self._lock:
            if hit:
                self.cache_hits += 1
            else:
                self.cache_misses += 1

    def record_guardrail_block(self) -> None:
        with self._lock:
            self.guardrail_blocks += 1

    def estimated_cost_usd(
        self,
        input_per_m: float = DEFAULT_INPUT_USD_PER_M,
        output_per_m: float = DEFAULT_OUTPUT_USD_PER_M,
    ) -> float:
        return (
            (self.prompt_tokens / 1_000_000.0) * input_per_m
            + (self.completion_tokens / 1_000_000.0) * output_per_m
        )

    def snapshot(self) -> Dict[str, float | int]:
        with self._lock:
            return {
                "llm_calls": self.llm_calls,
                "prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "estimated_cost_usd": round(self.estimated_cost_usd(), 6),
                "retrievals": self.retrievals,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "guardrail_blocks": self.guardrail_blocks,
                "uptime_s": round(time.time() - self.started_at, 1),
            }

    def reset(self) -> None:
        with self._lock:
            self.llm_calls = 0
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.retrievals = 0
            self.cache_hits = 0
            self.cache_misses = 0
            self.guardrail_blocks = 0
            self.started_at = time.time()


metrics = Metrics()
