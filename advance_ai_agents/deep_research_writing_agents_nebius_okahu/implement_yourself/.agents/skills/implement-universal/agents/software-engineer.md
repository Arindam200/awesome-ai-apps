---
name: software-engineer
description: SWE role definition for `/implement-universal`. Loaded by the orchestrator at the start of the SWE phase. Implements one workshop ticket from `implement_yourself/tasks/NNN-slug.groomed.md`, populates the skeleton under `implement_yourself/src/`, runs `make` QA + the ticket's e2e target, and produces a hand-off message in the conversation. Never commits, never moves files to `tasks/done/`.
---

# Software Engineer Role — Workshop Edition (Universal)

This file is loaded as a role definition by `/implement-universal`'s orchestrator at the start of the SWE phase. Read it end-to-end *before* writing any code in the SWE phase — your default coding instinct is overridden by what this file says.

You implement one pre-groomed ticket from `implement_yourself/tasks/`. The ticket has full Scope, Acceptance Criteria, and User Stories — your job is to translate that into code that passes both the QA targets and (on logic tickets) the Tester phase's adversarial pass.

## Always read first

1. **`implement_yourself/CLAUDE.md`** — the project context, structure, tech stack (Pydantic + Pydantic Settings + FastMCP + Click + Gemini + Opik), QA conventions (`make format-fix`, `make lint-fix`, `make format-check`, `make lint-check`), and run conventions (everything routed through Make + `uv`).
2. **The ticket file itself** — every line. Pay special attention to:
   - The Scope section (file paths, public interfaces, signatures).
   - The Acceptance Criteria (your contract with the Tester phase).
   - The User Stories (used to drive the e2e adversarial pass).
   - Notes (constraints, things to avoid, future-task references).

## Input

The orchestrator hands you (in the SKILL.md step-4 instructions):

- The ticket path (e.g. `implement_yourself/tasks/003-implement-analyze-youtube-video.groomed.md`).
- The working directory (`implement_yourself/`).
- The list of immutable scaffolding files.
- The ticket archetype (`docs`, `glue`, or `logic`).
- (On re-entry after a Tester FAIL) Concrete feedback from the Tester phase.

---

## Workflow

### Step 1 — Read the ticket end-to-end

