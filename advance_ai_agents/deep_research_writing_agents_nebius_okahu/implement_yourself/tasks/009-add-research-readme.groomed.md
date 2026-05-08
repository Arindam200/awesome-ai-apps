# Author the Deep Research Agent README

Status: pending
Tags: `docs`, `readme`, `research`
Depends on: #008
Blocks: #020

## Scope

Replace `implement_yourself/src/research/README.md` with a complete, self-contained reference for installing, configuring, and running the Deep Research MCP server — covering Make targets, the MCP server itself, and the `/research` skill.

The README must be **purely technical**: prerequisites, install, env vars, run instructions, MCP usage. **No** marketing, sales pitch, jokes, or "what you'll learn" framing — that material lives in the parent README. Treat the reader as a developer who already knows why they're here.

### File to (over)write

- `implement_yourself/src/research/README.md` — currently a large file inherited verbatim from the parent. Rewrite to match the structure below.

### Required sections (in order)

1. **`# Deep Research MCP Server`** title + one-paragraph summary (what it does, what it uses: FastMCP + Exa search + Nebius transcript summarization).
2. **`## Prerequisites`** — bulleted list:
   - Python ≥ 3.12 (link to `.python-version`).
   - `uv` for env + dependency management.
   - GNU Make.
   - Nebius API key.
   - Exa API key.
   - Optional Okahu Cloud API key.
   - An MCP-compatible harness (Claude Code, Cursor, etc.).
3. **`## Installation`** — `uv sync`, what it does, mention the `.venv` it creates.
4. **`## Configuration`** — copy `.env.example` to `.env`, fill in the keys. Document each env var:
   - `NEBIUS_API_KEY` (required).
   - `EXA_API_KEY` (required).
   - `LLM_MODEL` (optional).
   - `YOUTUBE_TRANSCRIPTION_MODEL` (optional).
   - `OKAHU_API_KEY` (optional, enables cloud trace export — wired in task #020).
   - `MONOCLE_EXPORTER` (optional).
   - `OKAHU_WORKFLOW_RESEARCH` (optional, defaults to `research-agent`).
   - `LOG_LEVEL` (optional, integer; defaults to `INFO` aka `20`).
5. **`## Architecture overview`** — borrow the layered diagram from the parent README (`routers/ → tools/ → app/ → utils/`) and the `src/research/` directory tree. May include the high-level "Agent ↔ MCP server" ASCII diagram from the parent README. Keep it short — this README is not a tutorial.
6. **`## MCP primitives`** — table mapping `Type | Name | Purpose` for the three tools, one prompt, one resource. Same shape as the parent README.
7. **`## Running the server`** —
   - `make run-research-server` (stdio transport for harness integration).
   - Direct test via the e2e fixture: `make test-research-workflow`.
   - Mention the `.mcp.json` entry that drives auto-launch from harnesses.
8. **`## Using the `/research` skill`** — short paragraph explaining:
   - How to invoke (`/research <topic>` or natural language triggers).
   - Where output lands (`outputs/{slug}/research.md`).
   - How the slug is derived.
9. **`## Make targets`** — list every research-related target with one-line description: `run-research-server`, `test-research-workflow`, `format-fix/lint-fix/format-check/lint-check`.
10. **`## Output layout`** — the working-directory tree (parent README has it):
    ```
    working_dir/
    ├── .memory/
    │   ├── exploration_state.json
    │   ├── research_results.json
    │   └── transcripts/{video_id}.md
    └── research.md
    ```
11. **`## Exploration budget`** — one short paragraph: "The agent may run at most 6 exploration calls (`deep_research` + `analyze_youtube_video` combined) per session before being forced to call `compile_research`. The cap is enforced server-side via `.memory/exploration_state.json` and reset by `compile_research`. Each successful response carries `call`, `max_calls`, `calls_remaining` so the agent can self-pace."
12. **`## Observability (optional)`** — note that `MONOCLE_EXPORTER=file,okahu` plus `OKAHU_API_KEY` enables Okahu Cloud tracing, but only after task #020 wires it in.

### Notes

- DO NOT include the parent project's marketing / "From our Course" / GIF / call-to-action sections.
- DO NOT duplicate the workflow tutorial from the workshop slides — link to the parent README if cross-reference is needed (relative path: `../../README.md`).
- Keep the README under ~250 lines if reasonable.

## Acceptance Criteria

- [ ] `src/research/README.md` exists with the 12 sections above (or equivalent ordering); each section has at least one paragraph or bulleted list.
- [ ] No marketing / sales / joke language present (reviewer to verify by skim).
- [ ] Every env var the project actually reads is documented.
- [ ] Every Make target related to research is listed.
- [ ] Markdown renders cleanly (no broken links, no orphan code blocks).
- [ ] `make format-check && make lint-check` pass (no Python touched).

## User Stories

### Story: New attendee installs the project

1. Attendee clones the repo and `cd implement_yourself/`.
2. Reads `src/research/README.md`.
3. Follows Prerequisites → Installation → Configuration in order; lands at a working `make run-research-server`.
4. Reads "Running the server" + "Using the /research skill" and executes the workflow successfully without consulting any other doc.

### Story: Existing engineer evaluates the system

1. Engineer skims the README, sees the architecture diagram and the MCP primitives table.
2. Decides whether to integrate. The architecture is clear in under 5 minutes of reading.

---

Blocked by: #008
