"""
server.py — FastAPI service layer for RAGForge
===============================================

Run:
    uvicorn server:app --reload --app-dir ragforge
    # or from ragforge/:
    uvicorn server:app --reload
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.config import config
from src.factory import configure_logging
from src.metrics import metrics

configure_logging()

app = FastAPI(title="RAGForge", version="0.3.0")

_rate_buckets: dict[str, deque] = defaultdict(deque)


def _client_id(authorization: Optional[str], x_forwarded_for: Optional[str]) -> str:
    if authorization:
        return authorization[-12:]
    return x_forwarded_for or "local"


def require_auth(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
) -> None:
    expected = config.API_AUTH_TOKEN
    if not expected:
        return
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
    elif x_api_key:
        token = x_api_key.strip()
    if token != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


def rate_limit(
    authorization: Optional[str] = Header(default=None),
    x_forwarded_for: Optional[str] = Header(default=None),
) -> None:
    limit = config.API_RATE_LIMIT_PER_MIN
    if limit <= 0:
        return
    key = _client_id(authorization, x_forwarded_for)
    now = time.time()
    bucket = _rate_buckets[key]
    while bucket and now - bucket[0] > 60:
        bucket.popleft()
    if len(bucket) >= limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=4000)
    strategy: str = "hybrid_rerank"
    top_k: int = Field(default=8, ge=1, le=25)
    use_cache: bool = True


class QueryResponse(BaseModel):
    answer: str
    sources: List[Dict[str, Any]]
    retrieval_ms: int
    generation_ms: int
    cached: bool
    strategy: str


@app.get("/health")
def health():
    from src.vector_store import get_collection_stats

    stats = get_collection_stats()
    return {"status": "ok", "index": stats, "metrics": metrics.snapshot()}


@app.get("/metrics")
def get_metrics(_: None = Depends(require_auth)):
    return metrics.snapshot()


@app.post("/query", response_model=QueryResponse)
def query(
    body: QueryRequest,
    _: None = Depends(require_auth),
    __: None = Depends(rate_limit),
):
    from src.cache import get_cached_answer, set_cached_answer
    from src.generator import generate_answer
    from src.guardrails import check_input, check_output
    from src.retriever import retrieve_with_timing

    safe, msg = check_input(body.query)
    if not safe:
        raise HTTPException(status_code=400, detail=msg)

    if body.use_cache:
        cached = get_cached_answer(body.query, body.strategy)
        if cached:
            return QueryResponse(
                answer=cached,
                sources=[],
                retrieval_ms=0,
                generation_ms=0,
                cached=True,
                strategy=body.strategy,
            )

    t0 = time.perf_counter()
    chunks, meta = retrieve_with_timing(body.query, top_k=body.top_k, strategy=body.strategy)
    retrieval_ms = meta["total_ms"]
    answer = generate_answer(body.query, chunks)
    generation_ms = round((time.perf_counter() - t0) * 1000) - retrieval_ms

    out_ok, out_msg = check_output(answer)
    if not out_ok:
        raise HTTPException(status_code=400, detail=out_msg)

    if body.use_cache:
        set_cached_answer(body.query, body.strategy, answer)

    sources = [
        {
            "source": c.get("source"),
            "page": c.get("page"),
            "chunk_id": c.get("chunk_id"),
        }
        for c in chunks
    ]
    return QueryResponse(
        answer=answer,
        sources=sources,
        retrieval_ms=retrieval_ms,
        generation_ms=max(generation_ms, 0),
        cached=False,
        strategy=body.strategy,
    )


@app.post("/ingest")
def ingest_files(
    files: List[UploadFile] = File(...),
    _: None = Depends(require_auth),
    __: None = Depends(rate_limit),
):
    from src.ingest import run_ingestion_pipeline
    from src.validation import ValidationError, write_validated_upload

    saved = []
    try:
        for uf in files:
            data = uf.file.read()
            path = write_validated_upload(config.DOCUMENTS_DIR, uf.filename or "upload.bin", data)
            saved.append(path.name)
        run_ingestion_pipeline()
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"saved": saved, "status": "ingested"}


class CompareRequest(BaseModel):
    query: str
    strategies: List[str] = Field(
        default_factory=lambda: ["dense", "bm25", "hybrid", "hybrid_rerank"]
    )
    top_k: int = 5


@app.post("/compare")
def compare_strategies(
    body: CompareRequest,
    _: None = Depends(require_auth),
    __: None = Depends(rate_limit),
):
    from src.retriever import retrieve_with_timing

    rows = []
    for strategy in body.strategies:
        t0 = time.perf_counter()
        try:
            chunks, meta = retrieve_with_timing(body.query, top_k=body.top_k, strategy=strategy)
            rows.append({
                "strategy": strategy,
                "latency_ms": meta["total_ms"],
                "num_results": len(chunks),
                "top_source": chunks[0].get("source") if chunks else None,
                "error": None,
            })
        except Exception as e:
            rows.append({
                "strategy": strategy,
                "latency_ms": round((time.perf_counter() - t0) * 1000),
                "num_results": 0,
                "top_source": None,
                "error": str(e),
            })
    return {"query": body.query, "results": rows}
