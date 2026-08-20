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