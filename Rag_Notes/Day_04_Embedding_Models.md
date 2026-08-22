# Day 4 - Embedding Models 

**Date:** August 6, 2026

---

# 1. Introduction

On Day 3, we discussed Chunking and how to prepare our source documents by breaking them down into meaningful pieces. 

Today, we take those chunks and push them through the most magical component of the RAG pipeline: the **Embedding Model**. This is where human language is translated into a format that computers can natively understand and compare—mathematical vectors. 

Understanding embedding models is critical because they dictate the entire quality of your retrieval phase. If the embedding model fails to capture the true semantic meaning of a chunk, the vector database will fail to retrieve it.

---

# 2. What is an Embedding?

An **Embedding** is a list of numbers (a vector) that represents the semantic meaning of a piece of text (a word, a sentence, or a document). 

Instead of treating words as isolated strings of characters, embedding models map words with similar meanings to similar areas in a multi-dimensional mathematical space. 

For example, the words "King" and "Queen" will be positioned very close to each other in this space, while the word "Apple" will be far away.

---

# 3. Why are Embeddings Needed?

Computers do not understand language. They only understand numbers and math.

If a user searches for "How do I return a product?", traditional keyword search (like SQL `LIKE` or Elasticsearch TF-IDF) will look for the exact words "return" and "product". 
If the document says "To send an item back for a refund...", traditional search fails completely because none of the keywords match.

Embeddings solve this by capturing the **meaning** (semantics) rather than the **exact characters** (lexical). Both sentences will generate similar vectors because their underlying meaning is the same.

---

# 4. How Text Becomes Vectors

The process of turning a sentence into an embedding involves several layers of neural network processing:

```text
Input Text: "The quick brown fox"
         │
         ▼
    Tokenization (Splitting into tokens)
    ["The", "quick", "brown", "fox"]
         │
         ▼
 Transformer Neural Network (e.g., BERT, OpenAI Text-Embedding)
 (Analyzes context, grammar, and relationship between tokens)
         │
         ▼
   Pooling Layer (Averaging token vectors into one sentence vector)
         │
         ▼
    Final Output Vector
 [0.124, -0.053, 0.884, ... , 0.312]
```

This output vector usually has a fixed number of dimensions (e.g., 384, 768, 1536, or 3072 dimensions).

---

# 5. Dimensionality

The number of values in the vector array is called its **Dimensionality**. 

For example, OpenAI's `text-embedding-3-small` outputs vectors with 1536 dimensions. This means every single sentence is represented by a list of 1536 floating-point numbers.

* **Lower Dimensions (e.g., 384):** Faster to compute, cheaper to store in a vector database, but might miss subtle semantic nuances.
* **Higher Dimensions (e.g., 1536+):** Captures incredible detail and complex meaning, but requires more storage and slower retrieval times.

Imagine each dimension representing an abstract concept: 
Dimension 1 might represent "Royalty", Dimension 2 might represent "Gender", Dimension 3 might represent "Age". (In reality, dimensions are abstract mathematical features determined by the neural network, not human-readable labels).

---

# 6. Dense vs. Sparse Vectors

You will often hear about dense and sparse vectors in search algorithms.

### Sparse Vectors (e.g., TF-IDF, BM25)
* Most of the values in the array are zeros.
* Each dimension represents a specific word in the vocabulary.
* Great for exact keyword matching.
* Example: `[0, 0, 1, 0, 0, 5, 0...]`

### Dense Vectors (e.g., Sentence Transformers, OpenAI Embeddings)
* Almost all values in the array are non-zero floating-point numbers.
* Dimensions represent abstract semantic concepts, not specific words.
* Great for semantic matching and RAG.
* Example: `[0.12, -0.45, 0.89, -0.11...]`

RAG primarily uses **Dense Vectors**.

---

# 7. How Vectors are Compared

Once we have vectors, how do we know if two pieces of text are similar? We calculate the distance or angle between their vectors in the multi-dimensional space.

### Cosine Similarity
This is the most common metric. It measures the cosine of the angle between two vectors.
* **1.0**: The vectors point in the exact same direction (Identical meaning).
* **0.0**: The vectors are orthogonal (Unrelated).
* **-1.0**: The vectors point in opposite directions (Opposite meaning).

### Euclidean Distance (L2)
Measures the straight-line distance between the endpoints of two vectors. Smaller distance means higher similarity.

### Dot Product
Multiplies the vectors together. Used frequently when vectors are normalized.

