# Day 9 - Reranking & Context Optimization

**Date:** August 11, 2026

---

# 1. Introduction

In a standard RAG pipeline, the Vector Database returns the Top-K chunks based on Cosine Similarity. 
However, **Cosine Similarity is not perfect**. It is a fast, rough approximation. Often, the chunk at rank #5 is actually more relevant to answering the user's question than the chunk at rank #1.

To fix this, we introduce a **Reranking** step before sending the data to the LLM.

---

# 2. What is a Reranker?

A Reranker is a specialized machine learning model (often a Cross-Encoder) that evaluates the relevance of a document to a specific query.

* **Bi-Encoder (Standard Vector DB):** Embeds the query and document separately. Very fast, but misses deep linguistic relationships between the two texts.
* **Cross-Encoder (Reranker):** Takes both the query and the document *together* and processes them simultaneously. 
* **Trade-off:** Cross-encoders are incredibly accurate but way too slow to run against a million documents. 

### The Two-Stage Pipeline
1. **Stage 1 (Fast & Broad):** Vector DB retrieves the Top 50 documents using Cosine Similarity (Bi-Encoder).
2. **Stage 2 (Slow & Precise):** The Reranker evaluates those 50 documents against the query, scores them from 0 to 1, and sorts them. We take the new Top 5 and send them to the LLM.

*Popular Rerankers:* **Cohere Rerank**, **BGE Reranker**.

---

# 3. The "Lost-in-the-Middle" Problem

Research shows that LLMs are terrible at finding information buried in the middle of their context window. 

* If the answer is in the **very first** chunk provided in the prompt, the LLM finds it easily.
* If the answer is in the **very last** chunk, the LLM finds it easily.
* If the answer is in the **middle** chunks, the LLM often completely ignores it or hallucinates.

**How Reranking helps:** By aggressively scoring and sorting the chunks, we can strategically place the most relevant chunks at the very beginning and very end of the prompt, leaving the less relevant chunks in the middle.

---

# 4. Context Window Management

LLMs have finite context windows (e.g., 8k, 32k, 128k tokens). Even if the window is massive, dumping 50 chunks into a prompt is a bad idea because:
1. It increases latency (time to first token).
2. It increases API costs dramatically.
3. It exacerbates the Lost-in-the-Middle problem.

**Optimization Strategies:**
* **Strict Token Limits:** Cap the context size at 3000 tokens regardless of how many chunks were retrieved.
* **Dynamic Truncation:** Cut off chunks that score below a certain threshold on the Reranker (e.g., discard anything scoring < 0.3).

---

# 5. Prompt Engineering for RAG

The way you structure the prompt heavily influences the LLM's adherence to the facts.

**Bad Prompt:**
*"Answer the user's question based on these documents: [Context] Question: [Query]"*

**Good RAG Prompt (Crisp & Guardrailed):**
```text
You are an expert financial assistant. 
Your task is to answer the user's question using ONLY the provided context below.

Rules:
1. If the answer is not contained in the context, reply exactly with: "I do not have enough information to answer that."
2. Do not use outside knowledge.
3. Cite the document name if possible.

<context>
{chunk_1}
{chunk_2}
</context>

Question: {user_query}
```
*Note: Using XML tags like `<context>` helps modern LLMs clearly separate instructions from raw data.*

---

# 6. Day Summary

* **Vector Search is fast but imprecise.** 
* **Rerankers (Cross-Encoders)** act as a highly accurate secondary filter, re-scoring the top results from the vector DB.
* The **Lost-in-the-Middle** phenomenon dictates that we must place the most important context at the beginning or end of the prompt.
* **Context Optimization** and strict **Prompt Engineering** are necessary to prevent hallucinations and manage costs.
