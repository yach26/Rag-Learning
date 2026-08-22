# Day 8 - Advanced Retrieval

**Date:** August 10, 2026

---

# 1. Introduction

Standard RAG (embed chunk $\rightarrow$ embed query $\rightarrow$ cosine similarity) is great for simple Q&A. However, it fails on complex queries, vague language, or when context is fragmented.
**Advanced Retrieval** techniques fix these shortcomings by manipulating how queries are searched and how context is structured.

---

# 2. Query Manipulation Techniques

Sometimes the user's query is poorly phrased for vector search. We use an LLM to "fix" the query before searching.

### A. Query Expansion
* **Concept:** A user might ask, "How to fix a flat?" The system expands this to include synonyms: "How to fix a flat tire, puncture, bicycle wheel repair."
* **Why:** Increases the chance of a semantic match by broadening the vocabulary.

### B. Query Transformation (Rewrite)
* **Concept:** User says, "What about the second one?" (referring to a previous chat). The LLM rewrites the query using chat history: "What is the battery life of the second laptop mentioned?"

### C. Multi-Query Retrieval
* **Concept:** The LLM takes the user's query and generates 3-5 variations of it. 
* **Execution:** All 5 variations are embedded and searched in parallel. The results are pooled, duplicates are removed, and the final list is sent to the LLM. 
* **Why:** Overcomes the strictness of a single embedding vector.

---

# 3. Advanced Context Structuring

Standard chunking forces a trade-off: small chunks retrieve accurately but lack context; large chunks have context but retrieve poorly.

### A. Parent Document Retriever (Small-to-Big)
* **How it works:** 
  1. You split documents into **Large Parent Chunks** (e.g., 1000 tokens).
  2. You split those parents into **Small Child Chunks** (e.g., 200 tokens).
  3. You only embed and search the **Child Chunks** (high accuracy).
  4. When a child matches, you don't send the child to the LLM; you send its **Parent Chunk**.
* **Why:** You get the precise search accuracy of small chunks, but the LLM gets the rich context of large chunks.

### B. Multi-Vector Retrieval
* **How it works:** You extract summaries, hypothetical questions, or keywords from a document, and embed *those* instead of the raw text. But they still point back to the original document.
* **Why:** Matching a user's question to a "hypothetical question" vector is mathematically easier than matching a question to a dense paragraph of facts.

---

# 4. Self-Query Retriever

Users often mix semantic questions with metadata filters in natural language.
* **User:** "Find me sci-fi movies directed by Nolan about space."
* **Standard RAG:** Embeds the whole sentence and searches. Fails because "Nolan" is a metadata field, not a semantic concept.
* **Self-Query:** Uses an LLM to parse the query into two parts:
  1. Semantic Query: "movies about space"
  2. Metadata Filter: `{ "genre": "sci-fi", "director": "Nolan" }`
* It then executes a hybrid search on the vector DB.

---

# 5. Contextual Compression

If you retrieve 10 chunks, most of them will contain irrelevant sentences padding the actual answer.
* **How it works:** After retrieving the documents, you pass them through a lightweight model that compresses them by extracting *only* the sentences highly relevant to the query.
* **Why:** Saves context window space, reduces API costs, and prevents the LLM from getting distracted by noise.

---

# 6. Day Summary

* **Query Expansion/Multi-Query:** Modifies the search query to cast a wider, more accurate net.
* **Parent Document Retriever:** Searches on small granular chunks, but returns the larger surrounding context to the LLM.
* **Self-Query:** Translates natural language into strict metadata filters.
* **Advanced retrieval** is the key difference between a toy RAG prototype and a production-grade enterprise system.
