# RAGForge — Beginner RAG System (Phase 1)

A **learning-first** Retrieval-Augmented Generation (RAG) system built from scratch — no LangChain, no LlamaIndex, no magic wrappers. Just Python.

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
                    │   Ingestion  │  Extract text, clean, detect format
                    └──────┬───────┘
                           ↓
                    ┌──────────────┐
                    │   Chunking   │  Split into ~500-token pieces with overlap
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
           Query Embedding
                   ↓
           Vector Search (ChromaDB)
                   ↓
           Top-K Similar Chunks
                   ↓
           Prompt + Context
                   ↓
           Gemini LLM
                   ↓
           Answer + Sources
```

---

## Project Structure

```
ragforge/
│
├── data/
│   └── documents/          ← Put your PDF/TXT/MD files here
│
├── chroma_db/              ← Auto-generated: ChromaDB vector store
│
├── src/
│   ├── __init__.py         ← Makes src a Python package
│   ├── config.py           ← All settings in one place
│   ├── ingest.py           ← Document loading (PDF/TXT/MD)
│   ├── chunker.py          ← Text splitting with overlap
│   ├── embedder.py         ← sentence-transformers embedding
│   ├── vector_store.py     ← ChromaDB read/write
│   ├── retriever.py        ← Query → relevant chunks
│   └── generator.py        ← Chunks + LLM → answer
│
├── app.py                  ← Streamlit UI
├── test_ingest.py          ← Tests for ingestion
├── test_chunker.py         ← Tests for chunking
├── test_retriever.py       ← Tests for retrieval
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## How Each Component Works

### 1. Ingestion (`src/ingest.py`)

**Problem:** Documents come in different formats. PDFs need PyMuPDF, text files need `open()`, Markdown is just text.

**What it does:**
- Scans `data/documents/` for PDF, TXT, and Markdown files
- Extracts text using format-appropriate methods
- Cleans excess whitespace
- Preserves metadata: `{"source": "paper.pdf", "page": 3}`

**PDFs preserve page numbers** so you can cite them precisely.

---

### 2. Chunking (`src/chunker.py`)

**Problem:** You can't embed a 200-page PDF as one vector — it would average out all meaning. Embedding models also have token limits (~512 tokens for our model).

**What it does:**
- Splits documents into overlapping chunks using a sliding window
- Default: ~2000 characters per chunk (≈500 tokens), 200 char overlap

**Characters vs Words vs Tokens:**
| Unit | "Hello World" | Notes |
|------|--------------|-------|
| Characters | 11 | Simplest, language-agnostic |
| Words | 2 | Better approximation, but varies |
| Tokens | 2 | What LLMs actually count, requires a tokenizer |

We use characters in Phase 1 for simplicity. Rule of thumb: **1 token ≈ 4 characters**.

**Why overlap?** If a sentence falls exactly on a chunk boundary, overlap ensures it appears complete in at least one chunk.

---

### 3. Embeddings (`src/embedder.py`)

**Problem:** Computers can't compare text directly. We need a mathematical representation that captures *meaning*.

**What embeddings are:**
- A list of 384 numbers (a "vector") representing the semantic meaning of a text
- Texts with similar meanings have vectors that "point in similar directions"
- "Machine learning" and "AI algorithms" will have more similar vectors than "Machine learning" and "chocolate cake"

**Model:** `sentence-transformers/all-MiniLM-L6-v2`
- ~80 MB, runs on CPU, no GPU required
- 384-dimensional output vectors
- Trained on massive text corpora to capture meaning

**How similarity search works:**
```
cosine_similarity(A, B) = dot(A, B) / (|A| × |B|)

1.0  = identical meaning
0.5  = somewhat related  
0.0  = unrelated
```

The model is loaded **once** and reused for all queries (lazy singleton pattern).

---

### 4. ChromaDB (`src/vector_store.py`)

**Problem:** We need to store thousands of vectors and search them fast.

**What ChromaDB does:**
- Stores vectors + text + metadata in a local database (`./chroma_db/`)
- Uses ANN (Approximate Nearest Neighbour) indexing for fast similarity search
- Runs entirely locally — no Docker, no cloud, no account needed
- Persists data between program restarts

Think of it like SQLite, but for vectors.

**Deduplication:** We use deterministic chunk IDs (`paper.pdf__chunk_0007`) so re-running ingestion updates existing chunks rather than duplicating them.

---

### 5. Retrieval (`src/retriever.py`)

