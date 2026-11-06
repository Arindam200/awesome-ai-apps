# Raah Analytics AI Agent

An AI-powered web analytics assistant that connects to your [Raah.dev](https://raah.dev) account
via MCP and lets you ask natural-language questions about your website's performance, errors,
Web Vitals, and user sessions — answered in real time by **Llama 3.3 70B** running on
[Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/).

## Features

- **Natural-language queries** — ask anything: "Why is my LCP high?" or "Which endpoint is slowest?"
- **Live Raah data** — pulls real metrics (sessions, errors, Web Vitals, latency, geo) via the Raah MCP server
- **Llama 3.3 70B on Cloudflare** — fast, privacy-respecting inference with native tool-calling support
- **Agentic reasoning** — Llama discovers available tools, inspects their schemas, and chains multiple
  MCP calls to answer complex questions in one shot
- **Quick Insights** — one-click presets for Site Overview, Web Vitals, Top Errors, Slow Endpoints,
  Geo Performance, and Week-over-Week comparison
- **Actionable output** — highlights metrics outside healthy thresholds and suggests concrete fixes

## Demo

> Ask: *"Which API endpoints are slowest, and are there any regressions vs last week?"*

Llama will autonomously:
1. Call `list_tools` → discover `get_slowest_endpoints` and `compare_windows`
2. Call `describe_tool("get_slowest_endpoints")` → inspect its parameters
3. Call `run_tool("get_slowest_endpoints", {...})` → fetch p95 latency rankings
4. Call `run_tool("compare_windows", {"window_a": "7d", "window_b": "7d_prev"})` → detect regressions
5. Return a formatted analysis with tables and optimisation recommendations

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| LLM | Llama 3.3 70B (`@cf/meta/llama-3.3-70b-instruct-fp8-fast`) |
| Inference | [Cloudflare Workers AI](https://developers.cloudflare.com/workers-ai/) |
| Analytics | [Raah.dev](https://raah.dev) MCP server |
| MCP transport | Streamable HTTP (`mcp >= 1.3`) |
| UI | Streamlit |

## Getting Started

### Prerequisites

- Python 3.10+
- A [Raah.dev](https://raah.dev) account with an API token
- A [Cloudflare](https://dash.cloudflare.com) account with Workers AI access

### 1 — Get your Raah API token

1. Log in to [raah.dev](https://raah.dev)
2. Go to **Settings → API**
3. Click **Generate token** and copy it

### 2 — Get your Cloudflare credentials

| Value | Where to find it |
|---|---|
| **Account ID** | [dash.cloudflare.com](https://dash.cloudflare.com) → right-hand sidebar |
| **API Token** | My Profile → API Tokens → **Create Token** → use the *Workers AI* template |

### 3 — Clone and install

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/mcp_ai_agents/raah_analytics_agent

pip install -r requirements.txt
```

Or with `uv`:

```bash
uv venv && uv pip install -r requirements.txt
```

### 4 — Configure environment

```bash
cp .env.example .env
# Fill in RAAH_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN
```

### 5 — Run

```bash
streamlit run main.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

## Usage

1. Enter your **Raah API token**, **Cloudflare Account ID**, and **Cloudflare API token** in the sidebar
2. Optionally enter a **Raah Project ID** (leave blank to auto-discover)
3. Click a **Quick Insight** button or type a custom question
4. Click **Analyse** and watch Llama query your live analytics data

## Project Structure

```
raah_analytics_agent/
├── main.py          # Streamlit app + agentic MCP loop
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## How It Works

The agent uses Raah's **gateway tool pattern** — four MCP tools that Llama chains together:

| MCP Tool | Purpose |
|---|---|
| `whoami` | Returns authenticated identity and available projects |
| `list_tools` | Lists all analytics capabilities with summaries |
| `describe_tool` | Returns the full JSON schema for a capability |
| `run_tool` | Executes a capability (e.g. `get_web_vitals`, `get_recent_errors`) |

Llama receives these tools via Cloudflare's OpenAI-compatible endpoint and decides autonomously
which to call, in what order, to answer the user's question — no hardcoded query logic required.

## Contributing

Pull requests are welcome. See the repo-level [CONTRIBUTING.md](../../CONTRIBUTING.md).

## License

MIT — see [LICENSE](../../LICENSE).
