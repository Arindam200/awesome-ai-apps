# Semantic Kernel Starter

A minimal starter for [Microsoft Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/overview/) — an open-source SDK for orchestrating LLMs, plugins, and planners. This starter builds a `ChatCompletionAgent` with a custom plugin, powered by Nebius Token Factory.

## Features

- `ChatCompletionAgent` with streaming invocation
- Custom `TimePlugin` demonstrating the `@kernel_function` decorator
- Automatic function calling — the model decides when to invoke tools
- Nebius Token Factory via the OpenAI-compatible connector

## Prerequisites

- Python 3.10+
- Nebius API key — [Nebius Token Factory](https://studio.nebius.ai/)

## Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/semantic_kernel_starter

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

- "What time is it right now?" (triggers the `time.now` plugin)
- "Give me three ideas for an AI side project."
- "Explain semantic kernels in one paragraph."

## Technical Details

- **Framework**: `semantic-kernel` (Python)
- **Agent**: `ChatCompletionAgent`
- **Model**: `Qwen/Qwen3-30B-A3B` via Nebius (`OpenAIChatCompletion` with custom `base_url`)
- **Plugin**: `TimePlugin` (single `@kernel_function`)

## Acknowledgments

- [Semantic Kernel](https://github.com/microsoft/semantic-kernel)
- [Nebius Token Factory](https://studio.nebius.ai/)
