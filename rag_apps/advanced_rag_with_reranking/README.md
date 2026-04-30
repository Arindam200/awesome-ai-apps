# Advanced RAG With Reranking

Production-shaped RAG application for PDF-heavy corpora. The demo ingests PDFs, parses
text/tables/visual pages, applies contextual retrieval, indexes dense and sparse vectors
in Qdrant, reranks evidence, streams answers, and shows clickable citations with PDF
page previews and chunk highlighting.

The app is intentionally domain-neutral even though the original local demo used Boeing
annual and sustainability reports. Upload your own PDFs through the UI.

## Features

- Browser upload flow for a folder of PDFs or multiple selected PDFs.
- Real-time ingestion progress by document.
- MarkItDown parsing with page-level provenance.
- Markdown table chunks with table-quality metadata.
- Optional Nebius/OpenAI-compatible VLM extraction for visual pages.
- Anthropic-style contextual retrieval augmentation.
- Dense embeddings plus sparse BM25-style retrieval in Qdrant.
- Reciprocal-rank fusion and reranking.
- Streaming answer generation.
- Sentence-level citations and clickable references.
- PDF page preview with highlighted retrieved chunk text when a text layer is available.

## Architecture

```text
PDF upload
  -> FastAPI upload job
  -> MarkItDown page parsing
  -> text/table/image chunking
  -> contextual augmentation
  -> dense embeddings + sparse vectors
  -> Qdrant hybrid index
  -> Postgres document/chunk metadata
  -> hybrid retrieval + RRF + reranking
  -> streaming LLM answer
  -> React UI with citations and PDF preview
```

## Services

Local development uses Docker for:

- Postgres
- Qdrant

Nebius/OpenAI-compatible inference is optional but recommended for best quality:

- Embeddings: `Qwen/Qwen3-Embedding-8B`
- Chat: `MiniMaxAI/MiniMax-M2.5`
- Vision: `Qwen/Qwen2.5-VL-72B-Instruct`

No credentials are committed. Add your own values to `.env`.

## Quick Start

```bash
cp .env.example .env
docker compose up -d postgres qdrant

python3 -m venv .venv
source .venv/bin/activate
pip install -e .
boeing-rag init-db
uvicorn boeing_rag.api:app --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
cd web
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

Use the `Upload` tab to select a folder or PDFs, then start ingestion.

## Environment

```bash
DATABASE_URL=postgresql+psycopg://rag:rag@localhost:5432/boeing_rag
QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=advanced_rag

NEBIUS_API_KEY=
NEBIUS_BASE_URL=https://api.studio.nebius.com/v1
NEBIUS_EMBED_MODEL=Qwen/Qwen3-Embedding-8B
NEBIUS_CHAT_MODEL=MiniMaxAI/MiniMax-M2.5
NEBIUS_VISION_MODEL=Qwen/Qwen2.5-VL-72B-Instruct
```

If Nebius variables are empty, the app can still run basic smoke paths with local
fallback embeddings and extractive answers, but retrieval/answer quality will be lower.

## Useful Commands

```bash
boeing-rag init-db
boeing-rag stats
boeing-rag ask "What does the corpus say about emissions?"
```

Run the backend:

```bash
uvicorn boeing_rag.api:app --reload --host 0.0.0.0 --port 8000
```

Run the frontend:

```bash
cd web && npm run dev
```

## Production Notes

For production, move upload ingestion from the in-process demo thread to a durable
worker queue such as Celery/RQ/Dramatiq with Redis, and use object storage for PDFs,
rendered pages, and parsed artifacts.

Recommended services:

- React frontend hosting
- FastAPI backend
- Postgres
- Qdrant
- Redis-backed worker queue
- Object storage
- Nebius/OpenAI-compatible inference endpoint
