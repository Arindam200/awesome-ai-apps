---
name: implement
description: Drive a single workshop ticket through the inner SWE↔Tester loop. Resolves the ticket from `implement_yourself/tasks/`, creates an `implementing/from-scratch` branch (a fixed default — not derived from the ticket; subsequent tickets stack on top), launches the software-engineer agent to implement it, then routes by archetype — Tester runs on logic tickets, orchestrator spot-checks the SWE's AC walk on glue/bootstrap tickets, fast-path file existence check on docs tickets (Tester HARD-OFF). Loops on FAIL up to 3 times, moves the file to `tasks/done/`, then commits directly with `git commit -m`. Stops after one ticket — the human reviews the commit, talks through it, then re-invokes for the next ticket. Trigger when the user types `/implement`, asks to "implement task NNN", says "pick up the next ticket", or otherwise wants to ship one workshop ticket under supervision.
disable-model-invocation: true
argument-hint: [task-ref-or-description]
---

# Implement Mode — Workshop Single-Ticket Implementation Loop

A workshop-specialized adaptation of squid's `/day` skill. Drives **one** pre-groomed ticket from `implement_yourself/tasks/NNN-slug.groomed.md` through:

```
new feature branch → SWE implements (+ AC walk on glue tickets) → verifier (Tester on logic tickets, orchestrator spot-check on glue tickets) → orchestrator moves file to tasks/done/ → orchestrator commits directly with `git commit -m` → report to human
```

After the report, **the session ends**. The human reviews the commit, talks the workshop audience through what happened, optionally amends or pushes, then types `/implement next` (or `/implement NNN`) to pick up the following ticket.

You are the **orchestrator** — a MANAGER, not an implementer. You do NOT write code, run `make` targets, or read changed files for review yourself. You launch agents, enforce the Tester gate, and finalize the ticket (branch + done-move + commit).

## E2E smoke tests

The Makefile exposes three end-to-end targets that double as smoke tests. Most tickets name one of them in their Acceptance Criteria as the verification target:

