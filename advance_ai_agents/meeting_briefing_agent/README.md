# 🗂️ Briefing Room — Pre-Meeting Intel Agent

> You have a call with a company in 30 minutes. What do you need to know?

Enter a **company name** (and optionally the **attendee**) and the agent researches the live web and produces a one-page, fully cited pre-meeting brief: **three things to know, a company snapshot, three questions to ask, and one thing to avoid.**

Built with **LangGraph**, **Tavily**, and **Nebius Token Factory**.

## 🚀 Features

- **LangGraph research loop, not a chain** — the graph plans research questions, searches the web with Tavily, then a *reflection* node checks coverage and loops back with follow-up queries if it finds gaps (up to your iteration budget).
- **Cited output** — every claim in the brief is grounded in the collected evidence with inline `[n]` citations and a sources list.
- **Live graph progress** — the Streamlit UI streams node-by-node updates (plan → research → reflect → write) as the run happens.
- **Structured intermediate outputs** — planning and reflection use Pydantic structured output (`with_structured_output`), so the control flow is data-driven, not prompt-parsing.
- **CLI + Streamlit UI** — run it headless in a terminal or interactively in the browser.
- **Optional LangSmith tracing** — flip two env vars to watch every graph step in LangSmith.

## 🛠️ Tech Stack

- **Python 3.10+**
- **[LangGraph](https://github.com/langchain-ai/langgraph)** — state machine with a conditional reflect→research cycle
- **[langchain-tavily](https://pypi.org/project/langchain-tavily/)** — Tavily web search as a LangChain tool
- **langchain-openai** — OpenAI-compatible client pointed at [Nebius Token Factory](https://dub.sh/nebius)
- **Streamlit** — web UI
- **Pydantic** — structured outputs

## Workflow

```
        ┌────────┐     ┌──────────┐     ┌─────────┐
START ─▶│  plan  │ ──▶ │ research │ ──▶ │ reflect │ ──┐ gaps + budget left
        └────────┘     └──────────┘     └─────────┘   │
              ▲                                       │
              └───────────────────────────────────────┘
                                                   │ sufficient
                                                   ▼
                                              ┌────────┐
                                              │  write │ ──▶ END
                                              └────────┘
```

1. **plan** — decomposes "meeting with *company*" into 4–6 search-ready research questions (structured output).
2. **research** — runs each question through Tavily, dedupes by URL, and accumulates evidence in graph state.
3. **reflect** — an editor-persona LLM judges coverage (structured output: `sufficient`, `gaps`). Gaps route the graph *back* to research; otherwise it proceeds.
4. **write** — synthesizes the markdown brief with inline citations from the numbered evidence.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- API keys:
  - [Nebius Token Factory](https://dub.sh/nebius) — serves the LLM
  - [Tavily](https://tavily.com/) — powers web research

### Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/meeting_briefing_agent

uv sync          # or: pip install -e .
cp .env.example .env   # add your NEBIUS_API_KEY and TAVILY_API_KEY
```

The app resolves `.env` from the `meeting_briefing_agent` directory, regardless
of the directory from which Streamlit is launched. The sidebar keeps the
original password-masked fields and fills them from `.env` when configured.

## ⚙️ Usage

**Streamlit UI:**

```bash
uv run streamlit run app.py
```

Open http://localhost:8501, enter a company (e.g. `LangChain`), optionally an attendee and your meeting goal, and hit **Generate brief**. Watch the graph work through its nodes, then read the brief and inspect the evidence table. Download the brief as Markdown with one click.

**CLI:**

```bash
uv run python main.py "LangChain" --attendee "Harrison Chase, CEO" --context "exploring an integration partnership"
```

**LangSmith (optional):** add these to `.env` to trace every run:

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your_langsmith_api_key
```

## 📂 Project Structure

```
meeting_briefing_agent/
├── graph.py          # LangGraph state machine (plan → research → reflect ⇄ → write)
├── app.py            # Streamlit UI with live node progress + evidence table
├── main.py           # CLI entrypoint
├── pyproject.toml    # Dependencies (uv/pip)
├── .env.example      # Required/optional environment variables
└── README.md
```

## 🔍 Technical Notes

- **Default model:** `Qwen/Qwen3-30B-A3B-Instruct-2507` on Nebius Token Factory (an economical MoE model with structured-output support). Switch to `Qwen/Qwen3.5-397B-A17B`, `deepseek-ai/DeepSeek-V4-Pro`, or `zai-org/GLM-5.2` in the sidebar for higher-quality reasoning and writing, or set `NEBIUS_MODEL`.
- **Iteration budget:** the reflect→research loop runs at most `max_iterations` times (default 2, configurable) so a run always terminates.
- **Evidence dedupe:** sources are deduplicated by URL across all research passes.

## 🤝 Contributing

Contributions are welcome! Please see the [CONTRIBUTING.md](../../CONTRIBUTING.md) for details.
