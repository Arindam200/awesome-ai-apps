# LangGraph Starter

A minimal starter for [LangGraph](https://langchain-ai.github.io/langgraph/) — a framework for building stateful, graph-based LLM applications. This starter uses the prebuilt `create_react_agent` to assemble a ReAct loop (reason → act → observe) powered by Nebius Token Factory.

## Features

- Prebuilt ReAct agent from `langgraph.prebuilt.create_react_agent`
- Two Python tools auto-called by the model: `get_current_time`, `word_count`
- Multi-turn conversation via the graph's `messages` state
- Nebius Token Factory via `ChatOpenAI` (OpenAI-compatible)

## Prerequisites

- Python 3.10+
- Nebius API key — [Nebius Token Factory](https://studio.nebius.ai/)

## Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/langgraph_starter

pip install -r requirements.txt
# or: uv sync
```

Create `.env`:

```bash
cp .env.example .env
# set NEBIUS_API_KEY
```

## Usage

```bash
python main.py
```

### Example Queries

- "What time is it right now?" (triggers `get_current_time`)
- "How many words are in 'the quick brown fox jumps'?" (triggers `word_count`)
- "Explain the ReAct pattern in two sentences."

## Technical Details

- **Framework**: `langgraph` + `langchain-openai`
- **Agent**: `create_react_agent` (prebuilt ReAct loop — reason, act, observe)
- **Model**: `Qwen/Qwen3-30B-A3B` via Nebius (`ChatOpenAI` with custom `base_url`)
- **Tools**: `get_current_time`, `word_count` (plain `@tool`-decorated functions)

## Next Steps

To move beyond the prebuilt agent, define your own `StateGraph` with explicit `nodes` and `edges` so you can control routing, add memory, or branch on tool results. See the [LangGraph docs](https://langchain-ai.github.io/langgraph/) for building from scratch.

## Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Nebius Token Factory](https://studio.nebius.ai/)