**Problem:** Given a user question, find the most relevant document chunks.

**Flow:**
```
User question (string)
        ↓
embed_query()     ← converts question to 384-dim vector
        ↓
ChromaDB query    ← finds chunks with similar vectors
        ↓
Top-5 chunks      ← sorted by cosine distance (lower = more relevant)
```

**Critical:** The query MUST be embedded with the **same model** used during ingestion. Mixing models makes similarity scores meaningless.

---

### 6. Generation (`src/generator.py`)

**Problem:** We have relevant chunks — now we need to generate a natural language answer.

**What it does:**
- Assembles a prompt with retrieved chunks as context
- Sends the prompt to Google Gemini
- Returns the grounded answer

**The RAG Prompt:**
```
You are a helpful assistant...
Use ONLY the provided context...

Context:
[Source 1: paper.pdf, page 3]
Chunk text here...

[Source 2: notes.md, page 1]  
More chunk text...

Question:
What is the main finding?

Answer:
```

The explicit grounding instruction prevents the LLM from using its pre-trained knowledge instead of your documents.

---

## Installation

### Prerequisites
- Python 3.11+
- `pip`

### Setup

```bash
# Clone or navigate to the project
cd ragforge

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# Install dependencies
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
LLM_MODEL=gemini-2.0-flash
```

**Never commit `.env` to git** — it's already in `.gitignore`.

---

## How to Add Documents

Place your files in `data/documents/`:

```
data/
└── documents/
    ├── research_paper.pdf
    ├── meeting_notes.txt
    └── project_spec.md
```

Supported formats: **PDF**, **TXT**, **Markdown (.md)**

---

## How to Run Ingestion

```bash
cd ragforge
python -m src.ingest
```

Expected output:
```
============================================================
RAGForge — Full Ingestion Pipeline
============================================================

[Step 1/4] Loading documents...
Found 3 document(s) in 'data/documents'

[1/3] Processing: research_paper.pdf
  [PDF] Extracting: research_paper.pdf
  [PDF] Found 12 page(s)
  [PDF] Extracted 11 non-empty page(s)
...
  → Loaded 13 page(s)/document(s)

[Step 2/4] Chunking documents...
  → Created 52 chunk(s)

[Step 3/4] Generating embeddings...
  → Generated 52 embedding vectors

[Step 4/4] Storing in ChromaDB...
  → ChromaDB now contains 52 total chunk(s)

✓ Ingestion complete! You can now start the UI:
    streamlit run app.py
```

---

## How to Start the UI

```bash
streamlit run app.py
```

Open your browser to `http://localhost:8501`

The UI shows:
- A chat interface for asking questions
- **Sources** — which documents and pages the answer came from
- **Retrieved Context** — the exact chunks given to the LLM (expand to inspect)

---

## How to Run Tests

```bash
pytest test_ingest.py test_chunker.py test_retriever.py -v
```

> **Note:** `test_retriever.py` downloads the embedding model (~80 MB) on first run. Subsequent runs are fast.

---

## Example Query

After ingesting a machine learning paper:

**Question:** `What is the main contribution of this paper?`

**Answer:** `The paper introduces a novel attention mechanism called...`

**Sources:**
- `ml_paper.pdf — page 2`
- `ml_paper.pdf — page 8`

**Retrieved Context (expandable):**
```
Chunk #1 | Source: ml_paper.pdf | Page: 2 | Distance: 0.142
"The main contribution of this work is..."

Chunk #2 | Source: ml_paper.pdf | Page: 8 | Distance: 0.218
"We demonstrate that our approach..."
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No supported documents found` | Add PDF/TXT/MD files to `data/documents/` |
| `Vector store is empty` | Run `python -m src.ingest` first |
| `LLM_API_KEY is not set` | Add your key to `.env` |
| `Failed to open PDF` | PDF may be encrypted or corrupted |
| Model downloads slowly | First run downloads ~80 MB model — normal |

---

## Key Concepts Recap

| Term | Plain English |
|------|--------------|
| Embedding | A list of numbers that represents text meaning |
| Vector | Same as embedding — a point in high-dimensional space |
| Cosine similarity | How similar two vectors are (1 = identical, 0 = unrelated) |
| Chunk | A small piece of a document (≈500 tokens) |
| RAG | Retrieval-Augmented Generation — grounding LLM answers in your docs |
| ChromaDB | A local database that stores and searches vectors |
| Grounding | Forcing the LLM to only use provided context |
