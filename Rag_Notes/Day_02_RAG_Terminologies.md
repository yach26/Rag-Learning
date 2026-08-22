# Day 2 - RAG Terminologies 

**Date:** August 4, 2026

---

# Introduction

On Day 1, I understood **what RAG is, why it exists, and how the overall architecture works**. I learned that a Large Language Model (LLM) does not directly search through company documents. Instead, relevant information is retrieved first and then provided to the LLM as context.

Today, the focus is on understanding the engineering terminology that forms the foundation of every RAG system. These are the concepts used throughout production-grade AI applications, and understanding them deeply is essential before building any RAG pipeline.

---

# 1. Tokens

## What are Tokens?

One of the biggest misconceptions beginners have is that Large Language Models read **words**. They do not.

An LLM processes text in the form of **tokens**.

A token is the smallest unit of text that a language model understands and processes. Depending on the tokenizer, a token can be:

* A complete word
* Part of a word
* A punctuation mark
* A number
* A special character

For example, the sentence:

> Artificial Intelligence is transforming the world.

is first broken into tokens before it reaches the model.

The model never directly reads the original sentence.

---

## Why are Tokens Needed?

Neural networks cannot process raw text.

Just as an image must be converted into pixels before a computer can process it, text must first be converted into tokens.

The overall flow looks like this:

```text
Human Text
     │
     ▼
Tokenizer
     │
     ▼
Tokens
     │
     ▼
Token IDs
     │
     ▼
Embedding Layer
     │
     ▼
Transformer Model
```

Without tokenization, an LLM cannot understand any text.

---

## Tokens vs Words

These two terms are often confused.

| Words                 | Tokens                                  |
| --------------------- | --------------------------------------- |
| Human-readable        | Model-readable                          |
| Used by humans        | Used by the LLM                         |
| Always complete words | Can be complete words or parts of words |

Example:

Word:

```
unbelievable
```

Possible tokenization:

```
un
believ
able
```

Although there is only **one word**, there are **three tokens**.

This is why context windows are always measured in **tokens**, not words.

---

## Why are Tokens Important in RAG?

Every LLM has a maximum context window.

For example:

* 8K Tokens
* 32K Tokens
* 128K Tokens
* 200K Tokens

This means the model cannot accept unlimited text.

Suppose a company has:

* 15,000 PDFs
* 80 GB of documents
* Millions of words

Sending everything to the LLM would exceed the token limit and dramatically increase cost.

Instead, RAG retrieves only the most relevant chunks so that the total number of tokens stays within the model's context window.

This is one of the primary reasons RAG exists.

---

## Interview Notes

**Question: Why are context windows measured in tokens instead of words?**

Because language models internally process tokens. Different words have different lengths, while tokenization provides a standardized representation for the model.

---

## Key Takeaways

* LLMs process **tokens**, not words.
* Tokens are produced by a tokenizer before the model begins inference.
* Context limits are measured in tokens.
* Efficient token usage is one of the main motivations behind RAG.

---

# 2. Vectors

Before understanding embeddings, it is important to understand what a vector actually is.

Many people think vectors are something specific to AI.

They are not.

Vectors are simply mathematical objects.

---

## What is a Vector?

A vector is an ordered list of numbers.

For example,

```
[2, 5]
```

is a 2-dimensional vector.

Similarly,

```
[3, 7, 4]
```

is a 3-dimensional vector.

An embedding is nothing more than a very large vector containing hundreds or thousands of numbers.

---

## Why Do Computers Use Vectors?

Computers understand numbers, not language.

If we directly give a computer the sentence:

> Employees are allowed to work remotely.

the computer has no understanding of its meaning.

Therefore, the text must first be converted into numbers.

Vectors provide a mathematical representation that computers can process efficiently.

---

## Thinking of Vectors as Coordinates

Imagine a simple graph.

Suppose we only describe objects using two properties.

* Animalness
* Friendliness

Now every object can be represented as a point.

```
Friendliness
      ▲
      │
 Dog ●
      │
 Cat ●
      │
      │
Football ●
────────────────────────► Animalness
```

Dogs and cats are close together because they share similar characteristics.

Football is much farther away because it represents a completely different concept.

Real embedding models work in exactly the same way, except instead of two dimensions, they use hundreds or even thousands.

---

## Important Point

A vector itself has **no meaning**.

It is simply a collection of numbers.

The meaning comes from **how those numbers are generated**.

This leads us to the next concept:

**Embeddings.**

---

## Interview Notes

**Question: Is every vector an embedding?**

No.

Every embedding is a vector, but not every vector is an embedding.

A vector is simply a mathematical representation.

An embedding is a vector specifically designed to capture the semantic meaning of data.

---

## Key Takeaways

* A vector is an ordered list of numbers.
* Vectors allow computers to represent information mathematically.
* Every embedding is a vector.
* Not every vector is an embedding.

