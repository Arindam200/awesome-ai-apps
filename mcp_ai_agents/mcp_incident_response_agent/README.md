# MCP Incident Response Agent

> An SRE assistant that triages alerts, checks service health, searches runbooks and drafts a status update, using a local mock MCP server.

## 🚀 Features

- **Alert triage**: reads firing alerts from a mock alert feed
- **Service status**: checks health, owner, dependencies and last deploy
- **Runbook search**: keyword search over local markdown runbooks
- **Incident output**: incident summary, likely impact, recommended next actions and a stakeholder status update
- **No enterprise accounts**: all data is local JSON/markdown fixtures; only an LLM API key is needed

## 🛠️ Tech Stack

- **Python**
- **[FastMCP](https://gofastmcp.com)**: local MCP server exposing the tools
- **[OpenAI Agents SDK](https://github.com/openai/openai-agents-python)**: agent + MCP client (stdio)
- **Nebius Token Factory** (default): any OpenAI-compatible provider works via `LLM_BASE_URL`

## Workflow

`main.py` starts `incident_server.py` over stdio. The agent calls `list_alerts`, `get_service_status` and `search_runbooks`, then writes the four report sections.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- An API key for an OpenAI-compatible LLM provider (e.g. [Nebius](https://studio.nebius.com))

### Environment Variables

```bash
cp .env.example .env
```

```env
LLM_API_KEY="your_api_key_here"
LLM_BASE_URL="https://api.tokenfactory.nebius.com/v1"
LLM_MODEL="meta-llama/Llama-3.3-70B-Instruct"
```

### Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/mcp_ai_agents/mcp_incident_response_agent
pip install -r requirements.txt
```

### Usage

```bash
python main.py
python main.py "Is checkout affected, and what should we do first?"
```

Verify the mock MCP tools without an LLM:

```bash
python test_server.py
```

The sample data models a `checkout-api` degradation caused by `payments-db` connection pool saturation shortly after a deploy. Edit files in `data/` to try other scenarios.

## 📂 Project Structure

```
mcp_incident_response_agent/
├── main.py              # agent
├── incident_server.py   # FastMCP mock server
├── test_server.py       # offline tool smoke test
└── data/                # alerts.json, services.json, runbooks/*.md
```

## 🤝 Contributing

Contributions are welcome — see the repository's contributing guide.