---

# 8. Evolution of Embedding Models

The technology has evolved rapidly:

1. **Word2Vec / GloVe (2013):** Mapped individual words to vectors. Ignored context. (The word "bank" in "river bank" and "bank account" had the same vector).
2. **RNNs / LSTMs (2015):** Started processing sequences of words, but struggled with long text.
3. **Transformers (BERT) (2018):** Read the entire sentence at once using "Attention". Context became king. (The word "bank" now has a different vector depending on the surrounding words).
4. **Modern Sentence Transformers (e.g., OpenAI, BGE, Cohere) (2022+):** Optimized specifically to compare whole paragraphs and documents for similarity search.

---

# 9. Choosing an Embedding Model

Not all embedding models are created equal. You must choose based on your constraints:

* **OpenAI (text-embedding-3):** Industry standard, highly capable, but requires API calls and sending data to OpenAI.
* **Cohere:** Excellent for multilingual support and enterprise search.
* **BGE (BAAI General Embedding):** Top-tier open-source model. Runs locally, free, great for privacy.
* **MiniLM (all-MiniLM-L6-v2):** Extremely fast and lightweight open-source model. Good for edge devices or low-budget prototypes, but lower accuracy.

Check the **MTEB (Massive Text Embedding Benchmark) Leaderboard** on HuggingFace to see the current ranking of models.

---

# 10. Embedding Best Practices

1. **Match Models:** You **MUST** use the exact same embedding model to embed your source documents and to embed the user's query. You cannot mix models.
2. **Normalize Vectors:** If your model doesn't do it automatically, normalize your vectors before storing them. This makes Cosine Similarity and Dot Product identical and faster to compute.
3. **Multilingual Data:** If your documents are in multiple languages, ensure you pick a model explicitly trained on multilingual data (e.g., `text-embedding-3` or `Cohere Multilingual`).
4. **Context Length:** Be aware of the embedding model's maximum context length (often 512 or 8192 tokens). Any text passed beyond this limit is usually silently truncated and ignored.

---

# 11. Common Mistakes

* **Swapping Models Mid-Project:** If you change your embedding model, you must delete your entire vector database and re-embed every single document. 
* **Using an LLM to Embed:** You don't use GPT-4 to create embeddings. You use a specialized embedding model. LLMs generate text; Embedding models generate vectors.
* **Ignoring the MTEB Leaderboard:** Don't just pick a random open-source model from 4 years ago. Embedding tech moves fast.

---

# 12. Real Production Examples

**Use Case 1: Privacy-Strict Healthcare App**
* **Model:** BGE-Large-En (Open Source).
* **Why:** Patient data cannot be sent to OpenAI APIs. Running a local, open-source model ensures HIPAA compliance while maintaining high retrieval accuracy.

**Use Case 2: Global Enterprise Search**
* **Model:** Cohere Multilingual v3.
* **Why:** The company has documents in English, Japanese, and Spanish. Cohere can map a Japanese query to an English document because they share the same semantic vector space.

**Use Case 3: Fast Prototyping / Generic Startup**
* **Model:** OpenAI `text-embedding-3-small`.
* **Why:** Cheap, highly reliable, massive 8192 token limit, and requires zero infrastructure setup.

---

# 13. Interview Questions

**Question:** What is the difference between an Embedding Model and an LLM?
**Answer:** An embedding model converts text into mathematical vectors designed for similarity search and semantic comparison. An LLM (Large Language Model) is designed to predict the next token and generate human-readable text.

**Question:** Why do we prefer Dense Vectors over Sparse Vectors for RAG?
**Answer:** Sparse vectors (like TF-IDF) only look for exact keyword matches. Dense vectors capture the underlying semantic meaning, allowing the system to find relevant documents even if the exact vocabulary differs between the query and the text.

**Question:** If I query my Vector DB and get terrible results, what is the first thing to check?
**Answer:** First, verify that the embedding model used for the query is exactly the same as the one used to embed the documents. Second, check if the chunks are exceeding the embedding model's token limit, causing truncation.

---

# 14. Day Summary

* Embedding models act as the translators between human language and mathematical vectors.
* They capture semantic meaning, solving the "exact keyword match" problem.
* Dimensionality dictates the detail of the vector.
* Cosine similarity is the standard way to measure how closely related two vectors are.
* You must use the exact same embedding model for both indexing and querying.
* Open-source models (like BGE) and closed-source (like OpenAI) offer different trade-offs for privacy and ease of use.
