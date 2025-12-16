## YouTube Trend Analysis Agent

YouTube channel analysis agent powered by **Memori**, **Agno (Nebius)**, **Exa**, and **yt-dlp**.  
Paste your YouTube channel URL, ingest recent videos into Memori, then chat with an agent that surfaces trends and concrete new video ideas grounded in your own content.

### Features

- **Direct YouTube scraping**: Uses `yt-dlp` to scrape your channel or playlist from YouTube and collect titles, tags, dates, views, and descriptions.
- **Memori memory store**: Stores each video as a Memori memory (via OpenAI) for fast semantic search and reuse across chats.
- **Web trend context with Exa**: Calls Exa to pull recent articles and topics for your niche and blends them with your own channel history.
- **Streamlit UI**: Sidebar for API keys + channel URL and a chat area for asking about trends and ideas.

---

### Setup (with `uv`)

1. **Install `uv`** (if you don’t have it yet):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. **Create the environment and install dependencies from `pyproject.toml`:**

```bash
cd memory_agents/youtube_trend_agent
uv sync
```

This will create a virtual environment (if needed) and install all dependencies declared in `pyproject.toml`.

3. **Environment variables** (set in your shell or a local `.env` file in this folder):

- `NEBIUS_API_KEY` – required (used both for Memori ingestion and the Agno-powered advisor).
- `EXA_API_KEY` – optional but recommended (for external trend context via Exa).
- `MEMORI_API_KEY` – optional, for Memori Advanced Augmentation / higher quotas.
- `SQLITE_DB_PATH` – optional, defaults to `./memori.sqlite` if unset.

---

### Run

From the `youtube_trend_agent` directory:

```bash
uv run streamlit run app.py
```

In the **sidebar**:

1. Enter your **Nebius**, optional **Exa**, and optional **Memori** API keys.
2. Paste your **YouTube channel (or playlist) URL**.
3. Click **“Ingest channel into Memori”** to scrape and store recent videos.

Then use the main chat box to ask things like:

- “Suggest 5 new video ideas that build on my existing content and current trends.”
- “What trends am I missing in my current uploads?”
