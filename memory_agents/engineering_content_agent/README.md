# Developer Trend & DevRel Ideation Agent

> Chat-first Streamlit app that turns Hacker News demand signals, DEV.to supply gaps, and Weaviate Engram memory into a developer trend digest plus ranked talk, blog, and tutorial ideas.

An Agno-powered DevRel research assistant for developer-tool companies. It plans HN and DEV.to searches with Nebius GLM, gathers evidence in parallel, writes a structured ideation report, and remembers prior research across sessions with Engram.

Project path: `memory_agents/engineering_content_agent`

## Features

- **Chat-first Streamlit UI** with sidebar API key controls and live pipeline progress
- **GLM query planning** for high-intent HN and DEV.to searches
- **Parallel evidence gathering** from Hacker News Algolia, DEV/Forem API, and Engram Memory
- **DevRel ideation report** with trend digest plus ranked talk/blog/tutorial ideas
- **Report guardrails** for malformed JSON, stale-topic bleed, repeated DEV links, and raw HN comment fragments
- **Cross-session memory** via Weaviate Engram (compact product context + research summaries)
- **Markdown download** for the latest report

## Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) or pip
- [Nebius Token Factory](https://dub.sh/nebius) API key (required)
- [Weaviate Engram](https://docs.weaviate.io/engram) API key (optional but recommended)
- [DEV API key](https://developers.forem.com/api) (optional; public search works without it)

## Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/memory_agents/engineering_content_agent
   ```

2. **Install dependencies:**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -r requirements.txt
   ```

3. **Create a `.env` file:**

   ```bash
   cp .env.example .env
   ```

   Required:

   ```env
   NEBIUS_API_KEY=your_nebius_api_key_here
   NEBIUS_MODEL=zai-org/GLM-5.2
   ```

   Optional:

   ```env
   ENGRAM_API_KEY=your_engram_api_key_here
   ENGRAM_NAMESPACE=default
   ENGRAM_USER_ID=engineering-content-agent-user
   ENGRAM_CONVERSATION_ID=
   DEV_API_KEY=optional_dev_api_key_here
   LOG_LEVEL=INFO
   ```

   > **Note:** This app uses **Nebius Token Factory** via Agno's `Nebius` provider (Chat Completions). Get your API key from [Nebius Token Factory](https://dub.sh/nebius).

## Usage

1. **Start the Streamlit app:**

   ```bash
   uv run streamlit run app.py
   ```

2. **Open your browser** at `http://localhost:8501`.

3. **Add API keys** in the sidebar if they are not already loaded from `.env`.

4. **Describe your product and ask for research.** Example:

   ```text
   I run raah.dev, a web analytics and network observability tool. My audience is backend engineers who care about latency, error rates, and user-side ISP behavior. Research what developers are discussing on HN, check DEV.to saturation, and suggest talk and blog ideas around debugging production services.
   ```

5. **Follow up after a report:** `What did we find?` · `Show evidence for idea 1` · `What topics have we researched before?`

## How It Works

1. **Context extraction** — The chat router infers company, product, audience, and seed keywords from natural language.
2. **Query planning** — GLM selects HN queries, DEV queries, and tags for developer demand and supply research.
3. **Parallel research** — HN Algolia, DEV/Forem, and Engram memory search run concurrently.
4. **Report writing** — The DevRel Ideation Writer produces a trend digest and up to five ranked content ideas from gathered facts.
5. **Guardrails** — Local validation repairs links, filters noisy source fragments, and enforces product-context relevance.
6. **Memory storage** — A compact research summary is stored in Engram for future sessions.

The app shows a live pipeline stepper while query planning, parallel research, and report writing run.

### Engram vs local artifacts

- **Engram** stores compact product context and research summaries (top trends + idea titles).
- **Chat history** is the current Streamlit session transcript only.
- **`outputs/`** holds local runtime files such as `latest_ideation_report.json`. This folder is gitignored except for `outputs/.gitignore`.
- To drop legacy memories, use a new `ENGRAM_NAMESPACE` or clear memories in the Engram dashboard.

## Project Structure

```text
engineering_content_agent/
├── app.py                 # Streamlit UI, routing, pipeline stepper
├── agents.py              # Query planning, report writing, guardrails
├── chat.py                # Intent detection and follow-up helpers
├── config.py              # Settings and env loading
├── engram_memory.py       # Engram Memory store adapter
├── llm.py                 # Nebius model setup for Agno agents
├── models.py              # Dataclass domain models
├── sources.py             # HN Algolia and DEV.to search
├── tests/                 # Unit tests
├── assets/                # Logos and UI assets
├── outputs/               # Gitignored runtime artifacts
├── .streamlit/            # Streamlit theme config
├── .env.example
├── pyproject.toml
└── requirements.txt
```

## Tech Stack

- [Agno](https://docs.agno.com/) >= 2.2.3 — specialist agents and Nebius model provider
- [Nebius Token Factory](https://dub.sh/nebius) — LLM inference via Agno `Nebius` (Chat Completions)
- [Weaviate Engram](https://docs.weaviate.io/engram) — persistent cross-session memory
- [Streamlit](https://streamlit.io/) — chat UI
- [HN Algolia API](https://hn.algolia.com/api) — developer demand signals
- [DEV API](https://developers.forem.com/api) — article supply analysis

## Testing

```bash
cd memory_agents/engineering_content_agent
python -m pytest tests/ -q
```

## Provider Links

- [Nebius Token Factory](https://dub.sh/nebius)
- [Weaviate Engram docs](https://docs.weaviate.io/engram)
- [Agno docs](https://docs.agno.com/)
- [DEV API](https://developers.forem.com/api)
- [HN Algolia API](https://hn.algolia.com/api)

## Contributing

Contributions are welcome. See the repository [CONTRIBUTING.md](../../CONTRIBUTING.md) for guidelines. Submit one project per pull request.

## License

This project is part of [awesome-ai-apps](https://github.com/Arindam200/awesome-ai-apps) and is licensed under the MIT License.
