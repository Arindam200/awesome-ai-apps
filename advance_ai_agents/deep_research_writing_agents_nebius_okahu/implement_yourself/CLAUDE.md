# Project

We are building an educative workshop teaching people how to build AI systems by implementing a hybrid AI system containing a Deep Research Agent and a Writing Workflow, both served as MCP servers and connected to a harness such as Claude Code or Cursor.

# Project Root

**`implement_yourself/` is the project root for this workshop project.** When Claude (or Cursor, or any MCP harness) is launched from this directory, all relative paths — `outputs/`, `inputs/`, `tasks/`, `test_logic/`, `scratch_*/`, etc. — resolve under `implement_yourself/`, not under the parent repo. Skills loaded from the parent (e.g. `/research`, `/research-and-write`, `/write-post`) that say "relative to the project root" should be read as relative to **this** directory whenever the harness was opened here. The parent repo's `outputs/` is for the reference implementation; the workshop's outputs belong inside `implement_yourself/outputs/`.

# Project Structure

```
project-root/
├── src/
│   ├── research/              # Deep Research Agent MCP server
│   │   ├── server.py          # FastMCP entry point
│   │   ├── config/            # Settings, constants, prompt templates
│   │   ├── models/            # Pydantic schemas for structured LLM output
│   │   ├── app/               # Business logic handlers
│   │   ├── tools/             # MCP tool implementations
│   │   ├── routers/           # MCP tool, resource, and prompt registration
│   │   └── utils/             # Nebius/LangChain, Exa, file I/O, markdown helpers
│   └── writing/               # LinkedIn Writer MCP server
│       ├── server.py          # FastMCP entry point
│       ├── profiles/          # Shipped markdown profiles (structure, terminology, character)
│       ├── config/            # Settings, constants, prompt templates
│       ├── models/            # Pydantic schemas (Post, Review, Profiles)
│       ├── app/               # Business logic handlers (writer, reviewer, image, profile loader)
│       ├── tools/             # MCP tool implementations
│       ├── routers/           # MCP tool, resource, and prompt registration
│       └── utils/             # Nebius/LangChain, Gemini image, Okahu helpers
├── inputs/                    # Seed and guideline files
├── scripts/                   # Entrypoints and test scripts
└── .env.example               # All supported env vars
```

# Tech Stack

- Data validation and structuring: Pydantic
- Settings: Pydantic Settings
- MCP Server Framework: FastMCP
- CLI: Click
- Logging: Native Python logger (never prints!)
- LLM API: Nebius via LangChain
- Search API: Exa
- Image generation: Gemini
- Observability and evals: Okahu Cloud + Monocle

## Access Documentation
Use the context7 MCP server to find out more about the tech stack usage and good practices.

# Running QA

We use ruff as our formatter and linter.

First always fix the formatting and linting errors with the fix commands:
```
make format-fix
make lint-fix
```
Then, check if there are any errors that couldn't be fixed automatically and fix them:
```
make format-check
make lint-check
```

# Running Code

We manage all the core commands through GNU Make as our command center. File available at @Makefile. Run all the commands with `make ...`

We use uv to manage our Python project such as the virtual environment(s), dependencies, and overall package the project.

Thus, use uv to run any custom command that is not present in the @Makefile, but uses Python: `uv run python ...`

## Fallback when `make` is not installed

Some environments (fresh WSL, minimal containers, corporate dev images) ship without GNU Make. **Do not block on a missing `make`** — every target in the Makefile is a thin wrapper around a one-line `uv run ...` invocation. When `make <target>` fails with `command not found: make`, open the `Makefile`, find the target's recipe, and run the underlying command directly. Example: `make test-research-workflow` becomes `uv run python scripts/test_research_workflow.py --working-dir test_logic --iterations 2` (after the two `mkdir -p` / `cp` setup lines also shown in the recipe). The Makefile's `export PYTHONPATH=./src/` and `include .env` are already handled by `uv run` reading the project's environment + `.env`, so no extra shell setup is needed.

# Three Ways to Invoke the MCP Server Logic

The Deep Research and LinkedIn Writer servers can be exercised through three different paths, each with a different purpose. Pick the one that matches what you're trying to do.

## 1. Make targets — smoke / debugging tests

Run the workflow logic directly from the terminal, bypassing the MCP layer. Fastest feedback loop for debugging the underlying handlers and the project's canonical e2e smoke tests.

- `make test-research-workflow` — Deep Research workflow on the dataset seed.
- `make test-writing-workflow` — LinkedIn Writer workflow on the dataset guideline + prebuilt research.
- `make test-end-to-end` — research + writing chained on a dataset sample.
- `make run-dataset-writing` / `make run-dataset-writing-no-image` — full dataset sweep.

Use these when iterating on app logic, reproducing a bug, or verifying a ticket — they hit the same handlers as the MCP tools but skip transport.

## 2. MCP servers via `.mcp.json` — full functionality

Run the servers as MCP processes and connect them to a harness (Claude Code, Cursor, etc.). This is the production path and exposes every tool, prompt, and resource the servers register.

- `make run-research-server` — boots the Deep Research MCP server (stdio).
- `make run-writing-server` — boots the LinkedIn Writer MCP server (stdio).
- The harness connects automatically via @.mcp.json (working directory must be the harness root).

Use this when demonstrating the full system, calling tools by name (`mcp__deep-research__deep_research`, etc.).

## 3. Skills — ease of use

High-level slash commands that orchestrate the MCP tools end-to-end with sensible defaults.

- `/research` — runs deep research on a topic via the Deep Research MCP server.
- `/write-post` — drafts a LinkedIn post via the LinkedIn Writer MCP server.
- `/research-and-write` — chains both into the full pipeline.
- `/implement` — drives one workshop ticket through the SWE↔Tester loop using Claude Code subagents (workshop-only).
- `/implement-universal` — harness-agnostic twin of `/implement`. Same SWE↔Tester loop, but runs in a single conversation context by adopting role files from `.claude/skills/implement-universal/agents/` instead of dispatching subagents. Use this in Cursor, Windsurf, plain Anthropic SDK loops, or any harness that doesn't support Claude Code's `Task` tool.

Use these when you want the workflow without remembering tool names. Ideal for everyday use.
