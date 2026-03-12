# Building a Production-Ready Multi-Agent Investment Committee with AgentField (Argus🔬)

> An autonomous financial research agent built on [AgentField](https://dub.sh/agentf). Argus uses a **5-agent Investment Committee** to produce two parallel research reports - one for **short-term** (1-6 months) and one for **long-term** (1-5 year) investment horizons.

## Architecture

```
User Query
    |
[1] Manager       - Decomposes query -> ResearchPlan (sequential)
    |
[2] yfinance      - 9 data fetches in parallel (asyncio.gather)
    |               annual + quarterly income/cashflow, balance sheet,
    |               company facts, analyst price targets, insider
    |               transactions, news (20 articles)
    |
[3] Analyst   --+ - LLM calls dispatched concurrently (asyncio.gather)
[3] Contrarian -+   Both see: financials, targets, insiders, news
    |
[4] EditorShort -+ - Also parallel (asyncio.gather). Model: gpt-oss-20b
[4] EditorLong  -+   Short: quarterly trends + near-term signals
    |                 Long:  annual data + moat + valuation
  DualResearchReport -> tabbed UI (Short Term | Long Term)
```

<img width="2752" height="1536" alt="studio1-02-argus-architecture-edited" src="https://github.com/user-attachments/assets/b126dfdf-66a8-4d38-9497-485a97148eae" />

> **Parallel note:** yfinance data (9 fetches), Analyst+Contrarian LLM calls, and both Editor LLM calls each use `asyncio.gather` - three separate parallelism stages. The Editors use `gpt-oss-20b` (better confidence calibration); all other agents use `gpt-oss-120b`.

### Visible Reasoning

Each agent writes its **step-by-step reasoning** into a `reasoning_steps: list[str]` field _before_ producing its conclusion. This is structured chain-of-thought - the model explains what it found, why it weighs evidence the way it does, and how it arrived at its answer. These steps appear live in the UI as each agent completes.

### The Investment Committee

| Agent | Model | Role | Runs |
| --- | --- | --- | --- |
| **Manager** | gpt-oss-120b | Decomposes query, dispatches committee | Sequential |
| **Analyst** | gpt-oss-120b | Bull case: revenue, margins, growth, free cash flow, catalysts | **Parallel [2]** |
| **Contrarian** | gpt-oss-120b | Bear case: risks, lawsuits, competition, valuation | **Parallel [2]** |
| **EditorShort** | gpt-oss-20b | Short-term verdict (1-6 months) - focuses on catalysts & momentum | **Parallel [3]** |
| **EditorLong** | gpt-oss-20b | Long-term verdict (1-5 years) - focuses on moat & intrinsic value | **Parallel [3]** |
| **Skills** | - | yfinance wrappers: 7 data endpoints, all fetched in parallel | Parallel [2] |

## Setup

### 1. Prerequisites

- Python 3.8-3.13
- A [Nebius](https://tokenfactory.nebius.com/) API key

### 2. Install

```bash
cd argus-agentfield

# Create venv + install dependencies (fast)
uv venv && uv pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` and fill in your key:

```env
NEBIUS_API_KEY=sk-...
```

> **Note:** No other API keys are needed - `yfinance` (free, no registration) covers all financial data, and AgentField's `Agent()` class requires no API key.

> **Supported tickers:** Argus works best with **real, actively traded stocks** listed on major exchanges (NYSE, NASDAQ, LSE, etc.) - e.g. `AAPL`, `NVDA`, `TSLA`, `MSFT`, `INTC`. Avoid: delisted companies, OTC/penny stocks, crypto tokens, and ETFs - yfinance data for these is often incomplete or missing, which degrades analysis quality.

### 4. Run

```bash
uv run python3 src/main.py
```

The agent starts on `http://localhost:8080`.

### 5. Open the UI

Visit **http://localhost:8080** in your browser. Type any query (e.g. _"Should I invest in NVDA?"_) and watch the 5-agent committee work in real time - cards glow, thought drawers type out reasoning live, then the tabbed report appears with separate **Short Term** and **Long Term** verdicts.

## Usage

Argus exposes **two ways** to run the full 5-agent pipeline. Both use the same agents, the same parallel execution, and produce the same `DualResearchReport` (short-term + long-term verdict). The difference is _how_ results are delivered.

---

### Option A - Streaming API (used by the UI)

The streaming API is what the browser UI uses. It sends events in real-time as each agent works, so you can watch the committee think step by step.

**Why streaming?**
The full pipeline takes 30-90 seconds. With streaming you get live updates - agent cards glow, thought drawers type out reasoning, and the report appears the moment the editors finish. Without streaming you'd stare at a blank page for a minute.

**How it works (2-step):**

```bash
# Step 1 - Start a session, get a session_id
SESSION=$(curl -s -X POST http://localhost:8080/research/stream/start \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I invest in NVDA?"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['session_id'])")

# Step 2 - Connect and receive live SSE events
curl -s "http://localhost:8080/research/stream/events/$SESSION"
```

**SSE event types you'll receive:**

| Event | Agent | When |
| --- | --- | --- |
| `agent_start` | manager / analyst / contrarian / editor_short / editor_long | Agent begins working |
| `agent_note` | any | Progress update mid-task |
| `agent_complete` | any | Agent done - includes `reasoning_steps`, `verdict`, `confidence` |
| `complete` | system | All done - full `{ short_term: {...}, long_term: {...} }` payload |
| `error` | system | Something went wrong |

The `complete` event payload:

```json
{
  "short_term": {
    "time_horizon": "short_term",
    "ticker": "NVDA",
    "verdict": "BUY",
    "confidence": 78,
    "summary": "Near-term momentum driven by...",
    "bull_case": "...", "bear_case": "...",
    "key_metrics": ["Revenue Growth: 122% YoY", "..."],
    "risks": ["..."],
    "reasoning": "..."
  },
  "long_term": {
    "time_horizon": "long_term",
    "ticker": "NVDA",
    "verdict": "BUY",
    "confidence": 85,
    "summary": "Structural AI infrastructure leader with...",
    ...
  }
}
```

---

### Option B - Direct Reasoner API (programmatic use)

For scripts, integrations, or testing individual agents. Blocks until complete, returns a single JSON response.

```bash
# Full pipeline - returns DualResearchReport (short + long term)
curl -X POST http://localhost:8080/research \
  -H "Content-Type: application/json" \
  -d '{"query": "Should I invest in AAPL?"}'
```

Response:

```json
{
  "short_term": { "ticker": "AAPL", "verdict": "HOLD", "confidence": 65, ... },
  "long_term":  { "ticker": "AAPL", "verdict": "BUY",  "confidence": 80, ... }
}
```

```bash
# Analyst only (bull case) - returns AnalystFinding
curl -X POST http://localhost:8080/research/analyst \
  -H "Content-Type: application/json" \
  -d '{"plan": {"ticker": "TSLA", "company_name": "Tesla Inc.", "hypotheses": ["EV dominance"], "data_needs": ["revenue"], "focus_areas": ["growth"], "reasoning_steps": []}}'

# Contrarian only (bear case) - requires plan + analyst_finding
```

> **Rule of thumb:** use the **streaming API** for anything user-facing; use the **direct API** for scripts, CI checks, or when you just want a clean JSON result.

## Skills Reference

All skills are also exposed as REST endpoints and can be called directly:

| Skill | Endpoint | Description |
| --- | --- | --- |
| `get_income_statement` | `POST /skills/get_income_statement` | Revenue, net income, EBITDA (annual **and** quarterly) |
| `get_balance_sheet` | `POST /skills/get_balance_sheet` | Assets, liabilities, equity |
| `get_cash_flow_statement` | `POST /skills/get_cash_flow_statement` | Operating, investing, financing cash flows |
| `search_market_news` | `POST /skills/search_market_news` | Recent news articles for a ticker (default 20) |
| `get_company_facts` | `POST /skills/get_company_facts` | P/E, market cap, sector, margins, 52-week range |
| `get_analyst_targets` | `POST /skills/get_analyst_targets` | Price targets (low/mean/high), consensus rating, upside% |
| `get_insider_transactions` | `POST /skills/get_insider_transactions` | Recent insider buys/sells with shares and $ value |

> **Note:** `PARA` (Paramount Global) was delisted after the Skydance merger and returns a 404 from yfinance. Use `WBD` (Warner Bros. Discovery) as an alternative for testing uncertain media stocks.

## Project Structure

```
argus-agentfield/
├── proposal.md          # Original design proposal
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variable template
├── README.md            # This file
├── ui/
│   └── index.html       # Single-page live UI (served at GET /)
└── src/
    ├── __init__.py      # Shared Agent singleton + AIConfig (openai/gpt-oss-120b)
    ├── schemas.py       # Pydantic models with reasoning_steps fields
    ├── skills.py        # yfinance data-fetching skills
    ├── reasoners.py     # 4-agent investment committee (AgentField reasoners)
    ├── stream.py        # SSE streaming backend + raw FastAPI routes
    └── main.py          # Entry point
```

## Deployment

Argus is a **persistent Python server** (FastAPI + uvicorn + SSE streaming). It cannot run on serverless platforms (Cloudflare Workers, Vercel, Lambda). Use any platform that supports long-running Python processes.

### Requirements on the host

| Requirement | Detail |
| --- | --- |
| Python | 3.10+ |
| `NEBIUS_API_KEY` | Set as an environment variable |
| `PORT` | Platform-injected or set manually (default `8080`) |
| Outbound internet | For Nebius API + yfinance data |

### Railway (recommended - easiest)

```bash
npm i -g @railway/cli
railway login
railway init      # link or create a project
railway up        # deploys from current directory
```

Set `NEBIUS_API_KEY` in the Railway dashboard -> Variables. Railway auto-injects `PORT`.

### Render

1. New Web Service -> connect GitHub repo
2. **Build command:** `pip install -r requirements.txt`
3. **Start command:** `python src/main.py`
4. Add `NEBIUS_API_KEY` in Environment -> Secret Files
5. Use a **paid instance** (free tier sleeps after 15 min, which kills SSE connections)

### Fly.io

```bash
fly launch          # generates fly.toml
fly secrets set NEBIUS_API_KEY=sk-...
fly deploy
```

### Generic VPS (DigitalOcean, Hetzner, etc.)

```bash
git clone <repo>
cd argus-agentfield
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in NEBIUS_API_KEY
# Run with a process manager:
PORT=8080 nohup python3 src/main.py &
# Or use systemd / PM2 / supervisor to keep it alive
```

> **Note:** The app prints some AgentField "degraded mode" warnings on startup - these are harmless. All research and UI features work fully without a cloud AgentField hub.
