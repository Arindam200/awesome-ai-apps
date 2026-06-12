# FlowSentinel — AI Workflow Command Center

A Next.js dashboard that orchestrates AI agent workflows through n8n, powered by Nebius LLMs, with every human and AI action tracked in Velt's immutable activity log, all exposed securely through Tailscale Funnel.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLOWSENTINEL ARCHITECTURE                     │
│                                                                 │
│   ┌───────────────────────────────────────────────────────┐     │
│   │              Next.js Dashboard (UI)                   │     │
│   │  ┌──────────┐  ┌────────────┐  ┌──────────────────┐  │     │
│   │  │  Chat    │  │  Workflow  │  │  Activity Feed   │  │     │
│   │  │  Panel   │  │  Panel    │  │  (Velt SDK)      │  │     │
│   │  └────┬─────┘  └─────┬─────┘  └────────┬─────────┘  │     │
│   └───────┼──────────────┼─────────────────┼─────────────┘     │
│           │              │                 │                    │
│   ┌───────▼──────┐ ┌────▼──────────┐ ┌────▼─────────────┐     │
│   │ Nebius LLM   │ │ n8n Webhook   │ │ Velt Activity    │     │
│   │ Nemotron     │ │ + API         │ │ Logs API         │     │
│   │ via Token    │ │ Orchestration │ │ Immutable Trail  │     │
│   │ Factory API  │ │               │ │                  │     │
│   └──────────────┘ └───────────────┘ └──────────────────┘     │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │              Tailscale Funnel                           │   │
│   │   localhost:3000  ──▶  https://you.ts.net (public)     │   │
│   └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## What It Does

