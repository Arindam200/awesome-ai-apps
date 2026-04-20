# LangChain Starter

A minimal starter for [LangChain](https://python.langchain.com/) — the most widely used framework for composing LLM applications. This starter builds a tool-calling agent with `create_tool_calling_agent` + `AgentExecutor`, powered by Nebius Token Factory.

## Features

- `create_tool_calling_agent` + `AgentExecutor`
- Two Python tools auto-called by the model: `get_current_time`, `word_count`
- Chat history passed through the prompt `placeholder`
- Nebius Token Factory via `ChatOpenAI` (OpenAI-compatible)

## Prerequisites

- Python 3.10+
- Nebius API key — [Nebius Token Factory](https://studio.nebius.ai/)

## Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/langchain_starter

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
- "Explain chain-of-thought prompting in two sentences."

## Technical Details

- **Framework**: `langchain` + `langchain-openai`
- **Agent**: `create_tool_calling_agent` wrapped in `AgentExecutor`
- **Model**: `Qwen/Qwen3-30B-A3B` via Nebius (`ChatOpenAI` with custom `base_url`)
- **Tools**: `get_current_time`, `word_count` (plain `@tool`-decorated functions)

## Acknowledgments

- [LangChain](https://github.com/langchain-ai/langchain)
- [Nebius Token Factory](https://studio.nebius.ai/)
