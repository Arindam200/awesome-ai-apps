# SandBase CLI MCP Agent

> A minimal OpenAI Agents SDK example that connects to SandBase CLI over stdio MCP and asks an agent to discover and call an AI model.

## Features

- Starts SandBase CLI as a local stdio MCP server.
- Lets the agent inspect available models and choose a provider.
- Keeps the client code independent from provider-specific SDKs.

## Prerequisites

- Python 3.10+
- Node.js 18+ and `npx`
- An OpenAI API key (used only by the example agent)
- A SandBase account; the first run opens its OAuth device flow

## Setup

```bash
cp .env.example .env
# edit .env and set OPENAI_API_KEY
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

The script starts the immutable SandBase CLI release asset with `npx`, asks the agent to discover and inspect a compatible model, and sends one short prompt through the selected model. It requires the `sandbase_discover` → `sandbase_inspect` → `sandbase_run` tool sequence before printing a result. The agent defaults to `gpt-4o-mini`; set `OPENAI_MODEL` to override it. Review the tool calls and do not use production data for the first run.

## How it works

`main.py` uses `MCPServerStdio` to launch `npx -y https://github.com/sandbaseai/cli/releases/download/v0.1.17/sandbaseai-cli-0.1.17.tgz connect`. SandBase handles provider/model discovery and OAuth; the OpenAI Agents SDK handles the example agent loop. A five-minute MCP session timeout allows for first-run OAuth and provider requests. No SandBase provider key is committed or placed in the project files.

## Project structure

```text
sandbase_cli_mcp_agent/
├── .env.example
├── main.py
├── README.md
└── requirements.txt
```

## License

This example follows the repository license. SandBase CLI is Apache-2.0 licensed; see its [repository](https://github.com/sandbaseai/cli) for details.
