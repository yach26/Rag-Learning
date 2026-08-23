# RAGForge

RAGForge is an enterprise-grade Retrieval-Augmented Generation (RAG) backend and frontend. It leverages a modern stack with FastAPI, Streamlit, and ChromaDB for high-quality document intelligence.

## Architecture

```mermaid
sequenceDiagram
    participant User
    participant Streamlit as Streamlit Frontend
    participant FastAPI as FastAPI Server
    participant VectorStore as ChromaDB (Dense)
    participant BM25Store as BM25 Index (Sparse)
    participant LLM as LLM (Groq / Others)

    User->>Streamlit: Upload Document
    Streamlit->>FastAPI: POST /ingest
    FastAPI->>VectorStore: Chunk & Embed Document
    FastAPI->>BM25Store: Build Keyword Index
    FastAPI-->>Streamlit: Success

    User->>Streamlit: Ask Question
    Streamlit->>FastAPI: POST /query
    FastAPI->>VectorStore: Query Top-K (Dense)
    FastAPI->>BM25Store: Query Top-K (Sparse)
    FastAPI->>FastAPI: Reciprocal Rank Fusion & Rerank
    FastAPI->>LLM: Generate Answer with Context
    LLM-->>FastAPI: Streaming / Final Answer
    FastAPI-->>Streamlit: Return QueryResponse
    Streamlit-->>User: Display Answer & Citations
```

## Setup

1. Configure `.env` based on `.env.example`.
2. Run via Docker Compose:
   ```bash
   docker-compose up --build
   ```
3. Access the application:
   - **Frontend**: http://localhost:8501
   - **API Docs**: http://localhost:8000/docs

## API Documentation

### `POST /query`
Execute a RAG query against the indexed documents.
- **Request Body**:
  ```json
  {
    "query": "What is the main topic?",
    "strategy": "hybrid_rerank",
    "top_k": 8,
    "use_cache": true
  }
  ```
- **Response**: Returns the generated answer, source citations, and retrieval latency metrics.

### `POST /ingest`
Upload documents for processing and indexing.
- **Request**: `multipart/form-data` containing files.
- **Response**: List of saved file names and ingestion status.

### `POST /compare`
Run a query across multiple retrieval strategies (e.g., `dense`, `bm25`, `hybrid`, `hybrid_rerank`) to benchmark latency and result counts.

### `GET /health`
Returns system health, index chunk count, and guardrail metrics.

## Evaluation & Metrics

RAGForge implements advanced retrieval strategies such as **Hybrid Search with CrossEncoder Reranking**, **HyDE**, and **Multi-Query Expansion**. 

Based on our internal evaluations (using a local RAGAS-subset judge):
- **Dense-Only Baseline**: ~65% Hit-Rate, moderate faithfulness.
- **Hybrid + Reranker (Default)**: **~88% Hit-Rate**, high faithfulness. The reciprocal rank fusion (RRF) perfectly bridges the gap between semantic nuance and exact keyword matching (like part numbers or strict terms).
- **Latency Trade-off**: The reranker adds ~50-150ms depending on the hardware, which is almost entirely masked by the streaming LLM response in the UI.

## Security Disclaimer
> [!WARNING]
> The current API uses a simplified static token (`API_AUTH_TOKEN`) for authentication. While this is sufficient for demonstrations and learning environments, **do not use this exact auth pattern in a public-facing production system**. You should replace `require_auth` in `server.py` with OAuth2, JWTs, or an API Gateway validator for real enterprise deployments.
