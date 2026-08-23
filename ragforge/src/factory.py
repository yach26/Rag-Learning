"""
src/factory.py — Lightweight service factory
=============================================

Avoids hidden globals in tests: call reset_runtime() between cases
and construct GroqLLM / Config independently when injecting mocks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from src.config import Config, config
from src.llm import GroqLLM, get_llm, reset_llm

logger = logging.getLogger("RAGForge")


@dataclass
class AppServices:
    config: Config
    llm: GroqLLM


def configure_logging(level: str | None = None) -> None:
    resolved = (level or config.LOG_LEVEL).upper()
    logging.basicConfig(
        level=getattr(logging, resolved, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        force=False,
    )


def create_services(cfg: Config | None = None, llm: GroqLLM | None = None) -> AppServices:
    cfg = cfg or config
    if llm is None:
        llm = get_llm()
    return AppServices(config=cfg, llm=llm)


def reset_runtime() -> None:
    """Clear LLM singleton and BM25/cache module state for tests."""
    reset_llm()
    from src.bm25_store import invalidate_index
    from src.vector_store import reset_client

    invalidate_index()
    reset_client()
