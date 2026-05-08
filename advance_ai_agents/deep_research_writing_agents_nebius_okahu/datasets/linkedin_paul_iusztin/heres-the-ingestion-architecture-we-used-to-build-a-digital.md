Here’s the ingestion architecture we used to build a Digital Twin agent:

(Steal it to build your own)

Most teams obsess over vector search and graph traversal.

Very few design the memory pipeline correctly.

These are the steps that matter...

1–2/ Raw Data → Data Warehouse

All sources land in one raw_documents collection in MongoDB (Atlas or self-hosted).

Emails keep headers.
Notion keeps metadata.
PDFs stay semi-structured.

Each document stores:

• source_type
• source_uri
• timestamps
• raw content

This is your durable ingestion layer.

3/ Clean + Chunk

Strip HTML. Extract headers. Normalize. Chunk.

Email: “Arthur, attached is the GraphRAG survey. Coffee Friday?”

Extract:

• from: Felix
• to: Arthur
• date
• cleaned body

Update in place with atomic $set.

4/ Extract Graph Triples

Structured following our ontology (LLM):

(Arthur) → CONNECTED_TO → (Felix)
(Arthur) → HAS → (Task: Coffee Friday)

Semi-structured using metadata:

(email_doc) → CONNECTED_TO → (graphrag_paper)

The ontology constrains node + edge types.
This prevents graph drift.

5/ Entity Resolution

Merge “Arthur” with existing “Arthur Iusztin”.

Match on:

• full_name
• aliases
• fuzzy search

Memory quality > memory quantity.

6/ Embeddings

Generate vectors for:

• Document chunks
• Tasks / Preferences chunks

Store them directly on each node.

7/ Knowledge Graph Objects

Each node becomes a document in kg_nodes:

• Properties
• Edges array
• Vector field

That’s your graph.

8/ Immutable Memory

All state changes are appended to a separate kg_events collection in MongoDB.

Never overwrite.
Append events such as:

• NodeCreated
• RelationshipAdded
• PreferenceUpdated

June → “Prefers Java”
September → “Prefers Python”

Both stored.
This ensures versioning.

Latest state built via:

$sort → $group → $last

If extraction was wrong, invalidate the event.

9/ Hybrid Retrieval

At query time:

1. $vectorSearch finds entry points
2. $graphLookup expands 1–3 hops
3. Text search catches exact matches

Single aggregation pipeline.
Bounded traversal.

10/ Query-Time Knowledge Graph

The graph is a projection built from immutable logs.

Traversal depth is explicit (maxDepth: 3).

tl;dr: GraphRAG needs controlled expansion.

11–12/ Agent Layer

Expose two tools:

Write Memory → append events
Search Memory → hybrid retrieval

The agent reads and writes to the same memory layer.

That’s Agentic GraphRAG.

The core idea:

GraphRAG is a memory architecture problem.

If ingestion is structured, retrieval becomes predictable.

For this architecture, we use MongoDB (Atlas or self-hosted) as a unified memory layer.

Documents, vectors, traversal, and event logs live in the same system.

P.S. Where does your RAG/GraphRAG ingestion pipeline break first?
