# Not Human Search MCP Agent

Search for agent-ready websites and verify MCP endpoints through the public [Not Human Search](https://nothumansearch.ai) MCP server.

This example is for developers building agents that need to discover usable APIs, OpenAPI specs, llms.txt files, and live MCP servers before wiring a tool into an agent runtime.

## Features

- Searches Not Human Search through its live MCP endpoint.
- Shows agentic readiness scores and detected signals for each result.
- Optionally verifies a remote MCP endpoint with a JSON-RPC handshake.
- Runs without API keys, accounts, or local MCP server setup.

## Tech Stack

- Python 3.10+
- `httpx` for async HTTP calls
- Model Context Protocol JSON-RPC over HTTP
- Not Human Search public MCP server

## Workflow

1. The script calls `tools/list` on `https://nothumansearch.ai/mcp`.
2. It calls the `search_agents` MCP tool with your query.
3. It prints ranked results with score and detected agent-readiness signals.
4. If `--verify-url` is provided, it calls the `verify_mcp` tool against that endpoint.

## Getting Started

### Prerequisites

- Python 3.10+
- `uv` or `pip`

No API keys are required.

### Installation

```bash
cd mcp_ai_agents/nothumansearch_mcp_agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Or with `uv`:

```bash
cd mcp_ai_agents/nothumansearch_mcp_agent
uv sync
```

## Usage

Search for agent-ready tools:

```bash
python main.py --query "payment api" --limit 3
```

Verify a live MCP endpoint:

```bash
python main.py --query "mcp registry" --limit 3 --verify-url https://nothumansearch.ai/mcp
```

Use a different Not Human Search MCP endpoint:

```bash
NHS_MCP_URL="https://nothumansearch.ai/mcp" python main.py --query "job api"
```

## Project Structure

```text
nothumansearch_mcp_agent/
├── main.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Acknowledgments

- [Not Human Search](https://nothumansearch.ai) for the public agent-readiness index and MCP endpoint.
- [Model Context Protocol](https://modelcontextprotocol.io) for the tool-calling protocol.
