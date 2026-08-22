# Day 3 - Chunking in RAG

**Date:** August 5, 2026

---

# 1. Introduction

On Day 1, I learned the overall architecture of a RAG system. On Day 2, I understood the foundational terminologies like Tokens, Embeddings, Vectors, and Vector Databases. 

Today, we dive deep into **Chunking**, which is arguably one of the most critical engineering decisions when building a RAG pipeline. If chunking is done poorly, even the most advanced LLM and embedding models will fail to generate good answers. 

This deserves a deep engineering treatment because chunking directly affects what context is retrieved and sent to the LLM.

---

# 2. What is Chunking?

Chunking is the process of breaking down large documents into smaller, more manageable pieces (chunks) of text before converting them into embeddings.

Instead of passing an entire 100-page PDF to an embedding model, we divide it into sections, paragraphs, or sentences. Each of these chunks is then converted into its own embedding and stored in the Vector Database.

---

# 3. Why is Chunking Needed?

Chunking is necessary because of a few main constraints:

1. **Embedding Model Limits:** Most embedding models have a maximum token limit (e.g., 512 or 8192 tokens). They cannot process an entire book in a single pass.
2. **LLM Context Window Limits:** Even if we could embed a whole book, retrieving the entire book and sending it to an LLM would exceed its context window (or be prohibitively expensive and slow).
3. **Retrieval Accuracy:** If a chunk is too large, its embedding represents multiple, potentially unrelated topics. This dilutes the semantic meaning, making similarity search less accurate.

---

# 4. Why Not Store the Entire PDF?

If we embed a 50-page PDF as a single vector, that vector has to represent the meaning of the entire document. 

When a user asks a highly specific question, the embedding of their question will be compared to the embedding of the entire PDF. Because the PDF's embedding is an "average" of 50 pages of topics, the specific answer is buried. The similarity score will be low, and the retriever might miss it completely.

By chunking, we create focused vectors where each vector represents exactly one core idea or topic.

---

# 5. How Chunking Works

The basic pipeline of text processing before it enters the database looks like this:

```text
PDF / Source Document
         │
         ▼
  Text Extraction
         │
         ▼
     Cleaning (Removing noise)
         │
         ▼
     Chunking
         │
         ├── Chunk 1
         ├── Chunk 2
         ├── Chunk 3
         └── Chunk 4
         │
         ▼
  Embedding Model
         │
         ▼
  Vector Database
```

Each chunk is processed independently from this point onward.

---

# 6. Chunk Size

The **Chunk Size** defines how large each individual piece of text should be. It is usually measured in **tokens** (or sometimes characters).

### The Goldilocks Problem of Chunking

**Why 100-token chunks fail:**
If chunks are too small, they lose context. 
Imagine a chunk that just says: *"It was caused by a memory leak in the main thread."*
What is "It"? Without the preceding sentences, the LLM cannot provide a meaningful answer. This is called **context fragmentation**.

**Why 2000-token chunks fail:**
If chunks are too large, they contain too much irrelevant information. The embedding becomes diluted, making retrieval less precise. Furthermore, sending multiple 2000-token chunks to the LLM consumes massive context window space, increases latency, and raises API costs.

---

# 7. Chunk Overlap

To solve the problem of context fragmentation (where an important sentence is split right down the middle), engineers use **Chunk Overlap**.

Overlap means that the end of Chunk 1 is repeated at the beginning of Chunk 2.

```text
Document: "The quick brown fox jumps over the lazy dog. The dog wakes up and barks."

Without Overlap:
Chunk 1: "The quick brown fox jumps over"
Chunk 2: "the lazy dog. The dog wakes up and barks."
(The meaning of who jumped over whom might be lost)

With Overlap:
Chunk 1: "The quick brown fox jumps over the lazy dog."
Chunk 2: "over the lazy dog. The dog wakes up and barks."
```

Overlap ensures that no matter where the split happens, the semantic context bridges across chunks. A standard overlap might be 10-20% of the chunk size.

---

# 8. Context Fragmentation

Context fragmentation happens when the information required to answer a query spans across multiple chunks, but the retriever only pulls one of them, or the connection between them is lost. 

For instance, if Chunk A has a pronoun ("He did this") and Chunk B has the noun ("John Smith"), splitting them without overlap or metadata makes it impossible for the LLM to know who "He" is. Overlap and advanced chunking strategies are the primary defense against fragmentation.

---

# 9. Types of Chunking

Choosing how to split the text is just as important as the size.

### Fixed Chunking
Splitting the text purely by a fixed number of characters or tokens (e.g., every 500 tokens).
* **Pros:** Easy to implement, fast.
* **Cons:** Cuts off sentences in the middle. Ignores the structure of the document.

### Sentence Chunking
Splitting text using punctuation (periods, question marks).
* **Pros:** Keeps complete thoughts intact.
* **Cons:** Sentences might be too short to carry full context.

