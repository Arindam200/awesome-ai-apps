# Letta Starter

A minimal starter for [Letta](https://www.letta.com/) (formerly MemGPT) — a framework for building **stateful** agents with long-term memory that persists across sessions.

## Features

- Stateful agent with persistent memory blocks (`human`, `persona`)
- Automatic memory management — the agent edits its own memory as it learns
- Powered by Nebius Token Factory for inference
- Interactive CLI

## Prerequisites

- Python 3.10+
- Docker (to run the Letta server)
- Nebius API key — [Nebius Token Factory](https://dub.sh/nebius)

## Setup

**1. Run the Letta server:**

```bash
docker run -d --name letta -p 8283:8283 \
  -e OPENAI_API_KEY=$NEBIUS_API_KEY \
  -e OPENAI_API_BASE=https://api.studio.nebius.ai/v1 \
  letta/letta:latest
```

**2. Install the client:**

```bash
cd awesome-ai-apps/starter_ai_agents/letta_starter
pip install -r requirements.txt
# or: uv sync
```

**3. Configure env:**

```bash
cp .env.example .env
# edit NEBIUS_API_KEY and (optionally) LETTA_BASE_URL
```

## Usage

```bash
python main.py
```

Try a sequence like this and then restart the script — the agent will remember:

1. "Hi, my name is Arindam and I love building AI apps."
2. (restart) "What's my name and what do I like to build?"

## Technical Details

- **Framework**: Letta (`letta-client`)
- **Model**: `Qwen/Qwen3-30B-A3B` via Nebius
- **Memory**: Persistent memory blocks stored by the Letta server

## Acknowledgments

- [Letta](https://docs.letta.com/)
- [Nebius Token Factory](https://dub.sh/nebius)
