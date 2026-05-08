# Deep Research MCP Server

A FastMCP server that gives any MCP-compatible agent (Claude Code, Cursor, etc.) the ability to conduct deep web research with Exa and summarize YouTube transcripts with Nebius-hosted LLMs.

## How It Works

```
User: "Research how AI agents work in production"
         │
         ▼
┌─────────────────────────────────────────────────────┐
│              Agent (Claude Code)                     │
│                                                      │
│  The agent decides WHAT to research and WHEN.        │
│  It has the ReAct loop — the MCP server just         │
│  provides capabilities.                              │
│                                                      │
│  1. Breaks topic into queries                        │
│  2. Calls tools, reads results                       │
│  3. Identifies gaps, researches more                 │
│  4. Compiles final output                            │
└──────────┬──────────────┬──────────────┬─────────────┘
           │              │              │
           ▼              ▼              ▼
   ┌──────────────┐ ┌───────────┐ ┌────────────────┐
   │deep_research │ │analyze_   │ │compile_        │
   │              │ │youtube_   │ │research        │
   │ Exa answer   │ │video      │ │                │
   │ search +     │ │           │ │ Aggregates all │
   │ citations    │ │ Captions  │ │ results into   │
   │              │ │ + Nebius  │ │ research.md    │
   │ Returns:     │ │ (native   │ │                │
   │ answer +     │ │ video     │ │                │
   │ sources      │ │ analysis) │ │                │
   └──────────────┘ └───────────┘ └────────────────┘
```

## MCP Primitives

| Type | Name | Purpose |
|------|------|---------|
| **Tool** | `deep_research` | Calls Exa answer search. Returns answer + sources |
| **Tool** | `analyze_youtube_video` | Fetches public YouTube captions/transcripts and summarizes them with Nebius |
| **Tool** | `compile_research` | Aggregates all results from `.memory/` into `research.md` |
| **Prompt** | `research_workflow` | Guides the agent on how to use the 3 tools in sequence |
| **Resource** | `resource://config/research` | Exposes server config: model names, version, feature flags |

All tools also take a `working_dir` parameter (the research session directory).

## Architecture

**Call chain:** `routers/ → tools/ → app/ → utils/`

- **`routers/`** — Registers tools/prompts/resources with FastMCP (the MCP interface layer)
- **`tools/`** — Tool implementations: validate inputs, call business logic, save/load files
- **`app/`** — Business logic: Exa search and Nebius transcript summarization
- **`utils/`** — Shared helpers used by `app/` and `tools/` (Nebius, Exa, file I/O, markdown, logging, Okahu)

```
src/research/
├── server.py                      # FastMCP entry point
│
├── routers/                       # MCP registration layer
│   ├── tools.py                   #   registers 3 tools
│   ├── prompts.py                 #   registers 1 prompt
│   └── resources.py               #   registers 1 resource
│
├── tools/                         # Tool implementations (thin wrappers)
│   ├── deep_research_tool.py      #   orchestrates Exa search
│   ├── analyze_youtube_video_tool.py  #   orchestrates video analysis
│   └── compile_research_tool.py   #   orchestrates markdown compilation
│
├── app/                           # Business logic
│   ├── research_handler.py        #   Exa search call
│   ├── youtube_handler.py         #   YouTube transcript + Nebius summarization
│   └── research_file_handler.py   #   markdown assembly
│
├── config/                        # Configuration
│   ├── settings.py                #   Pydantic Settings (env vars, models)
│   ├── constants.py               #   file/folder name constants
│   └── prompts.py                 #   LLM prompt templates
│
├── models/
│   └── schemas.py                 #   ResearchSource, ResearchResult
│
└── utils/
    ├── llm.py                     #   Nebius/LangChain and Exa helpers
    ├── file_utils.py              #   file I/O helpers
    ├── markdown_utils.py          #   collapsible sections, markdown assembly
    ├── logging.py                 #   logging setup
    └── okahu_utils.py             #   Okahu/Monocle observability integration
```

## Tool Response Pattern

Tools both **return results to the agent** and **write to disk** for accumulation:

```
deep_research("How do AI agents work?")
  │
  ├─→ Returns to agent:  { answer: "...", sources: [...], output_path: "..." }
  │   (agent sees the content immediately and can reason about it)
  │
  └─→ Writes to disk:    .memory/research_results.json  (appends)
      (so compile_research can later read ALL results)
```

- `deep_research` — returns the answer + sources AND appends to `.memory/research_results.json`
- `analyze_youtube_video` — returns the transcript AND saves to `.memory/transcripts/{id}.md`
- `compile_research` — reads everything from `.memory/`, assembles `research.md`

The agent gets results immediately to reason about gaps. The files are for accumulation so `compile_research` can combine everything at the end.

## Data Flow

During a research session, intermediate data is stored in `.memory/` within the working directory:

```
working_dir/
├── .memory/
│   ├── research_results.json      # Accumulated results from deep_research calls
│   └── transcripts/
│       └── {video_id}.md          # One file per analyzed YouTube video
└── research.md                    # Final output (created by compile_research)
```

## Configuration

Set via environment variables (or `.env` file):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEBIUS_API_KEY` | Yes | — | Nebius AI Studio API key |
| `EXA_API_KEY` | Yes | — | Exa API key for real-time research |
| `LLM_MODEL` | No | `meta-llama/Llama-3.3-70B-Instruct` | Default Nebius-hosted model |
| `YOUTUBE_TRANSCRIPTION_MODEL` | No | `meta-llama/Llama-3.3-70B-Instruct` | Nebius model for transcript summarization |
| `OKAHU_API_KEY` | No | — | Enables Okahu Cloud trace export |
| `MONOCLE_EXPORTER` | No | `file` | Monocle exporters, e.g. `file,okahu` |
| `OKAHU_WORKFLOW_RESEARCH` | No | `research-agent` | Okahu/Monocle workflow name |

## Observability

When Monocle tracing is enabled, tool invocations and LLM calls are traced locally and optionally sent to [Okahu Cloud](https://www.okahu.ai/). You can see:

- Full LLM input/output for each call
- Latency per tool and per model request
- Tool call sequence and workflow spans
- Token usage
