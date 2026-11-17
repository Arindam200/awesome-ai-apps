# Compliance Evidence Collector

> An MCP-powered audit assistant that maps mock enterprise evidence to controls, flags gaps and writes a cited compliance report.

## 🚀 Features

- **Multiple evidence sources** via MCP tools: policy documents, change tickets, deployment logs, access reviews, plus a control catalogue
- **Control mapping**: SOC 2-style controls (access review, change management, incident response testing)
- **Gap detection**: missing evidence (deploy without a ticket), weak evidence (unsigned review), conflicting evidence (self-approved change)
- **Cited report**: every finding cites a ticket/review/document ID
- **No enterprise accounts**: fixtures are local JSON/markdown; only an LLM API key is needed

## 🛠️ Tech Stack

- **Python**
- **[FastMCP](https://gofastmcp.com)**: local MCP evidence server
- **[OpenAI Agents SDK](https://github.com/openai/openai-agents-python)**: agent + MCP stdio client
- **Nebius Token Factory** (default): any OpenAI-compatible provider via `LLM_BASE_URL`

## Workflow

`main.py` launches `evidence_server.py` over stdio. The agent lists controls, pulls evidence from each tool, and writes an executive summary plus a per-control status, citations, gaps and remediation.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- An API key for an OpenAI-compatible provider (e.g. [Nebius](https://studio.nebius.com))

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
cd awesome-ai-apps/mcp_ai_agents/compliance_evidence_collector
pip install -r requirements.txt
```

### Usage

```bash
python main.py
```

Check the mock MCP tools without an LLM:

```bash
python test_server.py
```

The sample data intentionally contains gaps: Q4 access review unsigned with only 3/6 removals on time, `CHG-102` approved by its own author, deploy `D-9003` with no change ticket, and no incident-response test evidence. Edit `data/` to try other scenarios.

## 📂 Project Structure

```
compliance_evidence_collector/
├── main.py             # agent
├── evidence_server.py  # FastMCP mock evidence server
├── test_server.py      # offline smoke test
└── data/               # controls, tickets, deploy logs, access reviews, policies/
```

## 🤝 Contributing

Contributions are welcome — see the repository's contributing guide.
