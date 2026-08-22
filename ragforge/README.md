# RAGForge — Advanced RAG System (Phase 2)

A **learning-first** Retrieval-Augmented Generation (RAG) system built from scratch — no LangChain, no LlamaIndex, no magic wrappers. Just Python.

---

## What's New in Phase 2?

Phase 2 introduces production-grade RAG techniques to fix common failures in basic RAG systems:
1. **Hybrid Search (Vector + BM25)**: Combines semantic search with exact keyword matching via Reciprocal Rank Fusion (RRF).
2. **CrossEncoder Reranking**: Re-scores hybrid candidates for a massive accuracy jump (moves the most relevant chunks to position #1).
3. **Conversation-Aware Retrieval**: Uses Gemini to rewrite follow-up questions ("what about the second one?") into standalone queries.
4. **Semantic Chunking**: Splits text recursively at natural boundaries (paragraphs → sentences → words) instead of arbitrary characters.
5. **Incremental Ingestion**: Hashes files to skip unchanged documents, making re-ingestion nearly instant.
6. **OCR Fallback**: Routes scanned/image-only PDF pages through `pytesseract` automatically.
7. **Local Query Normalisation**: Uses `pyspellchecker` to fix typos before embedding, preventing query drift.

---

## What is RAG?

**RAG = Retrieval-Augmented Generation**

Large Language Models (LLMs) like ChatGPT are trained on internet data up to a certain date. They don't know about *your* documents. If you ask them "What does our internal policy say about vacation days?", they'll either refuse or make something up.

RAG solves this by:

1. **Indexing** your documents (once, offline)
2. **Retrieving** the most relevant chunks when a question is asked
3. **Generating** an answer using *only* those chunks as context

The LLM becomes a reasoning engine over *your* data, not a hallucination machine.

---

## Architecture

```
                    ┌──────────────┐
                    │   Documents  │  PDF, TXT, Markdown
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   Ingestion  │  Hash check + Extract text + OCR fallback
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   Chunking   │  Recursive Semantic Splitting (Paragraph/Sentence)
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │  Embeddings  │  all-MiniLM-L6-v2 → 384-dim vectors
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   ChromaDB   │  Local persistent vector store
                    └──────────────┘

        ──────── QUERY TIME ────────

             User Question
                   ↓
           Query Rewriting & Spellcheck
                   ↓
       ┌───────────┴───────────┐
       ↓                       ↓
 Vector Search           BM25 Keyword Search
 (ChromaDB)              (In-Memory Index)
       ↓                       ↓
       └───────────┬───────────┘
                   ↓
         Reciprocal Rank Fusion
                   ↓
         CrossEncoder Reranking
                   ↓
           Prompt + Context
                   ↓
            Gemini LLM
                   ↓
         Answer + Sources (Streamed)
```

---

## Project Structure

```
ragforge/
│
├── data/
│   └── documents/          ← Put your PDF/TXT/MD files here
│   └── .file_hashes.json   ← Auto-generated: MD5 hashes for incremental ingest
│
├── chroma_db/              ← Auto-generated: ChromaDB vector store
│
├── eval/
│   ├── qa_pairs.json       ← Ground-truth questions for testing
│   └── run_eval.py         ← Measures retrieval hit_rate@k
│
├── src/
│   ├── __init__.py
│   ├── config.py           ← All settings (API keys, models, thresholds)
│   ├── ingest.py           ← Document loading + OCR + hash-skip
│   ├── chunker.py          ← Semantic boundary text splitting
│   ├── embedder.py         ← sentence-transformers embedding
│   ├── vector_store.py     ← ChromaDB read/write/delete
│   ├── bm25_store.py       ← BM25 keyword index builder
│   ├── retriever.py        ← Hybrid Search + RRF + Reranker pipeline
│   ├── reranker.py         ← CrossEncoder rescoring
│   ├── query_rewriter.py   ← Conversational context + spellchecker
│   └── generator.py        ← Chunks + LLM → answer stream
│
├── app.py                  ← Streamlit UI
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Installation

### Prerequisites
- Python 3.11+
- `pip`
- (Optional) **Tesseract OCR** for scanned PDFs:
  - Windows: `winget install UB-Mannheim.TesseractOCR`
  - macOS: `brew install tesseract`
  - Linux: `sudo apt install tesseract-ocr`

### Setup

```bash
# Clone or navigate to the project
cd ragforge

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# Install dependencies (Phase 2 added rank-bm25, pytesseract, Pillow, pyspellchecker)
pip install -r requirements.txt

# Create your .env file
copy .env.example .env         # Windows
# cp .env.example .env         # Mac/Linux
```

---

## Environment Variables

Edit your `.env` file:

```env
# Get a free key at: https://aistudio.google.com/apikey
LLM_API_KEY=your_google_gemini_api_key_here
LLM_MODEL=gemini-3.6-flash
```

**Never commit `.env` to git** — it's already in `.gitignore`.

---

## How to Add Documents & Ingest

Place your files in `data/documents/`:

```bash
python -m src.ingest
```

**Incremental Ingestion:** You can run this as often as you want. RAGForge hashes the files, skips unchanged ones, purges stale chunks for modified files, and re-embeds only what's new.

---

## How to Start the UI

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`

The UI shows:
- Conversational chat interface (ask follow-up questions normally)
- Streaming text generation
- **Sources** — which documents and pages the answer came from
- **Retrieved Context** — the exact chunks given to the LLM (expand to inspect distance and reranker scores)

---

## Retrieval Evaluation

Phase 2 includes an evaluation harness to measure retrieval quality before you deploy changes.

1. Add your real questions to `eval/qa_pairs.json`.
2. Run the evaluator:
```bash
python eval/run_eval.py --top-k 4
```

This tests the Hybrid + Reranking pipeline against your ground-truth without spending money on LLM calls.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No supported documents found` | Add PDF/TXT/MD files to `data/documents/` |
| `Vector store is empty` | Run `python -m src.ingest` first |
| `LLM_API_KEY is not set` | Add your key to `.env` |
| OCR isn't working | Ensure Tesseract is installed on your OS |
| Initial search is slow | First run downloads embedding and reranking models (~160MB total) |
| Client has been closed error | Fixed in Phase 2 via generator client creation |
