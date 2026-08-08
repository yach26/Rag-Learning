# Day 6 - Vector Databases 

**Date:** August 8, 2026

---

# 1. Introduction

By Day 5, we learned how to mathematically compare vectors. But what happens when you have 10 million vectors? You can't just run a `for` loop and calculate the Cosine Similarity against every single one—it would take forever.

This is why we need **Vector Databases**. They are purpose-built to store, index, and query massive amounts of high-dimensional vectors at lightning speed.

---

# 2. Exact Match vs. ANN

### KNN (K-Nearest Neighbors) - Exact Match
* **How it works:** Compares your query vector against *every single* document vector in the database.
* **Pros:** 100% accurate. Guaranteed to find the true closest match.
* **Cons:** Extremely slow. $O(N)$ time complexity. Unusable for millions of records.

### ANN (Approximate Nearest Neighbors)
* **How it works:** Trades a tiny bit of accuracy for a massive gain in speed. Instead of searching everything, it uses intelligent indexing to only search the most likely candidates.
* **Pros:** Blazingly fast. Scales to billions of vectors.
* **Cons:** Might occasionally miss the absolute closest vector (but usually finds one in the top 99% accuracy range).
* **Verdict:** Almost all modern Vector Databases use ANN algorithms under the hood.

---

# 3. The Magic of HNSW (Hierarchical Navigable Small World)

How do Vector Databases search so fast without checking everything? They use indexing algorithms. The undisputed king of these algorithms is **HNSW**.

### How HNSW Works:
Imagine a multi-story building:
1. **Top Floor (Sparse):** Contains only a few major "highway" nodes. You start your search here. You quickly jump to the node closest to your query.
2. **Middle Floors (Denser):** You drop down a level. There are more nodes now. You use your location from the top floor to jump to an even closer node on this level.
3. **Ground Floor (All Data):** You drop to the bottom layer which contains all the vectors. Because you narrowed down your location on the upper floors, you only have to search a tiny neighborhood on the ground floor to find your final answer.

* **Result:** HNSW allows databases to search millions of vectors in milliseconds by skipping the vast majority of irrelevant data.

---

# 4. Leading Vector Databases

### 1. Pinecone
* **Type:** Fully Managed SaaS / Cloud Native.
* **Best For:** Enterprises and teams that want zero infrastructure setup. You just send data to an API and it works.
* **Pros:** Extremely fast, highly scalable, zero maintenance.
* **Cons:** Closed source, can get expensive at scale.

### 2. Qdrant
* **Type:** Open Source / Cloud available. Written in Rust.
* **Best For:** High performance with advanced filtering.
* **Pros:** Blazingly fast (Rust), fantastic support for Payload filtering (metadata filtering *before* vector search), very cost-effective to self-host.
* **Cons:** Slightly steeper learning curve than Chroma.

### 3. ChromaDB
* **Type:** Open Source / Local-first.
* **Best For:** Prototyping, Python developers, AI startups.
* **Pros:** Dead simple to set up. You can run it entirely in-memory or save it to a local SQLite-like file with 3 lines of Python code.
* **Cons:** Not designed for massive, multi-node distributed enterprise scaling (yet).

### 4. FAISS (Facebook AI Similarity Search)
* **Type:** Open Source Library (C++ / Python bindings).
* **Best For:** Hardcore data scientists building custom pipelines.
* **Pros:** The gold standard for raw speed and low-level control.
* **Cons:** It is a *library*, not a database. It doesn't handle things like server management, persistent metadata updates, or REST APIs out of the box.

---

# 5. Metadata and Hybrid Search

A vector database doesn't just store arrays of numbers. It stores **Payloads** (Metadata).

If a user asks: *"Show me the latest financial report from Apple."*
1. **Vector Search:** Finds documents semantically related to Apple finances.
2. **Metadata Filter:** You add a hard SQL-like filter: `WHERE company = "Apple" AND year = 2026`.

This is called **Hybrid Search** (combining semantic vector search with traditional keyword/metadata filtering). Databases like Qdrant and Pinecone excel at this.

---

# 6. Real Production Examples

**Use Case 1: Local Prototyping**
* **Choice:** ChromaDB.
* **Why:** You just run `pip install chromadb` and you have a vector DB running in your Jupyter notebook in 5 seconds. Perfect for Day 1 of a hackathon.

**Use Case 2: E-Commerce Product Recommendations**
* **Choice:** Pinecone.
* **Why:** 50 million products. The engineering team doesn't want to manage Kubernetes clusters or worry about uptime. They just pay the Pinecone invoice and get an enterprise SLA.

**Use Case 3: Advanced Filtering Platform**
* **Choice:** Qdrant.
* **Why:** The app needs to search vectors, but filter aggressively by `user_id`, `date_range`, and `document_type` simultaneously. Qdrant's payload indexing makes this incredibly fast.

---

# 7. Interview Questions

**Question:** What is the difference between KNN and ANN?
**Answer:** KNN (K-Nearest Neighbors) performs an exact match by comparing the query against every single vector, which is 100% accurate but too slow for large datasets. ANN (Approximate Nearest Neighbors) uses indexing to search only a subset of likely candidates, sacrificing a tiny amount of accuracy for massive speed gains.

**Question:** Can you explain how HNSW indexing works at a high level?
**Answer:** HNSW is a multi-layered graph algorithm. It starts searching on a sparse upper layer to quickly find the general neighborhood of the query. It then navigates down through increasingly dense layers, refining the search until it finds the closest vectors on the bottom layer, drastically reducing the total number of comparisons needed.

**Question:** When would you choose FAISS over Pinecone?
**Answer:** FAISS is a low-level library ideal for data scientists who want maximum control over indexing algorithms in memory without database overhead. Pinecone is a fully managed cloud database designed for production web applications where you want a REST API, high availability, and zero infrastructure management.

---

# 8. Day Summary

* **Vector Databases** allow us to search millions of vectors in milliseconds.
* **ANN (Approximate Nearest Neighbors)** is the concept of trading slight accuracy for massive speed.
* **HNSW** is the most popular and powerful algorithm used to achieve ANN.
* **ChromaDB** is best for local dev, **Pinecone** for managed cloud, **Qdrant** for high-performance filtering, and **FAISS** for low-level algorithm control.
* Always use **Metadata Filtering** alongside vector search to dramatically improve the accuracy of RAG systems.