| Component | Tool | Role |
|-----------|------|------|
| **AI Brain** | [Nebius Token Factory](https://docs.tokenfactory.nebius.com/) | Powers chat + workflow planning with Nemotron Super |
| **Live Research** | Built-in Web Research | Fetches time-sensitive updates (for example, latest vendor announcements) and grounds responses with sources |
| **Orchestrator** | [n8n](https://docs.n8n.io/) | Chains multi-step AI workflows via webhook + visual automation |
| **Auditor** | [Velt Activity Logs](https://docs.velt.dev/) | Immutable, real-time trail of every human & AI action |
| **Shield** | [Tailscale Funnel](https://tailscale.com/kb/1312/funnel) | Secure HTTPS exposure without ports or cloud infra |

## Project Structure

```
flowsentinal_audittrail/
├── src/
│   ├── app/
│   │   ├── layout.tsx            # Root layout with Velt provider
│   │   ├── page.tsx              # Dashboard entry point
│   │   ├── globals.css           # Tailwind + custom design system
│   │   └── api/
│   │       ├── chat/route.ts     # Nebius LLM chat endpoint
│   │       ├── workflow/route.ts # n8n workflow trigger + status polling
│   │       └── activities/route.ts # Activity log CRUD
│   ├── components/
│   │   ├── Dashboard.tsx         # Three-panel layout
│   │   ├── ChatPanel.tsx         # AI chat with Nebius
│   │   ├── WorkflowPanel.tsx     # n8n workflow runner
│   │   ├── ActivityFeed.tsx      # Velt activity timeline
│   │   ├── Header.tsx            # Status bar + live indicators
│   │   └── providers/
│   │       └── VeltWrapper.tsx   # Velt SDK initialization
│   └── lib/
│       ├── nebius.ts             # Nebius client (OpenAI-compatible)
│       ├── webResearch.ts        # Live web research helpers for time-sensitive queries
│       ├── n8n.ts                # n8n workflow client
│       └── activity.ts           # Local + Velt cloud activity logging helpers
├── README.md
├── setup-tailscale.sh            # One-command Tailscale Funnel setup
├── package.json
├── .env.example
├── tailwind.config.ts
├── tsconfig.json
└── next.config.mjs
```

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/flowsentinal_audittrail
npm install
cp .env.example .env.local
```

### 2. Get your API keys

| Service | Where to get it | Env variable |
|---------|----------------|--------------|
| **Nebius** | [Nebius](https://dub.sh/nebius/) | `NEBIUS_API_KEY` |
| **n8n** | [n8n.io/download](https://n8n.io/download) or `npx n8n` | `N8N_WEBHOOK_URL`, `N8N_API_KEY` (optional), `N8N_BASE_URL` |
| **Velt** | [console.velt.dev](https://console.velt.dev/) | `NEXT_PUBLIC_VELT_API_KEY` (UI), `VELT_API_KEY` (backend ingestion) |

```bash
cp .env.example .env.local
# Edit .env.local with your keys and n8n webhook URL
# Optional: add VELT_API_KEY for backend activity ingestion to Velt Cloud
```

### 3. Run the dashboard

```bash
npm run dev
# Open http://localhost:3000
```

### 4. Set up your n8n webhook workflow

The app sends workflow trigger requests to n8n automatically when you click **Plan** in the chat. You need to create a matching webhook workflow in n8n:

1. Open n8n at `http://localhost:5678` (or run `npx n8n` to start it).
2. Create a new workflow and add a **Webhook** node as the trigger.
3. Set the Webhook node to **HTTP Method: POST** and note the generated URL.
4. Set **Respond:** to `When Last Node Finishes` (so the app gets a synchronous response).
5. Add any downstream nodes you want (e.g. HTTP Request, Set, Code, etc.).
6. The app sends this JSON body to your webhook:

```json
{
  "query": "user's original question",
  "analysis": "Nebius AI analysis summary",
  "steps": "Step 1 | Step 2 | Step 3"
}
```

7. Your n8n workflow can return any JSON — the app will display it in the Workflow panel log.
8. Copy the webhook URL (use the **Test URL** while developing, **Production URL** when live) into `N8N_WEBHOOK_URL` in `.env.local`.
9. Activate the workflow (toggle top-right) before using Production URL.

> **Tip:** Start simple — a Webhook → Set node that echoes the inputs back is enough to confirm the integration works end-to-end.

### 5. (Optional) Expose via Tailscale Funnel

```bash
# Requires Tailscale v1.52+ installed and logged in
chmod +x setup-tailscale.sh
./setup-tailscale.sh

# Or directly:
tailscale funnel 3000
```

Your dashboard is now accessible at `https://your-machine.your-tailnet.ts.net/` — share this URL with your team.


## The Dashboard

| Panel | What it does |
|-------|-------------|
| **Chat Panel** | Talk to Nemotron Super via Nebius — ask questions, get analysis, plan workflows |
| **Workflow Panel** | Trigger and monitor n8n executions in real-time |
| **Activity Feed** | Immutable timeline of every action — human, AI, and system — powered by Velt |

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/chat` | Send messages to Nebius LLM, supports chat and workflow planning modes |
| `POST` | `/api/workflow` | Trigger an n8n workflow via webhook |
| `GET` | `/api/workflow?run_id=X` | Check workflow status |
| `GET` | `/api/activities` | Fetch activity log with optional type filter |
| `POST` | `/api/activities` | Log a custom activity event |
| `GET` | `/api/diagnostics/velt` | View backend Velt sync status and last error |
| `POST` | `/api/diagnostics/velt/ping` | Emit a diagnostic event to test Velt ingestion |

## Assistant Response Pattern

FlowSentinel chat is designed to return:

1. **Direct answer first** (`## Answer`)
2. **Sources for time-sensitive queries** (`## Sources Checked`)
3. **Optional automation follow-up** (`## Optional Automation (n8n)`)

Use the **Plan** button when you want a full workflow plan staged for execution.

## Models

Uses **Nemotron Super** (configurable via `NEBIUS_MODEL`) via [Nebius Token Factory API](https://docs.tokenfactory.nebius.com/api-reference). The integration stays OpenAI-compatible (no new SDK required) and can be extended to Nebius fine-tuned/custom models for broader production use cases.

```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "https://api.tokenfactory.nebius.com/v1/",
  apiKey: process.env.NEBIUS_API_KEY,
});
```

## Provider Links

- [Nebius Token Factory docs](https://docs.tokenfactory.nebius.com/)
- [n8n docs](https://docs.n8n.io/)
- [Velt docs](https://docs.velt.dev/)
- [Tailscale Funnel docs](https://tailscale.com/kb/1312/funnel)