# Day 7 - Complete RAG Pipeline

**Date:** August 9, 2026

---

# 1. Introduction

Over the last 6 days, we looked at individual pieces of RAG: Chunking, Embeddings, Math, and Vector Databases. 
Today, we zoom out and assemble the **Complete RAG Pipeline**. This is the end-to-end flow of how data moves from a raw file into a highly accurate LLM response.

---

# 2. Phase 1: Data Ingestion (Offline Pipeline)

This phase happens *before* the user ever asks a question. It is about preparing the database.

### 1. Document Parsing & OCR
* **PDFs/Word/HTML:** Raw files must be converted to plain text.
* **OCR (Optical Character Recognition):** If a PDF contains scanned images of text, standard parsers fail. We use tools like Tesseract or Unstructured.io to extract text from images.

### 2. Data Cleaning
* Remove repetitive headers/footers.
* Strip out HTML tags or weird formatting characters.
* Normalize whitespace. 
* *Garbage in = Garbage out.*

### 3. Chunking
* Break the cleaned document into semantic pieces (e.g., recursive chunking with 500 tokens and 10% overlap).

### 4. Embedding
* Pass each chunk through an Embedding Model (e.g., OpenAI `text-embedding-3`) to generate dense vectors.

### 5. Storage
* Insert the vectors, along with the original text chunk and metadata (author, date, source file), into the Vector Database (e.g., Pinecone, ChromaDB).

---

# 3. Phase 2: Retrieval & Generation (Online Pipeline)

This phase happens in real-time when the user submits a query.

### 1. The User Query
* User asks: *"What is our company's refund policy?"*

### 2. Query Embedding
* The query is sent to the **exact same Embedding Model** used in Phase 1 to convert it into a vector.

### 3. Similarity Search (Retrieval)
* The query vector is sent to the Vector Database.
* The DB performs an ANN search (using Cosine Similarity) and returns the Top-K (e.g., top 5) most similar document chunks.

### 4. Prompt Construction
* We take the retrieved text chunks and inject them into a structured prompt template.
* *Example Template:*
  ```text
  You are a helpful assistant. Answer the user's question using ONLY the provided context.
  
  CONTEXT:
  [Chunk 1 Text]
  [Chunk 2 Text]
  [Chunk 3 Text]
  
  QUESTION: What is our company's refund policy?
  ```

### 5. LLM Response (Generation)
* The fully constructed prompt is sent to the LLM (e.g., GPT-4o).
* The LLM reads the context, synthesizes the answer, and streams the response back to the user.

---

# 4. Pipeline Visualization

```text
[OFFLINE: Indexing]
Raw Docs ──> Clean & Parse ──> Chunking ──> Embedding Model ──> Vector DB
                                                                    │
[ONLINE: Querying]                                                  │
User Query ──> Embedding Model ──> Query Vector ────────────────────┘
                                        │ (Similarity Search)
                                        ▼
                                  Top-K Chunks
                                        │
                                        ▼
                             Prompt Construction
                                        │
                                        ▼
                                       LLM
                                        │
                                        ▼
                                  Final Answer
```

---

# 5. Day Summary

* The RAG pipeline is strictly divided into **Offline Indexing** and **Online Querying**.
* **Data Prep is critical:** If parsing, OCR, or cleaning fails, the rest of the pipeline is compromised.
* **Retrieval** bridges the gap by finding the right context and injecting it into the prompt.
* **Generation** is the final step where the LLM uses the retrieved context to synthesize the answer.
