# A2A Multi-Agent Planning Example

> An Agno architect and a LangGraph reviewer cooperate over the Agent2Agent (A2A) protocol.

Give the client a software idea. It asks the architect for a short implementation plan, then sends that plan to the reviewer for one risk and improvement. The two agents run as independent HTTP services and can be started on different machines.

## 🚀 Features

- Two agents built with different frameworks: Agno and LangGraph.
- An A2A Agent Card for each service at `/.well-known/agent-card.json`.
- Client-side discovery of each card and its advertised skill before delegation.
- Live task state and artifact updates from both services in the terminal.
- Offline integration tests with stub responses; no API key is needed to run tests.

## 🛠️ Tech Stack

- Python 3.10+
- [A2A Python SDK](https://github.com/a2aproject/a2a-python) with JSON-RPC transport
- [Agno](https://github.com/agno-agi/agno) for the architect
- [LangGraph](https://github.com/langchain-ai/langgraph) and LangChain's `ChatOpenAI` for the reviewer
- [Nebius Token Factory](https://tokenfactory.nebius.com/) as the shared model provider
- FastAPI and Uvicorn for the two HTTP services

## Workflow

```text
User idea
  → discover Agno architect Agent Card → A2A task → implementation plan
  → discover LangGraph reviewer Agent Card → A2A task → risk and improvement
```

Each service first emits a submitted task, then a working status, a text artifact, and a completed status. The client prints these events as they arrive. It reads the architect's artifact and uses that text as the reviewer's input; the handoff crosses the A2A protocol boundary rather than calling the other framework in-process.

The services bind to localhost and keep task state in memory. A restart clears tasks. Shared deployments need authentication and durable task storage.

**A2A and MCP solve different connections.** A2A lets independent agents advertise skills, exchange tasks, and report progress. MCP lets an agent use tools and data sources. This example uses A2A for agent-to-agent delegation; an MCP tool could be added inside either agent without changing the handoff.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- A Nebius Token Factory API key for live model calls

### Environment Variables

Copy `.env.example` to `.env` in this directory and set `NEBIUS_API_KEY`. Both servers load this file. `NEBIUS_MODEL` defaults to `openai/gpt-oss-20b` and can be changed to another Nebius chat model.

### Installation

From `mcp_ai_agents/a2a_multi_agent/`:

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## ⚙️ Usage

Open three terminals in this directory, with the virtual environment active:

```bash
# Terminal 1
python server.py architect --port 8001

# Terminal 2
python server.py reviewer --port 8002

# Terminal 3
python client.py "Build a documentation search tool for a Python library"
```

The client prints both discovered Agent Cards' names and URLs, each task's progress updates, the architect's plan, and the reviewer's response. To run a server on another machine, set `--host` and `--public-url` so its card advertises an address the client can reach. The client accepts `--architect-url` and `--reviewer-url` for those service base URLs.

Abbreviated output (task IDs and model responses vary):

```text
Discovered Agno Architect: draft_plan via http://127.0.0.1:8001/a2a/jsonrpc
[Agno Architect] task <task-id> submitted
[Agno Architect] TASK_STATE_WORKING Agno Architect is working...
[Agno Architect] artifact: <implementation plan>
[Agno Architect] TASK_STATE_COMPLETED
Discovered LangGraph Reviewer: review_plan via http://127.0.0.1:8002/a2a/jsonrpc
[LangGraph Reviewer] task <task-id> submitted
[LangGraph Reviewer] TASK_STATE_WORKING LangGraph Reviewer is working...
[LangGraph Reviewer] artifact: <risk and improvement>
[LangGraph Reviewer] TASK_STATE_COMPLETED
```

### Tests and formatting

```bash
python -m pytest -q
ruff check .
ruff format --check .
mypy agents.py client.py server.py
```

The tests exercise card discovery, A2A delegation, task updates, and the two-framework adapters with local stubs; they do not send requests to Nebius. Running the live example requires a valid key and network access to Nebius.

## 📂 Project Structure

```text
a2a_multi_agent/
├── .env.example       # Key and model configuration
├── agents.py          # Agno architect and LangGraph reviewer
├── client.py          # Agent Card discovery and delegation
├── server.py          # A2A service and streaming task executor
├── tests/             # Offline integration and adapter tests
└── pyproject.toml     # Dependencies and tool configuration
```

## 🤝 Contributing

See the repository's [CONTRIBUTING.md](../../CONTRIBUTING.md) for contribution guidelines.

## 📄 License

This project follows the repository's license.
