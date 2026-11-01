# Haystack Enterprise Knowledge Triage

> A Haystack agentic RAG app that routes internal questions by intent, retrieves and reranks evidence, and answers with citations, or declines when evidence is weak.

## 🚀 Features

- **Intent routing**: LLM classifier (Nebius) with a deterministic keyword fallback; scopes retrieval to the authoritative sources (HR, security, operations, finance).
- **Haystack pipelines**: ingestion (`DocumentSplitter` → `DocumentWriter`) and query (`InMemoryBM25Retriever` → intent filter → reranker) pipelines.
- **Cited answers**: every answer lists `file § section` sources.
- **Confidence gate**: below `TRIAGE_MIN_CONFIDENCE` the agent returns a clear fallback instead of guessing.
- **Runs offline**: with no API key it returns the top evidence chunk, so tests and demos need no network.

## 🛠️ Tech Stack

- **Python 3.9+**
- **Haystack (`haystack-ai` 2.x)**: pipelines, BM25 retrieval, custom components
- **Nebius Token Factory**: OpenAI-compatible LLM via `OpenAIChatGenerator`
- **In-memory document store**: no database needed

## Workflow

1. Markdown docs in `data/` are split per section and written to the store.
2. The question is classified into an intent.
3. BM25 retrieves candidates; the intent filter keeps relevant sources; the reranker scores query-term coverage (swap in any Haystack ranker).
4. If the top score is under the threshold → fallback. Otherwise the LLM answers from the numbered context with inline citations.

## 📦 Getting Started

```bash
cd rag_apps/haystack_enterprise_knowledge_triage
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add NEBIUS_API_KEY (optional)
python app.py "How many sick days do I get?"
python app.py          # interactive
pytest -q
```

### Environment Variables

See `.env.example`: `NEBIUS_API_KEY`, optional `NEBIUS_API_BASE`, `TRIAGE_MODEL`, `TRIAGE_MIN_CONFIDENCE`.

## Sample documents

`data/` holds a leave policy, security policy, incident runbook, expenses FAQ and a quarterly report. Add more `.md` files (and map them in `INTENT_SOURCES`) to extend.

## 🤝 Contributing

See the repository contributing guidelines.