- **`make test-research-workflow`** — exercises the Deep Research MCP server end-to-end on the dataset seed. Default smoke test for any research-side ticket (#001–#010, #013).
- **`make test-writing-workflow`** — exercises the LinkedIn Writer MCP server end-to-end on the dataset guideline + prebuilt research. Default smoke test for any writing-side ticket (#011, #014–#019).
- **`make test-end-to-end`** — runs research + writing back-to-back on a dataset sample. Use for cross-cutting tickets (#020 Opik wiring, #024 README, anything that integrates both servers).

When a ticket does not explicitly name a target, infer the right one from the affected server. Bootstrap tickets (`make run-research-server` / `make run-writing-server`) are the exception — those boot-and-kill checks are not smoke tests.

## Critical rules

- **Never rubber-stamp the Tester's (or SWE's, on glue tickets) report.** When the verifier says PASS, re-read each Acceptance Criterion in the ticket and confirm the report's evidence is real (file path, command output excerpt, Python expression result). REJECT and re-launch if not.
- **`/implement` is single-shot per ticket.** After step 7, end the session. Do not auto-pick the next ticket.
- **Commit directly with `git commit -m`.** The orchestrator hand-crafts a one-line commit message from the ticket title (`feat: {Title} (#NNN)` or `docs: {Title} (#NNN)` for README tickets) — we no longer route through `/commit-commands:commit` to save an LLM round-trip.
- **One ticket per invocation.** No batching. If the user asks for multiple tickets, decline and tell them to invoke `/implement` again per ticket.
- **No worktree isolation.** The branch is created in the human's working tree; the SWE works directly there so the audience can watch the diff evolve.
- **`make eval-online` is BANNED.** It hits production and burns budget. Never run it — not on the SWE side, not on the Tester side, not for any ticket (especially anything after #023 where it might be implied). Allowed eval targets are `make eval-dev`, `make eval-test`, `make upload-eval-dataset`. If a ticket explicitly names `eval-online`, push back to the human before proceeding.

---

## Step 1 — Resolve the ticket

`$ARGUMENTS` may be:

| Form | Example | Resolution |
|---|---|---|
| Numeric (1–3 digits) | `1`, `04`, `024` | Zero-pad to 3 digits, glob `implement_yourself/tasks/0NN-*.groomed.md`. Exactly one match expected. |
| Slug | `register-research-tool-shells` | Glob `implement_yourself/tasks/*-{slug}.groomed.md`. |
| Path | `implement_yourself/tasks/003-implement-analyze-youtube-video.groomed.md` | Use as-is after verifying it exists. |
| The literal `next` | `next` | List `implement_yourself/tasks/*.groomed.md` (excluding `done/`), sort, take the lowest-numbered. |
| Empty | (none) | Ask the human: "Which task? (e.g. `1`, `004`, `next`, or a slug.)" Wait for the response. |

If the resolved file is already under `tasks/done/`, refuse: "Ticket {NNN-slug} is already shipped. Did you mean `/implement next`?"

If multiple files match (rare with the slug case), list them and ask the human to disambiguate.

Once resolved:

- Read the ticket front matter (the Title line and the `Tags:`, `Depends on:`, `Blocks:` block). Note: the `Status:` line is no longer flipped to `done` — `tasks/done/` membership is the only "done" signal — so don't trust or update it.
- For each ID in `Depends on:` (excluding `None`), check that the dependency is in `tasks/done/`. If a dependency is still pending, warn the human but proceed if they confirm — workshop attendees may sometimes intentionally take tickets out of order.
- Classify the ticket archetype (drives the step-5 routing). Three archetypes — pick the one that matches:
  - **docs** — README-only tickets (IDs {009, 019, 024}) or any ticket whose Tags contain `docs` and whose Scope only writes/edits markdown documentation. **Tester is HARD-OFF** under any condition — never launch it on a docs ticket. AC walk is also dropped; verification = `ls` + non-empty check by the orchestrator.
  - **glue/bootstrap** — IDs in {001, 006, 007, 008, 011, 016, 017, 018}, OR any ticket whose Scope only registers MCP prompts/resources, only adds skill files, or only bootstraps a server skeleton. Tester skipped; SWE provides an AC walk; orchestrator spot-checks it.
  - **logic** — anything else (tools with `working_dir`, budgets, Pydantic I/O, image tool, eval harness, Opik wiring). The Tester runs as today.
- Surface a 2–3 sentence framing back to the human:
  > "Resolved to **{NNN-slug}** — {Title}. {1-sentence scope summary from the ticket's first paragraph}. Verification target: `{make target named in the ticket}`. Archetype: **{docs|glue|logic}** — {Tester off, fast-path file existence check | Tester off, orchestrator spot-checks SWE AC walk | starting the SWE↔Tester loop}."

Proceed without blocking.

---

## Step 2 — Create the feature branch (only if currently on `main`)

The branch name is the **fixed default `implementing/from-scratch`** — it is **not** derived from the ticket filename. Every ticket reuses the same long-lived branch, so commits stack on top of each other (typical workshop flow: 24+ commits on one branch by the end). The static name means: ticket #001 creates the branch; tickets #002 onward detect they're already on `implementing/from-scratch` and reuse it without a new `git checkout -b`.

If the human pre-checked out their own branch (e.g. `implementing/from-my-idea`) before invoking `/implement`, respect that — the "not on main" path below covers it.

First, detect the current branch:

```bash
CURRENT=$(git rev-parse --abbrev-ref HEAD)
git status --short
```

Then branch on the value:

- **`CURRENT == main`** — create and check out the default branch:
  ```bash
  git checkout -b implementing/from-scratch
  ```
  This is the typical first-ticket flow: human starts the workshop on `main`, types `/implement 1`, gets the default branch.
- **`CURRENT != main`** — **do not create a new branch.** Stay on the current branch and reuse it. Log to the human:
  > "Already on `{CURRENT}` (not `main`). Reusing this branch — the new commit will land on top of any existing work."
  This covers the two main workshop scenarios:
  1. Tickets #002 onward — `CURRENT == implementing/from-scratch` from the prior ticket; just stack on top.
  2. The human pre-checked out a custom branch name (`implementing/from-my-idea`, `workshop-demo`, etc.) before the first invocation — reuse it as their long-lived branch.
  Skip the `git checkout -b` entirely — there is nothing to do.

Edge cases (apply only to the `main` path above):

- **Branch already exists** (re-running `/implement 1` from `main` after the user manually deleted their checkout but not the branch ref): the `git checkout -b` will fail. Prompt the human "Branch `implementing/from-scratch` already exists. Reuse it (`r`) or recreate (`d`)?" — default to reuse (`git checkout implementing/from-scratch`).
- **Working tree is dirty on `main`**: surface `git status --short` to the human and ask whether to stash, commit on `main` first, or abort. Do not silently `git stash` — the workshop human needs to see the state.

This step is the orchestrator's responsibility. Do not delegate to the SWE.

---

## Step 3 — Create a visible TaskList

Use `TaskCreate` to make progress inspectable.

**Logic ticket** (4 items):

- `[SWE] implement {NNN-slug}` (in_progress immediately)
- `[QA] verify {NNN-slug}` — blocked by SWE
- `[Done] move ticket to tasks/done/` — blocked by QA
- `[Commit] git commit on implementing/from-scratch` — blocked by Done

**Glue/bootstrap ticket** (3 items — Tester is skipped):

- `[SWE] implement + AC walk {NNN-slug}` (in_progress immediately)
- `[Done] spot-check + move ticket to tasks/done/` — blocked by SWE
- `[Commit] git commit on implementing/from-scratch` — blocked by Done

**Docs ticket** (3 items — Tester HARD-OFF, no AC walk):

- `[SWE] write docs {NNN-slug}` (in_progress immediately)
- `[Done] confirm file(s) exist + move ticket to tasks/done/` — blocked by SWE
- `[Commit] git commit on implementing/from-scratch` — blocked by Done

No parallel branches. Mark items complete as each step finishes.

---

## Step 4 — Launch the SWE agent

```
Agent(
  subagent_type="software-engineer",
  prompt="""Implement ticket {NNN-slug}.

  Working directory: {repo-root}/implement_yourself/
  Ticket path: implement_yourself/tasks/{NNN-slug}.groomed.md

  Read implement_yourself/CLAUDE.md and the ticket first. Follow your role definition.

  IMMUTABLE scaffolding (do NOT modify): Makefile, pyproject.toml, .python-version,
  .env.example, scripts/, src/writing/profiles/*.md, LICENSE, AGENTS.md, CLAUDE.md,
  and any file already inside tasks/done/. The ticket's "Out of scope" section may
  list more.

  Run make format-fix && make lint-fix until clean (we no longer run the `*-check`
  pair — `lint-fix` exits non-zero on unfixable issues, which is sufficient).
  Then run the e2e smoke-test Make target named in the ticket (one of
  `test-research-workflow`, `test-writing-workflow`, `test-end-to-end` for most
  tickets; bootstrap tickets use `run-research-server` / `run-writing-server`;
  eval tickets use `eval-dev` / `eval-test` / `upload-eval-dataset`) and copy
  the output into your hand-off — verifiers will trust this excerpt and not
  re-run the target, so include the final status line.

  **`make eval-online` is BANNED.** Never run it. If a ticket names it, stop
  and escalate to the orchestrator before proceeding.

  Ticket archetype: **{docs|glue|logic}** (resolved by the orchestrator in step 1).
  - On **logic** tickets: hand off to the Tester. Files touched, format/lint
    output, e2e command + output excerpt, "READY FOR QA".
  - On **glue/bootstrap** tickets: the Tester is skipped. Your hand-off must
    include a complete **AC walk** — for every Acceptance Criterion, give
    PASS + concrete evidence (file path you `cat`'d, Python expression you
    ran with output, command excerpt, `ls` output). The orchestrator
    spot-checks your AC walk in lieu of a Tester pass.
  - On **docs** tickets: the Tester is HARD-OFF and the AC walk is dropped.
    Just write the docs file(s) named in the ticket. Hand off with: file
    path(s) created/edited, line counts (`wc -l`), and a one-line confirmation
    that the content matches the ticket's outline. No format/lint, no e2e,
    no AC walk required. The orchestrator confirms the file exists + is
    non-empty and commits.

  DO NOT commit. DO NOT move files to tasks/done/. The orchestrator handles both."""
)
```

Wait for completion. Mark `[SWE]` complete in the TaskList.

---

## Step 5 — Launch the Tester agent (logic tickets only)

**Skip this step on glue/bootstrap tickets** — the SWE's AC walk + the orchestrator's spot-check is the verification.

**HARD-OFF on docs tickets.** Never launch the Tester on a ticket classified as `docs` in step 1, regardless of edge cases or last-minute doubts. Docs tickets get a fast-path: SWE writes the file → orchestrator confirms `ls` returns a real path with non-empty content → commit. No Tester, no AC walk, no spot-check beyond file existence. If you're tempted to launch the Tester "just to be safe" on a docs ticket, don't — re-classify the ticket as glue/bootstrap or logic in step 1 instead.

For logic tickets, launch the Tester:

```
Agent(
  subagent_type="tester",
  prompt="""QA ticket {NNN-slug}.

  Working directory: {repo-root}/implement_yourself/
  Ticket path: implement_yourself/tasks/{NNN-slug}.groomed.md

  SWE hand-off: {full SWE message, verbatim}

  Read implement_yourself/CLAUDE.md and the ticket first. Follow your role definition.

  Headline duty (workshop mode): walk every Acceptance Criterion with concrete
  evidence. **Trust the SWE's happy-path e2e excerpt — do not re-run the Make
  target.** The Gemini-heavy e2e is the slowest step in the loop and we already
  paid for it once.

  Adversarial pass policy: at most 1 break path, only when the ticket implements
  new logic with branching behaviour (tools with `working_dir`, budgets, Pydantic
  I/O, image tool, eval harness, Opik wiring). For glue tickets (prompt
  registration, resource registration, README, skill files, bootstrap) skip the
  adversarial pass entirely — the AC walk is the verification.

  For each AC: PASS with concrete evidence (file path, command output excerpt,
  Python expression result) or FAIL with reason.

  Verdict: PASS or FAIL."""
)
```

Wait for completion.

---

## Step 6 — Handle the Tester verdict

### Docs tickets — fast-path verification

For docs tickets the spot-check is just a file existence + non-empty check. Skip the full AC re-read.

```bash
ls -la implement_yourself/path/to/README.md   # confirm exists
wc -l implement_yourself/path/to/README.md    # confirm non-empty (>10 lines)
```

If both succeed, accept and proceed to step 7. If the file is missing or empty, re-launch the SWE with the gap. Don't second-guess content quality — that's what the human review of the commit is for.

### Logic + glue tickets — spot-check the AC walk

**Spot-check before accepting** — re-read the ticket's Acceptance Criteria. The verifier is the **Tester** on logic tickets and the **SWE's hand-off AC walk** on glue/bootstrap tickets (since the Tester was skipped in step 5).

For each criterion marked PASS, confirm:

- Evidence is real (a Make target output line, a file path that exists, a Python expression with output, an `ls`/`cat` excerpt).
- The e2e excerpt in the SWE hand-off is credible (right Make target, non-error final line, not fabricated from training data).
- On logic tickets: the 1 break path has a real command + output excerpt.
- On glue/bootstrap tickets: every AC has direct evidence in the SWE's hand-off (no Tester to lean on — the SWE is the only signal).
- No criterion was skipped or hand-waved as "covered by other criteria."

Common rubber-stamp red flags (REJECT and re-launch the verifier with the gap as feedback — the SWE on glue tickets, the Tester on logic tickets):

- The Tester fabricated an e2e excerpt rather than quoting the SWE's. (Look for "I ran `make test-...`" without a corresponding entry in the SWE hand-off — that's a re-run we explicitly told them to skip *and* a likely fabrication.)
- AC requiring a runtime file (e.g. `post.md exists`) marked PASS without a `ls`/`cat` excerpt.
- AC requiring a budget-cap behavior marked PASS without showing both the success and the `budget_exceeded` payload.
- A logic-ticket break path marked PASS without an output excerpt.
- A glue-ticket AC asserting "prompt is listable" / "resource is readable" / "skill YAML parses" / "README links resolve" marked PASS without showing the `uv run python -c "..."`, `mcp.list_prompts()`, `cat`, or markdown-link probe that proves it.

Outcomes:

- **PASS (verified).** Mark `[QA]` complete (logic tickets) — there is no `[QA]` task on glue tickets, so just proceed to step 7.
- **FAIL or PASS-but-rubber-stamped.** Re-launch the SWE with concrete feedback (the failing AC, evidence gaps, suggested fixes). Then re-run step 5 (logic tickets) or re-spot-check (glue tickets).
  ```
  Agent(
    subagent_type="software-engineer",
    prompt="Verification failed on ticket {NNN-slug}. Concrete feedback: {failed AC + evidence gaps + fixes}. Apply the fixes, re-run make format-fix && make lint-fix, re-run the e2e target, hand off again. (Glue/bootstrap tickets: re-emit the AC walk with the missing evidence. Docs tickets: write the missing file content; orchestrator will re-run the file existence check.)"
  )
  ```

### Cap: 3 FAIL cycles per ticket

If the Tester FAILs the same ticket three times without a PASS, stop the pipeline:

- Mark `[QA]` as still in_progress in the TaskList.
- Surface `USER ACTION REQUIRED` with:
  - The ticket ID and title.
  - The last Tester report (verdict + reasons).
  - The last SWE hand-off summary.
  - A suggestion: "The loop is not converging. Consider editing the ticket's spec or pairing on the implementation manually before re-invoking `/implement`."
- End the session. Do **not** mark the ticket done. Do **not** move the file. Do **not** commit. The branch from step 2 is left in place for the human to inspect.

---

## Step 7 — Move file + commit + report

Once verification is PASS *and* you've spot-checked the evidence:

### 7a. Move the file to `tasks/done/`

`tasks/done/` membership is the only "done" signal — we no longer flip the `Status: pending` frontmatter line, and we keep the `.groomed.md` suffix as-is to avoid an extra rename round-trip.

```bash
mkdir -p implement_yourself/tasks/done
git mv implement_yourself/tasks/{NNN-slug}.groomed.md implement_yourself/tasks/done/{NNN-slug}.groomed.md
```

If `git mv` fails because the file isn't tracked yet, fall back to `mv` — the commit step below picks it up via `git add`.

### 7b. Mark `[Done]` complete in the TaskList

### 7c. Commit directly with `git commit`

We hand-craft the commit message from the ticket title — no `/commit-commands:commit` round-trip. Pick the type from the ticket archetype:

- `feat:` — implementation tickets (logic, MCP tools, server bootstraps, prompt/resource registration, skill files).
- `docs:` — README-only tickets (#009, #019, #024) or any ticket whose Tags contain `docs`.

Subject template: `<type>: {Title} (#NNN)` — match the existing repo log (`feat: Add the /write-post Claude Code skill (#018)`, `docs: Author the LinkedIn Writer README (#019)`).

```bash
git add -A
git commit -m "feat: {Title} (#NNN)"   # or docs: ... for README tickets
```

(Workshop scope justifies `git add -A`: only the SWE's source edits and the `git mv` from 7a are in the working tree; the SWE was forbidden from touching anything else.)

If the commit fails (pre-commit hook, signing gate, etc.), surface the error to the human and stop. Do **not** retry with `--no-verify` or `-c commit.gpgsign=false` — those require explicit human authorization.

After the commit lands:

- Verify with `git log --oneline -1` (the new commit should be the tip of the current branch — typically `implementing/from-scratch`).
- Verify with `git status --short` (working tree should be clean).

Mark `[Commit]` complete in the TaskList.

### 7d. Final summary block to the human

Print a single markdown block:

```markdown
## /implement complete — {NNN-slug}: {Title}

**Branch:** `{current branch — `implementing/from-scratch` by default}` ({N} commits ahead of `main`).
**Archetype:** {logic | glue/bootstrap | docs}. {Tester ran | Tester skipped — verified via SWE AC walk + orchestrator spot-check | Tester HARD-OFF — verified via `ls` + `wc -l`}.
**Files changed** ({N}): `path/to/a.py`, `path/to/b.py`, …
**E2E command:** `make {target}` — passed (per SWE excerpt).
**Format/lint:** `make format-fix && make lint-fix` — passed.

**Acceptance criteria:**
- [x] AC1 — evidence: `…`
- [x] AC2 — evidence: `…`
- …

**Ticket moved to:** `implement_yourself/tasks/done/{NNN-slug}.groomed.md`.
**Commit:** `{shortsha} {commit subject}`.

**Working tree is clean.** Review the commit (`git show HEAD`), talk the audience through it, optionally amend or push, then run `/implement next` to pick up the following ticket.
```

End the session. Do **not** invoke `/implement` recursively. Do **not** pick the next ticket. Do **not** push — pushing is the human's call.

---

## Notes

- **No retry caps on lint/format.** If the SWE's lint output is dirty after one pass, the SWE re-runs `make format-fix && make lint-fix` itself (per its role definition); the orchestrator does not police that.
- **No PM grooming, no PR Reviewer, no On-Call.** Tickets are already groomed; the human plays the diff-review and runtime-watching roles in real time.
- **Dependencies are advisory.** The orchestrator warns when a `Depends on:` ticket is still pending but does not block — workshop pacing sometimes calls for taking a ticket out of order to demonstrate a concept.
- **`tasks/done/` is sacred.** The orchestrator is the only writer. The SWE and Tester agents are forbidden from touching `tasks/done/`. The file's `.groomed.md` suffix is preserved on move — membership in `done/` is the only "done" signal we maintain.
- **The skill is tied to `implement_yourself/`.** All paths are rooted there. If the user invokes `/implement` from a different cwd, the skill should `cd` into `implement_yourself/` before launching agents.
- **Branch + commit are the orchestrator's job.** The SWE and Tester remain forbidden from running `git checkout`, `git add`, `git commit`, `git push`, or `git rm`. The orchestrator owns both endpoints of the git lifecycle for a ticket.
- **No push, no PR.** `/implement` stops at the local commit. Pushing the branch and opening a PR (if desired) is the human's manual step. This matches the workshop's "pause-per-task, narrate, then move on" cadence.