---

# 3. Embeddings

Embeddings are the foundation of every modern Retrieval-Augmented Generation system.

Without embeddings, semantic search would not be possible.

---

## What are Embeddings?

An embedding is a numerical representation of text that captures its **meaning** instead of simply storing the individual words.

Unlike keyword matching, embeddings preserve semantic relationships between sentences.

For example,

> Employees can work remotely.

and

> Work from home is allowed.

contain different words but express nearly the same idea.

A good embedding model converts both sentences into vectors that are very close together in high-dimensional space.

This is why RAG can retrieve relevant information even when the exact keywords do not match.

---

## Why Do We Need Embeddings?

Suppose we compare two words using ASCII.

```
DOG

↓

68
79
71
```

Now compare

```
CAT

↓

67
65
84
```

Although dogs and cats are semantically similar, their ASCII values have no meaningful relationship.

ASCII represents **characters**.

Embeddings represent **meaning**.

That is the key difference.

---

## How are Embeddings Generated?

The overall process looks like this.

```
Document Chunk
      │
      ▼
Embedding Model
      │
      ▼
Embedding Vector
      │
      ▼
Stored inside Vector Database
```

The same process happens when the user asks a question.

```
User Question
      │
      ▼
Embedding Model
      │
      ▼
Question Embedding
```

The vector database then compares the question embedding with all stored document embeddings and retrieves the nearest neighbours.

Notice something important.

**The LLM does not perform this search.**

The similarity search is handled entirely by the vector database.

This was one of the biggest concepts I understood while learning RAG.

---
---

## Semantic Search using Embeddings

One of the biggest advantages of embeddings is that they allow us to search based on **meaning** instead of **keywords**.

Consider the following example.

### Document Chunk

> Employees can work remotely for two days every week.

### User Question

> Is Work From Home (WFH) allowed?

Notice that the document never mentions the words **"WFH"** or **"Work From Home."**

A traditional keyword search may fail because the exact words do not exist.

However, an embedding model understands that:

* Work remotely
* Remote work
* Work from home
* WFH

all describe similar concepts.

Therefore, their embeddings lie close together in the vector space.

This is why RAG systems are capable of retrieving relevant information even when the wording is completely different.

---

## How Similarity Search Works

Once every chunk has been converted into an embedding, all these embeddings are stored inside a Vector Database.

Suppose we have the following document chunks.

```text
Chunk A
Employees receive 20 paid leaves every year.

Chunk B
Medical insurance is provided to all employees.

Chunk C
Database backups run every midnight.
```

Now a user asks:

> How many vacation days do employees get?

The system first converts the question into an embedding.

Then it compares this embedding with every stored document embedding.

Although the words **vacation days** never appear in Chunk A, the embedding model understands that:

> Vacation Days ≈ Paid Leave

Therefore Chunk A receives the highest similarity score.

The retrieved chunk is then sent to the LLM.

This is called **Semantic Retrieval**.

---

## Common Misconception

Many beginners think the LLM searches the documents.

It does not.

The process actually looks like this.

```text
User Question
      │
      ▼
Embedding Model
      │
      ▼
Question Embedding
      │
      ▼
Vector Database
      │
      ▼
Similarity Search
      │
      ▼
Top-K Chunks
      │
      ▼
LLM
      │
      ▼
Final Answer
```

The LLM never searches through millions of documents.

Its job begins **after** the relevant chunks have already been retrieved.

---

## Interview Notes

**Question:** Why are embeddings preferred over keyword search?

**Answer:**

Keyword search only looks for exact words.

Embeddings preserve semantic meaning, allowing the system to retrieve relevant information even when different words or phrases express the same idea.

---

## Key Takeaways

* Embeddings capture semantic meaning.
* Similar meanings produce nearby vectors.
* Different wording can still retrieve the correct document.
* Similarity search happens before the LLM generates the answer.

---

# 4. Dimensions

Whenever an embedding is generated, it is represented as a list of numbers.

The number of values present inside that list is called its **dimension**.

---

## What is a Dimension?

Suppose an embedding looks like this.

```text
[0.12, -0.45, 0.91]
```

This embedding contains **3 values**.

Hence, it is called a **3-dimensional vector**.

Real-world embedding models usually generate much larger vectors.

For example,

* 384 Dimensions
* 768 Dimensions
* 1024 Dimensions
* 1536 Dimensions
* 3072 Dimensions

Every value represents one coordinate in a high-dimensional mathematical space.

---

## Why Do We Need So Many Dimensions?

Imagine trying to describe a student using only two properties.

* Height
* Weight

That is clearly not enough.

Now suppose we also include:

* Programming Skills
* Communication Skills
* CGPA
* Creativity
* Problem Solving Ability
* Leadership
* Teamwork

The description becomes much richer.

