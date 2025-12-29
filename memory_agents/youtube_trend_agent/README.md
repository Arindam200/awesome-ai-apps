## YouTube Trend Analysis Agent with Memori & MiniMax

An AI-powered **YouTube Trend Coach** that uses **Memori v3** as long‑term memory and **MiniMax (OpenAI‑compatible)** for reasoning.

- **Scrapes your channel** with `yt-dlp` and stores video metadata in Memori.
- Uses **MiniMax** to analyze your channel history plus **Exa** web trends.
- Provides a **Streamlit chat UI** to ask for trends and concrete new video ideas grounded in your own content.

---

### Features

- **Direct YouTube scraping**
  - Uses `yt-dlp` to scrape a channel or playlist URL (titles, tags, dates, views, descriptions).
  - Stores each video as a Memori document for later semantic search.

- **Memori memory store**
  - Uses `Memori` + a MiniMax/OpenAI‑compatible client to persist “memories” of your videos.
  - Ingestion happens via `ingest_channel_into_memori` in `core.py`, which calls `client.chat.completions.create(...)` so Memori can automatically capture documents.

- **Web trend context with Exa (optional)**
  - If `EXA_API_KEY` is set, fetches web articles and topics for your niche via `Exa`.
  - Blends Exa trends with your channel history when generating ideas.

- **Streamlit UI**
  - Sidebar for API keys, MiniMax base URL, and channel URL.
  - Main area provides a chat interface for asking about trends and ideas.

---

### Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- MiniMax account + API key (used via the OpenAI SDK)
- Optional: Exa and Memori API keys

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

3. **Environment variables**

You can either:

- Set these in your `.env`, (see .env.example) **or**
- Enter them in the Streamlit **sidebar** (the app writes them into `os.environ` for the current process).

---

### Run

From the `youtube_trend_agent` directory:

```bash
uv run streamlit run app.py
```

---

### Using the App

In the **sidebar**:

1. Enter your **MiniMax API Key** and (optionally) **MiniMax Base URL**.
2. Optionally enter **Exa** and **Memori** API keys.
3. Paste your **YouTube channel (or playlist) URL**.
4. Click **“Save Settings”** to store the keys for this session.
5. Click **“Ingest channel into Memori”** to scrape and store recent videos.

Then, in the main chat:

- Ask things like:
  - “Suggest 5 new video ideas that build on my existing content and current trends.”
  - “What trends am I missing in my current uploads?”
  - “Which topics seem to perform best on my channel?”

The agent will:

- Pull context from **Memori** (your stored video history),
- Use **MiniMax** (`MiniMax-M2.1` by default, configurable),
- Optionally incorporate **Exa** web trends,
- And respond with specific, actionable ideas and analysis.