### Paragraph Chunking
Splitting by double newlines (`\n\n`).
* **Pros:** Preserves logical groupings of ideas.
* **Cons:** Some paragraphs can be extremely long, exceeding the ideal chunk size.

### Recursive Chunking
This is the default strategy in frameworks like **LangChain**. It tries to split by paragraphs first. If a paragraph is still too large, it recursively splits by sentences, then by words, and finally by characters.
* **Pros:** Respects document structure while strictly enforcing maximum chunk sizes.
* **Cons:** Slightly more complex to compute.

### Semantic Chunking
Instead of splitting by punctuation, this method uses a smaller embedding model to calculate the semantic similarity between adjacent sentences. If the meaning changes significantly between two sentences, it creates a split.
* **Pros:** When semantic chunking is superior, it creates highly cohesive chunks that group exact topics perfectly.
* **Cons:** Computationally expensive because you have to embed every sentence during the chunking phase itself.

### Document-aware Chunking
Splitting based on the structural format of the file (e.g., Markdown headers, HTML tags, or JSON keys).
* **Pros:** Excellent for structured documents.
* **Cons:** Requires custom parsers for every document type.

---

## Chunking Strategy Comparison

```text
Fixed       │ Cuts text blindly at N tokens. (High fragmentation)
Sentence    │ Natural breakpoints, but lacks deeper context.
Paragraph   │ Better logic, but unpredictable sizes.
Recursive   │ Smart fallback (Paragraph → Sentence → Word). Industry standard.
Semantic    │ AI-driven grouping based on meaning shifts. High quality, slow.
Doc-Aware   │ Splits by H1, H2, or HTML sections. Perfect for structured data.
```

---

# 10. Choosing the Right Chunk Size

How do you decide the perfect size? It depends on the data:

* **Legal Documents:** Often require larger chunks because clauses refer back to previous sections. Small chunks destroy legal context.
* **Medical Documents:** Can require medium chunks that capture symptoms, diagnosis, and treatment in one block without bringing in unrelated patient history.
* **Financial Reports:** Highly structured. Document-aware chunking (by section or table) works best here.
* **Code:** Must be chunked by functions or classes, not by characters. A split in the middle of a `for` loop ruins the syntax tree.

---

# 11. Chunking Best Practices

1. **Start with Recursive Chunking:** It is the most reliable baseline for most generic text.
2. **Add 10-20% Overlap:** This prevents edge-case context loss at the boundaries.
3. **Experiment with Chunk Sizes:** Test 256, 512, and 1024 token sizes with your specific embedding model to find the sweet spot.
4. **Clean Before You Chunk:** Remove headers, footers, and raw HTML noise before splitting text.

---

# 12. Common Mistakes

* **Treating tokens as characters:** A 500-character chunk is much smaller than a 500-token chunk.
* **Ignoring the embedding model's limits:** If your chunks are 1000 tokens, but your embedding model maxes out at 512, the model will silently truncate your text, losing half your data.
* **Blind fixed chunking:** Just splitting strings every 1000 characters without overlap is a recipe for terrible RAG performance.

---

# 13. Real Production Examples

**Use Case 1: Customer Support Chatbot**
* **Strategy:** Recursive Chunking (500 tokens, 50 token overlap).
* **Why:** FAQ articles and support tickets are usually short and to the point.

**Use Case 2: Contract Analysis System**
* **Strategy:** Document-aware (splitting by Markdown headers for clauses), falling back to large 1000-token chunks.
* **Why:** Legal meaning often spans multiple dense paragraphs.

**Use Case 3: Codebase Assistant**
* **Strategy:** Abstract Syntax Tree (AST) Chunking.
* **Why:** Code needs to be split logically by functions, methods, and classes to remain understandable to the LLM.

---

# 14. Interview Questions

**Question:** Why does recursive chunking usually perform better than fixed-size chunking?
**Answer:** Fixed chunking splits text blindly, often cutting sentences or words in half, destroying semantic meaning. Recursive chunking attempts to split at natural boundaries (paragraphs, then sentences, then words), preserving the logical structure of the text while ensuring chunks don't exceed the size limit.

**Question:** How does chunk overlap solve context fragmentation?
**Answer:** It ensures that words or concepts split at the boundary of a chunk are preserved in both the preceding and succeeding chunks, allowing the embedding model to maintain the semantic connection between the ideas.

**Question:** In what scenario is Semantic Chunking superior?
**Answer:** Semantic chunking is superior when dealing with dense, complex text where topic changes do not predictably align with paragraphs or headings, ensuring that chunks only contain semantically cohesive sentences.

---

# 15. Day Summary

* Chunking is how we prepare text for embedding.
* Small chunks lose context; large chunks dilute meaning.
* Overlap is crucial to prevent information from being lost at the boundaries.
* Recursive chunking is the industry standard default.
* Specialized domains (Legal, Medical, Code) require specialized chunking strategies.