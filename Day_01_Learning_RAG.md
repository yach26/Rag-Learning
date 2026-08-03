# Day 1 - Introduction to Retrieval-Augmented Generation (RAG)

**Date:** August 3, 2026

---

# Retrieval-Augmented Generation (RAG)

## What is RAG?

Retrieval-Augmented Generation (RAG) is a technique that combines a Large Language Model (LLM) with an external knowledge source. Instead of relying only on the information the model learned during training, RAG retrieves relevant information from external documents and provides it to the LLM before generating a response.

This allows the model to answer questions using up-to-date information, private company documents, or domain-specific knowledge without retraining the model.

---

# Why Do We Need RAG?

Large Language Models such as GPT, Claude, and Gemini have a fixed knowledge cutoff based on their training data. They are not automatically aware of:

* Recent news and events
* Internal company documentation
* Private databases
* Continuously changing information

Another limitation is the **context window**.

Even though modern LLMs support large context windows, it is still impossible and inefficient to send an organization's entire knowledge base (thousands of PDFs, policies, reports, and documents) with every user query.

Instead of providing all available data, RAG retrieves only the most relevant pieces of information and supplies them to the LLM. This reduces token usage, improves response quality, lowers cost, and minimizes unnecessary exposure of unrelated private data.

---

# Traditional LLM vs RAG

| Traditional LLM                            | RAG                                                                      |
| ------------------------------------------ | ------------------------------------------------------------------------ |
| Answers only from training knowledge       | Answers using retrieved external knowledge along with training knowledge |
| Limited by knowledge cutoff                | Can use the latest and private information                               |
| Cannot access company documents by default | Can answer questions from organization-specific documents                |
| Entire knowledge is fixed after training   | Knowledge base can be updated without retraining the model               |

---

# My Understanding of How RAG Works

A company's documents are first divided into smaller meaningful sections called **chunks**.

Each chunk is converted into a numerical representation called an **embedding**. These embeddings capture the semantic meaning of the text instead of just the individual words.

The embeddings are stored inside a **vector database**.

When a user asks a question:

1. The question is also converted into an embedding.
2. The vector database compares the question embedding with all stored document embeddings using similarity search.
3. The most relevant chunks (Top-K chunks) are retrieved.
4. These retrieved chunks are added to the prompt.
5. The LLM generates the final answer using the retrieved context.

An important realization from today's learning is that **the LLM does not search for the information**. The retrieval is performed by the vector database, while the LLM focuses only on generating a response using the retrieved context.

---

# High-Level RAG Architecture

```text
                Company Documents
                        │
                        ▼
                 Document Processing
                        │
                        ▼
                    Chunking
                        │
                        ▼
                 Embedding Model
                        │
                        ▼
                 Vector Database
────────────────────────────────────────────

                  User Question
                        │
                        ▼
                 Embedding Model
                        │
                        ▼
                Similarity Search
                        │
                        ▼
               Top-K Relevant Chunks
                        │
                        ▼
                 Prompt Construction
                        │
                        ▼
                  Large Language Model
                        │
                        ▼
                   Final Response
```

---

# Key Concepts Learned Today

* RAG extends an LLM with external knowledge instead of modifying the model itself.
* Documents are split into meaningful chunks before indexing.
* Embeddings represent the semantic meaning of text as vectors.
* Similar meanings produce embeddings that are close together in vector space.
* The user query is also embedded before retrieval.
* The vector database performs similarity search to retrieve the most relevant chunks.
* The LLM generates answers from the retrieved context rather than searching the database itself.
* Retrieving only relevant chunks is far more efficient than sending the entire knowledge base to the model.

---

## If LLMs Are Not Trained on Current Data, Then How Do They Answer Current Questions?

This was one of my biggest questions while learning RAG.

If GPT, Claude, or Gemini have a knowledge cutoff, how are they able to answer questions about today's news or recent events?

The answer is that **the LLM itself is not answering from newly learned knowledge**. Instead, the AI system first retrieves the latest information from an external source and then provides that information to the LLM as context.

For example, if I ask:

> **"Who won yesterday's cricket match?"**

The complete process is:

1. The AI system retrieves the latest information from an external knowledge source (such as a search engine, news database, or a company's document repository).
2. The retrieved information is inserted into the prompt as context.
3. The LLM reads this context and generates a natural language response.

The model does **not** update its training every day. It simply uses the information that is supplied to it at the time of answering the question.

This means there are two different sources of knowledge:

* **Internal Knowledge:** Information the LLM learned during training.
* **External Knowledge:** Information retrieved at inference time using techniques such as RAG or web search.

### Example

Without retrieval:

**Question:** "Who won the FIFA World Cup 2030?"

The model cannot answer correctly if that event happened after its training cutoff.

With retrieval:

The retrieval system fetches the latest article containing the result and provides it to the LLM. The LLM then reads the retrieved context and answers accurately.

This helped me understand an important distinction:

> **RAG does not make the LLM smarter or retrain it. It simply gives the LLM the right information before asking it to generate an answer.**

---
# Day 1 Summary

Today I understood that RAG is not a new language model but an architecture that enables an LLM to answer questions using external knowledge. The key idea is to retrieve only the most relevant information from a knowledge base and provide it to the LLM as context. This makes responses more accurate, up-to-date, scalable, and suitable for real-world applications where information changes frequently or is privately owned.

