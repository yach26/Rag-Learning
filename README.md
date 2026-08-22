# RAG Learning Journey

Welcome to the **RAG Learning Journey**! This repository contains a comprehensive 12-day curriculum detailing everything from the fundamental concepts of Retrieval-Augmented Generation to advanced production and agentic RAG architectures.

Whether you are just starting out with AI or looking to scale your local prototypes into enterprise-grade systems, these notes serve as a complete guide.

---

## Curriculum Overview

Here is the day-by-step breakdown of the topics covered:

### The Fundamentals
* **[Day 1: Introduction to RAG Architecture](Day_01_Architecture.md)** - What is RAG, and why do we need it instead of just fine-tuning LLMs?
* **[Day 2: Tokens, Embeddings, and Vectors](Day_02_Foundations.md)** - Understanding the basic data structures that power LLMs.
* **[Day 3: Chunking Strategies](Day_03_Chunking_Strategies.md)** - How to split documents effectively (recursive, semantic, fixed) without losing context.

### The Engine
* **[Day 4: Embedding Models (Deep Dive)](Day_04_Embedding_Models.md)** - How human text is translated into multi-dimensional arrays, dense vs. sparse vectors.
* **[Day 5: Similarity Search & Vector Mathematics](Day_05_Similarity_Search.md)** - Exploring Cosine Similarity, Dot Product, and why Euclidean Distance is rarely used.
* **[Day 6: Vector Databases](Day_06_Vector_Databases.md)** - Deep dive into FAISS, ChromaDB, Pinecone, Qdrant, and the HNSW indexing algorithm.

### The System
* **[Day 7: The Complete RAG Pipeline](Day_07_Complete_RAG_Pipeline.md)** - Assembling the pieces: from PDF parsing and OCR to final LLM generation.
* **[Day 8: Advanced Retrieval](Day_08_Advanced_Retrieval.md)** - Multi-Query, Query Expansion, Parent Document Retrievers, and Contextual Compression.
* **[Day 9: Reranking & Context Optimization](Day_09_Reranking_Context_Optimization.md)** - Cross-Encoders, solving the "Lost-in-the-Middle" problem, and RAG prompt engineering.

### Production & Beyond
* **[Day 10: Production RAG Systems](Day_10_Production_RAG_Systems.md)** - Semantic caching, incremental updates, security, access control, and streaming.
* **[Day 11: Evaluation & Agentic RAG](Day_11_Evaluation_Agentic_RAG.md)** - Mathematical evaluation (MRR, nDCG), anti-hallucination frameworks (RAGAS), and tool-calling Agents.
* **[Day 12: The RAG Master Summary](Day_12_RAG_Summary.md)** - The ultimate cheat sheet summarizing all 11 days, plus a peek into GraphRAG and Multimodal RAG.

---

## How to use this guide

Read through the days sequentially. Each markdown file includes:
1. **Clear Explanations** of the core engineering concepts.
2. **Best Practices** and common pitfalls to avoid.
3. **Real Production Examples** of how the technology is used in the wild.
4. **Interview Questions** to test your knowledge.

Happy learning! 

---

## 🚀 RAGForge: The Practical Implementation

This repository also contains **RAGForge** in the `ragforge/` directory — a learning-first Retrieval-Augmented Generation system built entirely from scratch in Python, without relying on black-box wrappers like LangChain or LlamaIndex.

RAGForge is built in two phases to demonstrate the evolution from a basic to an advanced, production-grade system.

### Phase 1: The Basics
The foundational system teaches the core components:
- **Ingestion**: Loading PDFs, TXTs, and Markdown files and preserving metadata (e.g., page numbers).
- **Chunking**: Overlapping sliding-window text chunking (~500 tokens).
- **Embeddings**: Generating 384-dimensional dense vectors using `all-MiniLM-L6-v2`.
- **Vector Store**: Local similarity search using ChromaDB.
- **Generation**: Grounded, hallucination-free generation using Google Gemini.

### Phase 2: Advanced Production Features
Phase 2 upgrades the basic pipeline to solve real-world retrieval failures:
1. **Hybrid Search (Vector + BM25)**: Combines semantic search with exact keyword matching using Reciprocal Rank Fusion (RRF). 
   *(Note: The BM25 index is built in-memory every session. This is fine for a learning project, but won't scale past a single-process deployment.)*
2. **CrossEncoder Reranking**: Re-scores hybrid candidates (`cross-encoder/ms-marco-MiniLM-L-6-v2`) to push the most relevant chunks to position #1.
3. **Conversation-Aware Retrieval**: Uses an LLM to rewrite follow-up questions ("what about the second one?") into standalone, context-independent queries.
4. **Semantic Chunking**: Splits text recursively at natural boundaries (paragraphs → sentences) instead of arbitrary characters.
5. **Incremental Ingestion**: Hashes files to skip unchanged documents, making re-ingestion nearly instant.
6. **OCR Fallback**: Routes scanned/image-only PDF pages through `pytesseract` automatically.
7. **Local Query Normalisation**: Uses `pyspellchecker` to instantly fix typos before embedding, preventing catastrophic query drift.
8. **Evaluation Harness**: Automatically measures `hit_rate@k` against ground-truth Q&A pairs to test retrieval quality.

### RAGForge Architecture (Phase 2)

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
                    │   Chunking   │  Recursive Semantic Splitting
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

### Running RAGForge

**1. Setup Environment**
```bash
cd ragforge
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env         # Add your LLM_API_KEY
```

**2. Add Documents & Ingest**
Place your files in `ragforge/data/documents/` and run:
```bash
python -m src.ingest
```

**3. Start the UI**
```bash
streamlit run app.py
```
Open your browser to `http://localhost:8501` to start chatting with your documents!