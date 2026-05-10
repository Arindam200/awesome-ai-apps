# Mastra Starter

A minimal starter for [Mastra](https://mastra.ai) — a TypeScript-first framework for building AI agents, workflows, and RAG pipelines. This starter shows a tool-using agent powered by Nebius Token Factory.

## Features

- TypeScript `Agent` with instructions, a custom tool, and the Vercel AI SDK
- `get-current-time` tool demonstrates structured input/output with Zod
- Nebius Token Factory via `@ai-sdk/openai` (OpenAI-compatible endpoint)
- Interactive CLI via Node's `readline/promises`

## Prerequisites

- Node.js 20+
- Nebius API key — [Nebius Token Factory](https://studio.nebius.ai/)

## Installation

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/starter_ai_agents/mastra_starter

npm install
# or: pnpm install / bun install
```

Create `.env`:

```bash
cp .env.example .env
# set NEBIUS_API_KEY
```

## Usage

```bash
npm run dev
```

### Example Queries

- "What time is it?" (triggers the `get-current-time` tool)
- "Draft a 3-line release note for v0.1."
- "Suggest names for a TypeScript agent framework."

## Technical Details

- **Framework**: `@mastra/core` (TypeScript)
- **Model**: `Qwen/Qwen3-30B-A3B` via Nebius using `@ai-sdk/openai` with custom `baseURL`
- **Tool**: single `createTool` with Zod schemas

## Acknowledgments

- [Mastra](https://mastra.ai)
- [Vercel AI SDK](https://sdk.vercel.ai)
- [Nebius Token Factory](https://studio.nebius.ai/)
