## Customer Support Voice Agent

Customer-support assistant powered by **OpenAI GPT‑4o**, **OpenAI TTS**, **Memori v3**, and **Firecrawl**.  
Paste your docs/FAQ URLs, ingest them into Memori, and chat with a voice-enabled support agent on top of that knowledge.

### Features

- **Company‑agnostic**: Works for any product/company docs you point it at.
- **Memori v3 knowledge base**: Docs are crawled with Firecrawl and stored in a Memori‑backed SQLite DB.
- **Chat + Voice UI**: Streamlit chat interface with optional audio playback.
- **Persistent memory**: Conversations and ingested docs are stored for future questions.

### Setup

Install dependencies (use any Python 3.11+ environment you like):

```bash
cd memory_agents/customer_support_voice_agent
python -m pip install -r requirements.txt
```

Create a `.env` file (copy from `.env.example`) and set:

- `OPENAI_API_KEY` – required (chat + TTS).
- `FIRECRAWL_API_KEY` – required to ingest docs via Firecrawl.
- `MEMORI_API_KEY` – optional, for Memori Advanced Augmentation / higher quotas.
- `SQLITE_DB_PATH` – optional, defaults to `./memori.sqlite`.

### Run

```bash
streamlit run app.py
```

In the **sidebar**:

1. Enter your **Firecrawl**, **Memori** (optional), and **OpenAI** API keys.
2. (Optionally) set a **Company Name**.
3. Paste one or more documentation URLs (one per line) under **“Ingest Docs into Memori”** and click **“Extract & store to Memori”**.

Then use the main chat box to ask customer‑support questions about your product.

> Note: `ingest_studio1.py` is kept as an example script for the original Studio1 demo.  
> For most use cases, you can ignore it and use the sidebar‑based ingestion instead.


