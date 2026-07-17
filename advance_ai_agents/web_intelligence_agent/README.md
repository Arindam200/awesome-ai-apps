# Web Intelligence Agent

Web Intelligence Agent turns live web evidence into source-aware intelligence documents.

Ask a plain-English research question, optionally add a URL, and the app collects evidence, reasons over it with Nemotron Ultra on Nebius, verifies gaps and contradictions, saves the run, and creates an editable case-study document for review.

This project runs locally by default. It is not deployed anywhere out of the box; teams that want a hosted web version can customize the deployment, auth, queues, and data-retention model for their environment.

## What It Does

- Collects live web evidence from search results, known URLs, site maps, crawls, or sourced answers.
- Uses NVIDIA Nemotron on Nebius to structure evidence, separate facts from inference, and draft a readable case study.
- Runs the pipeline through a controlled Mastra workflow: `Ask -> Collect -> Reason -> Verify -> Code`.
- Stores runs, generated code, and editable case-study Markdown in SQLite.
- Uses Velt for collaboration surfaces such as comments, presence, notifications, and immutable audit trail.

Web Intelligence Agent is useful for competitor research, product-page analysis, market signals, docs/API change research, pricing checks, and source-aware case-study drafts.

## Tool Stack

| Tool | Use in Web Intelligence Agent |
| --- | --- |
| [Olostep](https://www.olostep.com/) | Live web search, scrape, answers, map, and crawl operations. |
| [Nebius](https://dub.sh/nebius) | OpenAI-compatible endpoint for Nemotron Ultra reasoning and case-study generation. |
| [Mastra](https://mastra.ai/) | Agent and workflow framework for the controlled multi-agent pipeline. |
| [Velt](https://velt.dev/) | Comments, presence, notifications, and immutable audit trail. |
| [Next.js](https://nextjs.org/) | App UI and API routes. |
| SQLite | Run history, generated code, and editable case-study documents. |

## Project Structure

```
web_intelligence_agent/
├── src/
│   ├── app/              # Next.js pages and API routes
│   ├── components/       # UI (SignalForgeApp, VeltWorkspace, etc.)
│   └── lib/              # Core logic: Mastra workflow, DB, Olostep/Nebius/Velt clients
│       ├── mastra.ts     # Agents and webSignalWorkflow
│       ├── olostep.ts    # Olostep search/scrape/crawl tools
│       ├── nebius.ts     # Nemotron reasoning and case-study generation
│       ├── db.ts         # SQLite run and case-study persistence
│       ├── workflow.ts   # Run orchestration entrypoints
│       └── velt.ts       # Collaboration and audit trail
├── public/               # Logos and blog diagrams
├── .env.example
└── package.json
```

## Run Locally

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/advance_ai_agents/web_intelligence_agent
cp .env.example .env
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

The app does not use mock workflow data. Missing keys are shown in setup/status, and run attempts fail with the real missing-key error.

## Environment

Required for workflows:

```bash
OLOSTEP_API_KEY=
OLOSTEP_API_BASE_URL=https://api.olostep.com/v1

NEBIUS_API_KEY=
NEBIUS_BASE_URL=https://api.tokenfactory.us-central1.nebius.com/v1/
NEBIUS_MODEL=nvidia/Nemotron-3-Ultra-550b-a55b
```

Optional for collaboration and audit:

```bash
NEXT_PUBLIC_VELT_CLIENT_ID=
NEXT_PUBLIC_VELT_ORG_ID=
NEXT_PUBLIC_VELT_API_KEY=
NEXT_PUBLIC_VELT_ORGANIZATION_ID=
NEXT_PUBLIC_VELT_DOCUMENT_ID=signals-board

VELT_API_KEY=
VELT_AUTH_TOKEN=
VELT_ORGANIZATION_ID=
VELT_DOCUMENT_ID=signals-board
VELT_ACTIVITY_API_URL=https://api.velt.dev/v2/activities/add
```

Local persistence:

```bash
DATABASE_URL=file:./signalforge.db
```

## How To Use

1. Enter a research request, such as `Research Nebius Token Factory Data Lab as a source-aware case study`.
2. Optionally add a target URL for extraction, such as `https://nebius.com/services/token-factory/data-lab`.
3. Run the workflow.
4. Review the generated brief, evidence, plan, code, case study, audit trail, and history.

## App Tabs

| Tab | What it shows |
| --- | --- |
| Brief | Nemotron-generated summary, signals, confidence, risk/opportunity score, contradictions, gaps, and next query. |
| Evidence | Structured data extracted from the Olostep result and processed by the Nebius reasoning step. |
| Plan | The workflow plan, selected Olostep operation, target URL/query, inferred schema, assumptions, and stage list. |
| Code | Reusable TypeScript for the selected Olostep operation and payload. |
| Case Studies | Editable Markdown case-study documents saved in SQLite, with Velt text comments, presence, and PDF export. |
| Audit Trail | Per-run human and agent activity fetched from Velt. |
| History | Dense summary of previous workflow runs. |

Evidence, Plan, and Code are there to make each run inspectable: Evidence shows what was found, Plan shows why the workflow chose a tool and schema, and Code shows how to repeat the selected collection pattern.

## Under The Hood

The app uses five Mastra agents:

- Signals Planner Agent
- Olostep Evidence Agent
- Nebius Reasoning Agent
- Nebius Verification Agent
- Nebius Case Study Agent

It also registers five Olostep tools:

- `olostepSearchTool`
- `olostepScrapeTool`
- `olostepAnswersTool`
- `olostepMapTool`
- `olostepCrawlTool`

The route layer starts a run, executes `webSignalWorkflow.createRun(...).start(...)`, and polls the saved run state while the workflow updates SQLite and Velt.

## Boundaries

Web Intelligence Agent is a focused local-first project. It intentionally does not implement hosted deployment, scheduling, external destinations, self-healing monitors, account auth, or production queue infrastructure.

To deploy it as a hosted web app, add the infrastructure choices that fit your environment: authentication, server-side job queues, secrets management, database hosting, observability, and retention policies.

## Provider Links

- [Olostep docs](https://docs.olostep.com/)
- [Nebius Token Factory docs](https://dub.sh/nebius)
- [Mastra docs](https://mastra.ai/docs)
- [Velt docs](https://docs.velt.dev/)
- [Next.js docs](https://nextjs.org/docs)
