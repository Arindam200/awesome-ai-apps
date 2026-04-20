# AutoGen Starter

A minimal starter for [Microsoft AutoGen](https://microsoft.github.io/autogen/) — a framework for building multi-agent AI applications. This starter creates an `AssistantAgent` with a custom tool, powered by Nebius Token Factory.

## Features

- `AssistantAgent` from `autogen-agentchat`
- Custom Python tool (`get_current_time`) auto-called by the model
- Streaming responses rendered via `Console`
- Nebius Token Factory via `OpenAIChatCompletionClient` (OpenAI-compatible)

## Prerequisites

- Python 3.10+
- Nebius API key — [Nebius Token Factory](https://studio.nebius.ai/)

## Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/autogen_starter

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

- "What time is it right now?" (triggers the `get_current_time` tool)
- "Write a haiku about distributed systems."
- "Explain multi-agent orchestration in one paragraph."

## Technical Details

- **Framework**: `autogen-agentchat` + `autogen-ext[openai]` (v0.4+)
- **Agent**: `AssistantAgent` with `reflect_on_tool_use=True`
- **Model**: `Qwen/Qwen3-30B-A3B` via Nebius (`OpenAIChatCompletionClient` with custom `base_url`)
- **Tool**: `get_current_time` (plain Python function)

## Acknowledgments

- [AutoGen](https://github.com/microsoft/autogen)
- [Nebius Token Factory](https://studio.nebius.ai/)