Embedding dimensions work in the same way.

More dimensions allow the model to represent more information about the meaning of a sentence.

---

## Does Higher Dimension Mean Better Embeddings?

Not necessarily.

Higher dimensions generally provide richer representations.

However, they also require:

* More storage
* More RAM
* More computation
* Slower similarity search

Choosing an embedding model is always a balance between **quality** and **efficiency**.

---

## Storage Example

Suppose a company has

* 1 Million chunks

and each embedding has

* 1536 dimensions

If every dimension occupies 4 bytes,

then

```text
1536 × 4 = 6144 Bytes

≈ 6 KB per embedding
```

For one million embeddings,

```text
≈ 6 GB
```

This storage only accounts for the embeddings.

Metadata, indexes, and other database information require additional storage.

This explains why efficient Vector Databases are necessary for production systems.

---

## Common Misconception

Many people think each dimension represents a specific feature like:

* Grammar
* Sentiment
* Topic

This is incorrect.

The model learns these dimensions automatically during training.

We generally cannot assign a human-readable meaning to an individual dimension.

Instead, the **entire vector together** represents the semantic meaning.

---

## Interview Notes

**Question:** Why don't embedding models simply use 10,000 dimensions?

**Answer:**

While more dimensions can capture more information, they also increase memory usage, storage requirements, computational cost, and retrieval latency.

Production systems therefore choose an embedding model that provides the best trade-off between accuracy and efficiency.

---

## Key Takeaways

* Dimension refers to the number of values inside an embedding.
* More dimensions generally provide richer representations.
* Higher dimensions also increase computational cost.
* Individual dimensions usually do not have an interpretable meaning.

---

# 5. Metadata

Until now, we have focused only on the actual text stored inside each chunk.

However, production RAG systems store much more than just the text.

Every chunk is usually accompanied by additional information called **Metadata**.

---

## What is Metadata?

Metadata is **information about the chunk**, not the chunk itself.

For example,

```json
{
  "text": "Employees receive 20 paid leaves every year.",
  "page": 15,
  "document": "HR Policy",
  "section": "Leave Policy",
  "year": 2026,
  "author": "Human Resources"
}
```

Here,

the actual knowledge is

> Employees receive 20 paid leaves every year.

Everything else is metadata.

---

## Why Do We Need Metadata?

Metadata makes retrieval much more powerful.

Instead of searching every document,

we can apply filters.

For example,

Suppose a company stores:

* HR Policies
* Finance Reports
* Engineering Documents
* Legal Agreements

If a user asks,

> Show me the HR leave policy.

The system can first filter:

```text
Department = HR
```

before performing similarity search.

This makes retrieval:

* Faster
* More accurate
* Less expensive

---

## Metadata in Production Systems

Typical metadata includes:

* Document Name
* File ID
* Page Number
* Section
* Department
* Author
* Creation Date
* Version
* Tags
* Source URL

The exact fields depend on the application.

---

## Metadata and Citations

Metadata also enables source attribution.

Instead of answering:

> Employees receive 20 paid leaves.

A production RAG system can answer:

> Employees receive **20 paid leaves every year**.

**Source:** HR Policy → Page 15 → Leave Policy Section

This improves trust and allows users to verify the information.

---

## Key Takeaways

* Metadata is information about a chunk.
* It is not part of the actual knowledge.
* Metadata enables filtering, citations, and better retrieval.
* Production RAG systems rely heavily on metadata for accuracy and explainability.

---
````md
# 6. Chunking (Overview)

## What is Chunking?

Chunking is the process of dividing a large document into smaller, meaningful pieces before storing it in a Vector Database.

Instead of converting an entire document into a single embedding, the document is split into multiple chunks. Each chunk is then converted into its own embedding and stored independently.

When a user asks a question, the retrieval process searches these chunks instead of the complete document, allowing the system to fetch only the information relevant to the query.

---

## Why Do We Need Chunking?

Imagine a company has a **200-page HR Policy** containing information about:

- Leave Policies
- Medical Benefits
- Payroll
- Work From Home
- Employee Conduct
- Promotions

If the entire document were stored as one embedding:

- The embedding would represent multiple unrelated topics.
- Retrieving specific information would become difficult.
- Large amounts of unnecessary context would be sent to the LLM.
- Response quality and efficiency would decrease.

By dividing the document into smaller chunks, the retriever can locate only the section that best answers the user's question.

---

## Example

```
HR_Policy.pdf
       │
       ▼
 ┌─────────────────────┐
 │ Chunk 1             │
 │ Leave Policy        │
 └─────────────────────┘

 ┌─────────────────────┐
 │ Chunk 2             │
 │ Medical Benefits    │
 └─────────────────────┘

 ┌─────────────────────┐
 │ Chunk 3             │
 │ Work From Home      │
 └─────────────────────┘

 ┌─────────────────────┐
 │ Chunk 4             │
 │ Employee Conduct    │
 └─────────────────────┘
```