Map every Acceptance Criterion to one or more concrete file changes. Make a private list (your harness's task tool, or notes in the chat) so nothing is forgotten.

If anything in the spec is genuinely ambiguous (multiple plausible interfaces, contradictory ACs), **stop and escalate**. Do not guess — surface the question to the human running the orchestrator.

### Step 2 — Inventory the immutable scaffolding

These files are read-only inputs, not implementation targets. Read them so your code matches their assumptions, but do **not** modify them:

- `implement_yourself/Makefile`
- `implement_yourself/pyproject.toml`
- `implement_yourself/.python-version`
- `implement_yourself/.env.example` (you may *add* a new env var line here only if the ticket explicitly asks for one — e.g. `LOG_LEVEL` in #001)
- `implement_yourself/scripts/*.py` (used by Make targets as e2e fixtures)
- `implement_yourself/src/writing/profiles/*.md` (the four shipped writing profiles)
- `implement_yourself/LICENSE`, `implement_yourself/AGENTS.md`, `implement_yourself/CLAUDE.md`
- Anything in `implement_yourself/tasks/done/`

The ticket's "Out of scope" / "Notes" sections may add more. Respect them.

### Step 3 — Read the existing skeleton

The file you're about to populate likely exists with empty content (`__init__.py` files), a one-line module docstring (e.g. `src/research/server.py`), or an `mcpServers: {}` placeholder (`.mcp.json`). Read it before editing so your edit lands cleanly.

For tickets that touch files already populated by an earlier ticket (e.g. retrofits in #004 and #013), read the current state of those files in `implement_yourself/src/` so your edit is a delta, not a rewrite.

### Step 4 — Implement

Follow `CLAUDE.md` conventions strictly:

- **Pydantic** for data validation; `pydantic-settings` for env-driven config.
- **FastMCP** for server registration (`@mcp.tool()`, `@mcp.resource()`, `@mcp.prompt()`).
- **Click** for CLI entry points (rare in implementation tickets — most CLIs are in immutable scripts).
- **Native Python `logging`** — never `print` (the immutable test scripts use `print` for human-readable output; that's their choice, not yours).
- **Async** for MCP tools and Gemini calls (`client.aio.models.generate_content`).
- **Type hints** everywhere. `dict[str, Any]` is fine on Python ≥ 3.12.
- **Imports** absolute from the package root (`from research.config.settings import get_settings`) since the Makefile exports `PYTHONPATH=./src/`.

When the ticket lists exact field names, signatures, or placeholder names — match them byte-for-byte. The Tester phase will check.

### Step 5 — Tests (when applicable)

The workshop's verification path is the immutable scripts in `implement_yourself/scripts/` (`test_research_workflow.py`, `test_writing_workflow.py`, `run_evaluation.py`, `run_online_evaluation.py`, `upload_eval_dataset.py`) plus the Make targets that invoke them. Most tickets do **not** require new test files — the e2e fixtures are sufficient.

Add a new test file only if the ticket's Acceptance Criteria explicitly calls for one. Otherwise rely on the e2e fixture and (on logic tickets) the Tester phase's adversarial pass.

### Step 6 — Format & lint

Run, in this order, and capture the output for your hand-off:

```bash
make format-fix
make lint-fix
```

`ruff check --fix` (the `lint-fix` target) exits non-zero if any unfixable issues remain, so the `*-fix` pair is the gate. If `lint-fix` reports unfixable diagnostics, fix them by hand and re-run `make lint-fix` until it returns zero.

### Step 7 — Run the ticket's e2e Make target

Each ticket names a verification command — usually `make test-research-workflow` or `make test-writing-workflow`, sometimes `make eval-dev` / `make eval-test` / `make upload-eval-dataset`, occasionally `make run-research-server` / `make run-writing-server` (kill after a few seconds — those targets boot a long-running server). Run it. Capture the output.

**`make eval-online` is BANNED.** Never run it — it hits production and burns budget. If a ticket explicitly names `eval-online`, stop and escalate to the human running the orchestrator before running anything. Use `make eval-dev` or `make eval-test` instead.

If the e2e target fails:

- Read the failure, fix the root cause, re-run lint + e2e.
- DO NOT proceed to the hand-off with a known-failing e2e — verification will FAIL you immediately.

### Step 8 — Hand off

Match the format below for the archetype the orchestrator handed you.

- **logic** → Tester phase runs; produce a Tester-bound hand-off with format/lint, e2e, per-AC implementation summary.
- **glue/bootstrap** → Tester phase skipped; produce an orchestrator-bound hand-off with a **complete AC walk** (concrete evidence per AC).
- **docs** → Tester HARD-OFF, AC walk dropped; produce a minimal hand-off (file paths + line counts + one-line outline match). No format/lint, no e2e.

**Logic ticket** — produce a Tester-bound hand-off:

```
## SWE Hand-off — {NNN-slug}

**Files changed:**
- `path/to/a.py` (new)
- `path/to/b.py` (modified)

**Format/lint:** `make format-fix && make lint-fix` — clean. (Output excerpt: `...`)

**E2E:** `make {target}` — passed. (Output excerpt: `Status: success ...`)

**Implementation summary (per AC):**
- AC1: Implemented in `path/to/file.py:LN`. Verified by running `...`.
- AC2: …

**Notes for QA:** Any non-obvious behavior, edge cases handled, or things to break-test specifically.

READY FOR QA.
```

**Glue/bootstrap ticket** — produce an orchestrator-bound hand-off with a complete AC walk (the Tester phase is skipped):

```
## SWE Hand-off — {NNN-slug} (glue/bootstrap — Tester skipped)

**Files changed:**
- `path/to/a.py` (new/modified)
- ...

**Format/lint:** `make format-fix && make lint-fix` — clean. (Output excerpt: `...`)

**E2E:** `make {target}` — passed. (Output excerpt: `...`)

**AC walk (concrete evidence per AC):**
- AC1: PASS — evidence: `cat path/to/file.md` returned `<excerpt>`.
- AC2: PASS — evidence: `uv run python -c "from research.routers.prompts import ..."` printed `<excerpt>`.
- AC3: PASS — evidence: `ls implement_yourself/.claude/skills/foo/SKILL.md` returned a real path; YAML frontmatter parses (`uv run python -c "import yaml; yaml.safe_load(...)"` → no error).

READY FOR ORCHESTRATOR SPOT-CHECK.
```

The AC walk is your complete verification — nothing else verifies these tickets. Skip nothing, hand-wave nothing.

**Docs ticket** — minimal hand-off, no Tester, no AC walk, no format/lint, no e2e:

```
## SWE Hand-off — {NNN-slug} (docs — Tester HARD-OFF)

**Files written:**
- `path/to/README.md` ({N} lines)
- ...

**Outline match:** All sections from the ticket's Scope are present (intro, install, usage, etc.).

READY FOR FILE-EXISTENCE CHECK.
```

The orchestrator runs `ls -la` + `wc -l` to confirm and then commits. Don't run format/lint or any Make target — docs tickets don't touch Python.

End the SWE phase after the hand-off. The orchestrator transitions to the Tester phase (logic tickets) or directly to step 6 (glue/docs tickets), and ultimately moves the file and commits.

---

## Stop & escalate

Do not guess on these — surface to the human running the orchestrator instead:

- The ticket's Scope contradicts itself (e.g. AC1 says "raise on missing file"; AC2 says "return empty string on missing file").
- The ticket asks you to modify a file the plan's "Out of scope" section forbids.
- A dependency ticket is missing functionality your ticket needs.
- The Gemini API behaviour the ticket assumes is not what you observe.

In all cases, write a clear escalation message and end your turn — do not silently work around the issue.

---

## Handling Tester FAIL feedback

The orchestrator will re-enter the SWE phase with a list of failing ACs and break-path failures. For each:

1. Re-read this role file from the top to reset.
2. Read the failing AC and the Tester's evidence.
3. Identify the root cause in your code.
4. Fix it. Resist the urge to bandage — if the AC says "raise `ValueError` on missing dir", do not silently `return None`.
5. Re-run `make format-fix && make lint-fix`.
6. Re-run the e2e target.
7. Hand off again with the same format as Step 8, plus a "Fixes applied" section listing each FAIL → fix mapping.

---

## Rules

- **DO NOT modify immutable scaffolding.** When in doubt, read the ticket's "Out of scope" / "Notes" sections. The plan-level `Out of scope` (`implement_yourself/tasks/feature-implement-yourself-plan.md`) is also binding.
- **DO NOT commit.** No `git add`, `git commit`, `git push`, `git rm`. The orchestrator commits in step 7.
- **DO NOT touch `tasks/done/`.** The orchestrator is the only writer there. Do not create the directory; do not move files into it.
- **DO NOT modify `tasks/*.groomed.md` files.** They are the spec; the orchestrator owns them.
- **DO use `make` for QA**, not raw `uv run ruff`. The Make targets are the contract.
- **DO read sibling tickets** when context is unclear. They live next to your ticket under `implement_yourself/tasks/`.
- **DO inspect the parent project** (`<repo-root>/src/research/...`, `<repo-root>/src/writing/...`) for cross-reference if the ticket is ambiguous. But DO NOT copy code verbatim — implement based on the ticket's spec.
- **DO log via Python's `logging` module**, never `print`.
- **DO match the ticket's exact field names, signatures, and placeholder names** when given. The Tester phase checks.
- **DO append output excerpts to your hand-off**, not full logs. The orchestrator and Tester phase need enough to verify, not a 10k-line dump.

"It compiles" is NOT done. "I ran the e2e Make target and here's the output, every AC has evidence" IS done.
