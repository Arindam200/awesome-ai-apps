# Dexter — Autonomous Investment Research Agent

## Goal

Build an autonomous financial research agent using **AgentField**. Dexter analyses any real, actively traded stock by running a 5-agent Investment Committee that produces two parallel research reports — one for **short-term** (1–6 month) and one for **long-term** (1–5 year) investment horizons — each with a BUY / HOLD / SELL verdict and a calibrated confidence score.

> **Scope:** Dexter is designed for stocks listed on major exchanges (NYSE, NASDAQ, LSE, etc.). It works best with large- and mid-cap names where yfinance data is complete (e.g. AAPL, NVDA, TSLA, MSFT, INTC). Delisted companies, OTC stocks, crypto, and ETFs are not supported.

---

## Architecture: The 5-Agent Investment Committee

### Pipeline

```
User Query
    ↓
[1] Manager       — Decomposes query → ResearchPlan          (sequential, gpt-4o)
    ↓
[2] yfinance      — 9 data fetches in parallel (asyncio.gather)
    │               annual income, quarterly income, balance sheet,
    │               annual cashflow, quarterly cashflow, company facts,
    │               analyst price targets, insider transactions, news (20 articles)
    ↓
[3] Analyst   ──┐ — Bull case LLM calls, concurrent (asyncio.gather, gpt-4o)
[3] Contrarian─┘ — Bear case LLM calls, concurrent (asyncio.gather, gpt-4o)
    ↓
[4] EditorShort ──┐ — Parallel synthesis (asyncio.gather, o3-mini)
[4] EditorLong  ──┘ — Short: near-term signals  |  Long: structural moat
    ↓
  DualResearchReport → tabbed UI (⚡ Short Term | 🏛️ Long Term)
```

### Agent Roles

| Agent              | Model   | Role                                                            | Runs         |
| ------------------ | ------- | --------------------------------------------------------------- | ------------ |
| **Manager**        | gpt-4o  | Decomposes query → ResearchPlan. Adaptive retry if data is low. | Sequential   |
| **Analyst**        | gpt-4o  | Bull case: revenue growth, margins, FCF, catalysts, targets     | Parallel [2] |
| **Contrarian**     | gpt-4o  | Bear case: risks, lawsuits, valuation, macro headwinds          | Parallel [2] |
| **EditorShort** ⚡ | o3-mini | Short-term verdict — catalysts, momentum, quarterly trends      | Parallel [3] |
| **EditorLong** 🏛️  | o3-mini | Long-term verdict — moat, balance sheet, secular tailwinds      | Parallel [3] |

### Visible Reasoning

Every agent writes step-by-step `reasoning_steps` _before_ its conclusion. These are streamed live to the UI as typing animations in collapsible thought drawers. Only one drawer can be open at a time.

### Confidence Calibration

The Editors (both short and long) use this anchoring scale, embedded in both the schema field description and the system prompt:

- **85–100** — Overwhelming evidence, minimal credible counter-case
- **65–80** — Clear lean, meaningful uncertainty exists
- **50–65** — Genuinely balanced, could go either way
- **<50** — Too uncertain to have strong conviction

---

## Data Inputs (Skills)

All data is fetched via `yfinance` — free, no API key required.

| Skill                      | What it provides                                          |
| -------------------------- | --------------------------------------------------------- |
| `get_income_statement`     | Revenue, net income, EBITDA — annual **and** quarterly    |
| `get_balance_sheet`        | Assets, liabilities, equity                               |
| `get_cash_flow_statement`  | Operating, investing, financing CF — annual and quarterly |
| `get_company_facts`        | P/E, forward P/E, margins, market cap, 52-week range      |
| `get_analyst_targets`      | Price targets (low/mean/high), consensus, upside %        |
| `get_insider_transactions` | Recent insider buys/sells with shares and $ value         |
| `search_market_news`       | 20 most recent news articles                              |

---

## Output Schema

```
DualResearchReport
├── short_term: ResearchReport
│   ├── time_horizon: "short_term"
│   ├── ticker, company_name
│   ├── summary, bull_case, bear_case
│   ├── key_metrics: list[str]
│   ├── risks: list[str]
│   ├── verdict: BUY | HOLD | SELL
│   ├── confidence: int (0–100)
│   ├── reasoning: str
│   └── reasoning_steps: list[str]
└── long_term: ResearchReport  (same structure)
```

---

## Delivery

### Streaming UI (primary)

Two-step SSE protocol:

1. `POST /research/stream/start` → `{ session_id }`
2. `GET /research/stream/events/{session_id}` → live SSE events

Events: `agent_start`, `agent_note`, `agent_complete`, `complete`, `error`

UI: single-page `ui/index.html` served at `GET /`. Tabbed Short/Long report, 5 glowing agent cards, live thought drawers with typing animation.

### Direct API (programmatic)

`POST /research` → blocks until complete, returns `DualResearchReport` JSON.

Individual agent endpoints also available: `/research/analyst`, `/research/contrarian`, `/research/editor`.

---

## Requirements

- Python 3.10+
- OpenAI API Key (set in `.env`)
- No other API keys — yfinance is free and needs no registration

## Non-Goals

- Real-time price data / intraday signals
- Portfolio management or order execution
- Crypto, ETFs, OTC stocks
- Serverless deployment (SSE requires persistent connections)
