# smolagents Starter

A minimal starter for [HuggingFace smolagents](https://github.com/huggingface/smolagents) — a lightweight, code-first agent framework where agents "think in code". This starter builds a web-search agent powered by Nebius Token Factory.

## Features

- Code-first agent (`CodeAgent`) that writes Python to call tools
- DuckDuckGo web search tool out of the box
- Nebius Token Factory as the inference provider (OpenAI-compatible)
- Interactive CLI

## Prerequisites

- Python 3.10+
- Nebius API key — [Nebius Token Factory](https://studio.nebius.ai/)

## Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/smolagents_starter

# pip
pip install -r requirements.txt

# or uv (recommended)
uv sync
```

Create `.env`:

```bash
cp .env.example .env
# then edit and set NEBIUS_API_KEY
```

## Usage

```bash
python main.py
```

### Example Queries

- "Who won the latest F1 race and by how many seconds?"
- "Summarize today's top story on Hacker News"
- "Find three recent papers about agentic RAG"

## Technical Details

- **Framework**: smolagents (`CodeAgent` with `OpenAIServerModel`)
- **Model**: `Qwen/Qwen3-30B-A3B` via Nebius
- **Tools**: `DuckDuckGoSearchTool` + smolagents base tools

## Acknowledgments

- [smolagents](https://github.com/huggingface/smolagents)
- [Nebius Token Factory](https://studio.nebius.ai/)