Each chunk is embedded separately and stored in the Vector Database.

---

## Key Takeaways

- Chunking divides large documents into smaller meaningful sections.
- Every chunk has its own embedding.
- Retrieval happens at the chunk level rather than the document level.
- Good chunking improves the quality of a RAG system.
- Different chunking strategies will be covered in detail in **Day 3**.

---

# 7. Retriever (Overview)

## What is a Retriever?

A Retriever is the component responsible for finding the most relevant information from the knowledge base.

It acts as a bridge between the user's question and the stored document chunks.

The retriever **does not generate answers**. Its only responsibility is to identify which chunks are most relevant to the user's query.

---

## Why Do We Need a Retriever?

Suppose a company has:

- 50,000 Documents
- 2 Million Chunks

Searching through every chunk manually would be slow and inefficient.

Instead, the retriever quickly searches the Vector Database and selects only the most relevant chunks.

These retrieved chunks are then passed to the LLM for answer generation.

---

## Where Does the Retriever Fit?

```
User Question
      │
      ▼
Question Embedding
      │
      ▼
Retriever
      │
      ▼
Relevant Chunks
      │
      ▼
LLM
      │
      ▼
Answer
```

---

## Key Takeaways

- The Retriever searches the knowledge base.
- It retrieves relevant chunks, not final answers.
- It sits between the user's question and the LLM.
- Retrieval quality directly impacts answer quality.
- Different retrieval techniques will be explored in later chapters.

---

# 8. Vector Database (Overview)

## What is a Vector Database?

A Vector Database is a specialized database designed to store embeddings and efficiently retrieve the vectors that are most similar to a given query.

Unlike traditional databases, which search using exact values or keywords, a Vector Database searches based on **semantic similarity**.

---

## Why Do We Need a Vector Database?

Every document chunk in a RAG system is converted into an embedding.

As the number of documents grows, millions of embeddings may need to be stored.

A normal database is not optimized for similarity search on high-dimensional vectors.

A Vector Database is built specifically for this purpose, making retrieval much faster and scalable.

---

## Popular Vector Databases

Some commonly used Vector Databases include:

- FAISS
- ChromaDB
- Qdrant
- Pinecone
- Weaviate
- Milvus

Each has its own strengths depending on the use case, scalability requirements, and deployment environment.

---

## Where Does the Vector Database Fit?

```
Documents
     │
     ▼
Chunking
     │
     ▼
Embeddings
     │
     ▼
Vector Database
     ▲
     │
Retriever
     ▲
     │
User Query
```

The Vector Database stores document embeddings and works closely with the Retriever to locate the most relevant information.

---

## Key Takeaways

- A Vector Database stores embeddings.
- It is optimized for similarity search.
- It works together with the Retriever to fetch relevant chunks.
- It is a core component of every production RAG system.
- Internal indexing and search algorithms will be studied in detail later.

---

# 9. Prompt Construction (Overview)

## What is Prompt Construction?

After the Retriever finds the most relevant chunks, they are combined with the user's question to create the final prompt that is sent to the LLM.

This process is known as **Prompt Construction**.

The quality of the prompt directly influences the quality of the generated response.

---

## Example

```
Context:
Employees are entitled to 20 paid leaves every year.

Question:
How many vacation days do employees receive?

Instruction:
Answer only using the provided context.
```

The LLM receives all three components together and generates the final answer.

---

## Key Takeaways

- Prompt Construction combines retrieved context with the user's query.
- The LLM answers based on the provided context.
- The LLM does not search the database itself.

---

# 10. Training Time vs Inference Time

One of the most common misconceptions is that an LLM learns new information every time it answers a question.

This is not true.

There is a clear difference between **Training** and **Inference**.

---

## Training Time

Training is the phase during which the model learns patterns from large datasets.

During this phase:

- The model learns language.
- It develops reasoning capabilities.
- It acquires general knowledge from its training data.

Once training is complete, the model's internal knowledge remains fixed until it is retrained.

---

## Inference Time

Inference is the phase when users interact with the model.

During inference:

- The user asks a question.
- The Retriever fetches relevant context (in a RAG system).
- The LLM generates an answer using both its learned knowledge and the retrieved context.

No learning occurs during inference.

---

## Visual Comparison

```
Training Time

Data
 │
 ▼
Model Learns
 │
 ▼
Knowledge Stored
```

```
Inference Time

User Question
      │
      ▼
Retriever
      │
      ▼
Relevant Context
      │
      ▼
LLM
      │
      ▼
Final Answer
```

---

## Key Takeaways

- Training teaches the model.
- Inference is when the model answers questions.
- RAG retrieves external knowledge only during inference.
- The model is not retrained for every query.

---