# Day 11 - Evaluation & Agentic RAG

**Date:** August 13, 2026

---

# 1. Introduction

How do you know if your RAG system is actually good? "Vibes" and manual testing don't scale. We need mathematical metrics to evaluate retrieval quality and LLM hallucination rates.

Finally, we look at the future of RAG: moving from static retrieval to autonomous **Agentic RAG**.

---

# 2. Evaluating Retrieval (The Math)

Before evaluating the LLM's answer, we must evaluate if the Vector Database is returning the right chunks.

### 1. Precision@K
* **What it means:** Out of the Top-K chunks returned, how many were actually relevant?
* **Example (Precision@5):** If 3 out of 5 chunks were relevant, Precision is 60%.

### 2. Recall@K
* **What it means:** Out of ALL the relevant chunks that exist in the database, how many did we successfully retrieve in our Top-K?
* **Example:** There are 10 relevant chunks in the DB. Our Top-5 results contained 2 of them. Recall is 20%. 

### 3. MRR (Mean Reciprocal Rank)
* **What it means:** Measures how high up the *first* relevant result appeared in the list.
* **Formula:** `1 / Rank`. If the first relevant result is at rank 1, score = 1.0. If at rank 3, score = 0.33.

### 4. nDCG (Normalized Discounted Cumulative Gain)
* **What it means:** Takes into account both the relevance of the documents and their exact position in the ranked list. Highly penalizes relevant documents that appear at the bottom.

---

# 3. Evaluating Generation (The LLM)

Frameworks like **RAGAS** (RAG Assessment) and **TruLens** use "LLM-as-a-judge" to evaluate the final answers.

### 1. Faithfulness (Anti-Hallucination)
* Evaluates if the LLM's answer is strictly derived from the provided context chunks. If the LLM makes up a fact not found in the chunks, faithfulness drops.

### 2. Answer Relevance
* Evaluates if the final answer actually addresses the user's original query, or if it went off on a tangent.

### 3. Context Relevancy
* Checks if the retrieved context was heavily polluted with noise. 

---

# 4. Agentic RAG

Standard RAG is a linear, single-pass pipeline: `Query -> Retrieve -> Generate`. 
**Agentic RAG** introduces reasoning, looping, and tool use.

### A. Tool Calling (Routing)
Instead of blindly searching the Vector DB every time, the Agent acts as a router.
* User: *"Summarize my PDF."* -> Agent calls Vector DB tool.
* User: *"What is the weather?"* -> Agent skips Vector DB, calls Weather API tool.
* User: *"Calculate my total expenses."* -> Agent calls SQL Database tool.

### B. Multi-Step Retrieval
Sometimes a question requires bridging multiple facts.
* **Query:** *"Who is the CEO of the company that acquired WhatsApp?"*
* **Linear RAG Fails:** It looks for "WhatsApp CEO acquisition" and finds nothing.
* **Agentic RAG Succeeds:**
  1. *Thought:* I need to find who acquired WhatsApp first. 
  2. *Action:* Query DB: "Who acquired WhatsApp?" -> Returns: "Facebook".
  3. *Thought:* Now I need the CEO of Facebook.
  4. *Action:* Query DB: "Who is CEO of Facebook?" -> Returns: "Mark Zuckerberg".
  5. *Final Answer:* Mark Zuckerberg.

### C. Self-Reflection & Fallback
If the Agent retrieves documents, reads them, and realizes they don't contain the answer, it can choose to **rewrite the query and search again** automatically, rather than giving a bad answer.

---

# 5. Day Summary

* **Precision, Recall, MRR, and nDCG** measure the mathematical accuracy of your retrieval step.
* **RAGAS / TruLens** evaluate hallucination, faithfulness, and answer relevance.
* **Agentic RAG** upgrades linear pipelines into reasoning engines that can use tools, perform multi-step research, and self-correct when data is missing.
