# AI Shark Tank Agent

> A desktop pitch-practice room where you are the founder and three Nebius-backed investor sharks evaluate your answers, negotiate, and save deal memos.

Practice answering investor questions under pressure in a Shark Tank-style 3D room. Three Mastra agents act as sharks with different investor archetypes, score your answers each round, and produce a final deal memo saved in SQLite.

## Features

- **Interactive pitch room**: React Three Fiber stage with three shark seats and a center question panel.
- **Three shark agents**: MiniMax (operator), DeepSeek Flash (growth), and Nemotron Lightning (lead deal-maker).
- **Round-based Q&A**: Quick runs (3 rounds) or full runs (6 rounds), then offers, passes, or counter-offers.
- **Deal memos and drills**: Saved reports library, printable HTML memos, and practice drills from past sessions.
- **Nebius Token Factory**: All shark reasoning runs through Nebius OpenAI-compatible chat completions (no local fallbacks).

## Tech Stack

- **Node.js / Express**: Backend API, Mastra agents, SQLite persistence
- **React + Vite**: Frontend UI
- **React Three Fiber / Three.js**: 3D pitch room
- **Mastra**: Multi-agent orchestration
- **Nebius Token Factory**: LLM inference for all three sharks

## Prerequisites

- Node.js 18+
- npm
- [Nebius Token Factory](https://tokenfactory.nebius.com/) API key

## Setup

```bash
cd advance_ai_agents/shark_tank_agent
cp .env.example .env
# Add your NEBIUS_API_KEY to .env
npm install
```

### Environment Variables

```env
NEBIUS_API_KEY=your_nebius_key
NEBIUS_BASE_URL=https://api.tokenfactory.nebius.com/v1/
NEBIUS_NEMOTRON_MODEL=MiniMaxAI/MiniMax-M3
NEBIUS_DEEPSEEK_MODEL=deepseek-ai/DeepSeek-V4-Flash
NEBIUS_JUDGE_MODEL=nvidia/Nemotron-3_5-Lightning
NEBIUS_CALL_TIMEOUT_MS=90000
```

## Run

```bash
npm run dev
```

Open [http://localhost:5173/](http://localhost:5173/).

The API server runs on port `8790` by default (see `.env`).

## Usage

1. Enter a natural-language business pitch in the bottom dock.
2. Answer each shark's questions round by round.
3. Review shark reactions, scores, and interest levels after each answer.
4. After the final round, read offers/passes and the deal memo.
5. Optionally send one counter-offer before closing the session.

Example pitch:

```text
I run a social media agency for local restaurants. We do content shoots, reels, ads, and influencer collabs. We made $18k revenue last month with 42% margin, have 11 recurring clients, and want $150k to hire editors and build an AI reporting dashboard.
```

## API Endpoints

- `GET /api/health` — backend health and model config
- `POST /api/room/start` — create an interactive shark room
- `POST /api/room/:id/answer` — submit the user's answer for the active round
- `POST /api/room/:id/counter` — send one founder counter-offer
- `GET /api/reports` — saved reports and dashboard summary
- `GET /api/reports/:id` — saved report JSON

See [agent.md](./agent.md) for full architecture, data models, and testing notes.

## Test

```bash
npm run check
node scripts/visual-3d-check.mjs
node scripts/visual-interaction-check.mjs
node scripts/visual-result-check.mjs
```
