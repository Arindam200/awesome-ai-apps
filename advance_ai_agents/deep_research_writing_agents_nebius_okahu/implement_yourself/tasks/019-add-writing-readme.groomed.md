# Author the LinkedIn Writer README

Status: pending
Tags: `docs`, `readme`, `writing`
Depends on: #018
Blocks: #020

## Scope

Author `implement_yourself/src/writing/README.md` (currently absent) — a complete, technical reference for installing, configuring, and running the LinkedIn Writer MCP server. Same constraints as the research README in #009: prerequisites, install, env vars, run instructions, MCP usage. **No** marketing, sales, or workshop framing.

### File to create

- `implement_yourself/src/writing/README.md`

### Required sections (in order)

1. **`# LinkedIn Writer MCP Server`** + 1-paragraph summary (what it does: generates LinkedIn posts via an evaluator-optimizer loop with Nebius-hosted text models, plus Gemini image generation; uses FastMCP).
2. **`## Prerequisites`** — Python ≥ 3.12, `uv`, GNU Make, Nebius API key, Gemini API key for images, optional Okahu Cloud account, MCP-compatible harness, **and `make test-research-workflow` already producing a `research.md` (or any other source of `research.md`)**.
3. **`## Installation`** — `uv sync`.
4. **`## Configuration`** — document `NEBIUS_API_KEY`, `GEMINI_API_KEY`, `WRITER_MODEL`, `REVIEWER_MODEL`, `IMAGE_MODEL`, `OKAHU_API_KEY`, `MONOCLE_EXPORTER`, `OKAHU_WORKFLOW_WRITING`, and `LOG_LEVEL`.
5. **`## Architecture overview`** — directory tree of `src/writing/` with the same `routers/ → tools/ → app/ → utils/` call chain. Mention `profiles/` (the four shipped markdown profiles) is part of the package.
6. **`## MCP primitives`** — table mapping `Type | Name | Purpose`:
   - Tool: `generate_post` — generate post + evaluator-optimizer loop.
   - Tool: `edit_post` — review+edit pass driven by human feedback.
   - Tool: `generate_image` — Gemini image generation.
   - Prompt: `linkedin_post_workflow` — the workflow harness instructions.
   - Resource: `config://settings` — server config.
   - Resource: `profiles://all` — the four profiles' markdown content.
7. **`## Running the server`** —
   - `make run-writing-server` (stdio transport).
   - End-to-end test: `make test-writing-workflow` (requires the dataset's seed `_guideline.md` and `_research.md` already present in `test_logic/`).
   - Full research+writing in one go: `make test-end-to-end`.
8. **`## Using the `/write-post` skill`** — invocation, slug derivation, output path.
9. **`## Make targets`** — list every writing-related target with one-line descriptions: `run-writing-server`, `test-writing-workflow`, `test-end-to-end`, `run-dataset-writing`, `run-dataset-writing-no-image`, plus the `format-*` / `lint-*` family.
10. **`## Output layout`** — the directory tree from the workflow prompt:
    ```
    working_dir/
    ├── guideline.md
    ├── research.md
    ├── .memory/
    │   ├── reviews_1.json
    │   └── reviews_2.json
    ├── post_0.md
    ├── post_1.md
    ├── post.md
    └── post_image.png
    ```
11. **`## Profiles`** — short paragraph: the writer is anchored by four markdown profiles in `src/writing/profiles/` (`structure_profile.md`, `terminology_profile.md`, `character_profile.md`, `branding_profile.md`). They are shipped immutably and loaded by `app/profile_loader.py`. To customize voice, edit those files (they are intentionally exposed as part of the package).
12. **`## Observability (optional)`** — `MONOCLE_EXPORTER=file,okahu` plus `OKAHU_API_KEY` enables Okahu Cloud tracing; lands in #020.

### Notes

- DO NOT include the parent project's preview / GIFs / "From our Course" / call-to-action.
- Cross-reference the research README via relative path (`../research/README.md`) where appropriate.
- Keep total length under ~250 lines.

## Acceptance Criteria

- [ ] `src/writing/README.md` exists with all 12 sections (or equivalent).
- [ ] Each env var the writing package reads is documented.
- [ ] All writing-related Make targets are listed.
- [ ] Markdown renders cleanly.
- [ ] No marketing language.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Attendee installs the writing half from scratch

1. Attendee reads `src/writing/README.md`.
2. Follows Prerequisites → Installation → Configuration; runs `make run-writing-server`; the server boots.
3. Reads "Running the server" + "Using the /write-post skill" and successfully generates a post.

### Story: Attendee customizes voice

1. Attendee reads the "Profiles" section, opens `src/writing/profiles/character_profile.md`, edits.
2. Reruns `make test-writing-workflow`. The new post visibly reflects the edited persona.

---

Blocked by: #018
