---
name: implement-universal
description: Harness-agnostic version of `/implement`. Drives a single workshop ticket through the SWE→Tester loop in ONE conversation, with the role prompts bundled as `agents/software-engineer.md` and `agents/tester.md` instead of being launched as subagents. Resolves the ticket from `implement_yourself/tasks/`, creates an `implementing/from-scratch` branch (a fixed default — not derived from the ticket; subsequent tickets stack on top), adopts the software-engineer role to implement, then switches to the tester role to verify (logic tickets only). Loops on FAIL up to 3 times, moves the file to `tasks/done/`, then commits directly with `git commit -m`. Stops after one ticket. Trigger when the user types `/implement-universal`, asks to "implement task NNN without subagents", or is running in a harness (Cursor, Windsurf, plain Claude API client, etc.) that doesn't support Claude Code's `Task` tool.
disable-model-invocation: true
argument-hint: [task-ref-or-description]
---

# Implement Universal — Single-Context Workshop Implementation Loop

This is the harness-agnostic twin of `/implement`. It is functionally identical, but instead of dispatching subagents via Claude Code's `Task` tool, it instructs **you** to adopt two distinct roles in sequence:

1. **Software Engineer phase** — read `agents/software-engineer.md` and execute it end-to-end.
2. **Tester phase** — read `agents/tester.md` and execute it as a fresh reviewer of the SWE phase's output.

Use this skill when running in any harness that does NOT have Claude Code's subagent dispatch (Cursor, Windsurf, generic MCP clients, plain Anthropic SDK loops, etc.). If you are running inside Claude Code, prefer `/implement` — the subagent isolation gives you a more independent Tester verdict.

```
new feature branch → SWE role implements (+ AC walk on glue tickets) → role switch → Tester role verifies (logic tickets only) → orchestrator moves file to tasks/done/ → orchestrator commits directly with `git commit -m` → report to human
```

After the report, **the session ends**. The human reviews the commit, talks the workshop audience through what happened, optionally amends or pushes, then re-invokes for the next ticket.

You are the **orchestrator** for steps 1–3, 6, and 7. For steps 4 and 5 you adopt the bundled roles. The orchestrator is a MANAGER — it does NOT write code, run `make` targets, or read changed files for review on its own behalf. That work happens *inside* the role phases.

## Single-context limitation — read this first

Without subagent isolation, the SWE and Tester phases share one conversation history. That means:

- **The Tester phase will see the SWE phase's reasoning.** Bias toward confirming your own implementation is real. Counteract it: when you switch to the Tester role, treat the SWE hand-off message as if a stranger wrote it, and verify every AC against the file system / command output, not against your memory of what you implemented.
- **Tool budget is shared.** Format/lint/e2e runs from the SWE phase are visible; do not re-run them in the Tester phase (the Tester role explicitly trusts the SWE's e2e excerpt).
- **Context window is finite.** On a long ticket, the SWE phase may consume substantial context. If you notice context pressure, summarize the SWE work in a compact hand-off message rather than carrying every intermediate edit forward into the Tester phase.

The role files (`agents/software-engineer.md`, `agents/tester.md`) are the contract. Re-read each one *at the start* of its phase so you reset to the right mindset; do not skim from memory.

## E2E smoke tests

The Makefile exposes three end-to-end targets that double as smoke tests. Most tickets name one of them in their Acceptance Criteria as the verification target:

- **`make test-research-workflow`** — exercises the Deep Research MCP server end-to-end on the dataset seed. Default smoke test for any research-side ticket (#001–#010, #013).
- **`make test-writing-workflow`** — exercises the LinkedIn Writer MCP server end-to-end on the dataset guideline + prebuilt research. Default smoke test for any writing-side ticket (#011, #014–#019).
- **`make test-end-to-end`** — runs research + writing back-to-back on a dataset sample. Use for cross-cutting tickets (#020 Okahu/Monocle tracing, #024 README, anything that integrates both servers).

When a ticket does not explicitly name a target, infer the right one from the affected server. Bootstrap tickets (`make run-research-server` / `make run-writing-server`) are the exception — those boot-and-kill checks are not smoke tests.

## Critical rules

- **Never rubber-stamp the Tester phase's (or SWE phase's, on glue tickets) report.** When the verifier says PASS, re-read each Acceptance Criterion in the ticket and confirm the report's evidence is real (file path, command output excerpt, Python expression result). REJECT and re-run the relevant phase if not. This is doubly important in single-context mode, where the Tester verdict is less independent.
- **`/implement-universal` is single-shot per ticket.** After step 7, end the session. Do not auto-pick the next ticket.
- **Commit directly with `git commit -m`.** Hand-craft a one-line commit message from the ticket title (`feat: {Title} (#NNN)` or `docs: {Title} (#NNN)` for README tickets).
- **One ticket per invocation.** No batching. If the user asks for multiple tickets, decline and tell them to invoke `/implement-universal` again per ticket.
- **No worktree isolation.** The branch is created in the human's working tree; the SWE phase works directly there so the audience can watch the diff evolve.
- **`make eval-online` is BANNED.** It hits production and burns budget. Never run it — not in the SWE phase, not in the Tester phase, not for any ticket. Allowed eval targets are `make eval-dev` and `make eval-test`. If a ticket explicitly names `eval-online`, push back to the human before proceeding.

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

If the resolved file is already under `tasks/done/`, refuse: "Ticket {NNN-slug} is already shipped. Did you mean `/implement-universal next`?"

If multiple files match (rare with the slug case), list them and ask the human to disambiguate.

Once resolved:

- Read the ticket front matter (the Title line and the `Tags:`, `Depends on:`, `Blocks:` block). The `Status:` line is no longer flipped — `tasks/done/` membership is the only "done" signal — so don't trust or update it.
- For each ID in `Depends on:` (excluding `None`), check that the dependency is in `tasks/done/`. If a dependency is still pending, warn the human but proceed if they confirm — workshop attendees may sometimes intentionally take tickets out of order.
- Classify the ticket archetype (drives the step-5 routing):
  - **docs** — README-only tickets (IDs {009, 019, 024}) or any ticket whose Tags contain `docs` and whose Scope only writes/edits markdown documentation. **Tester is HARD-OFF** — never enter the Tester phase on a docs ticket. AC walk is also dropped; verification = `ls` + non-empty check by the orchestrator.
  - **glue/bootstrap** — IDs in {001, 006, 007, 008, 011, 016, 017, 018}, OR any ticket whose Scope only registers MCP prompts/resources, only adds skill files, or only bootstraps a server skeleton. Tester phase skipped; SWE phase provides an AC walk; orchestrator spot-checks it.
  - **logic** — anything else. The Tester phase runs.
- Surface a 2–3 sentence framing back to the human:
  > "Resolved to **{NNN-slug}** — {Title}. {1-sentence scope summary}. Verification target: `{make target}`. Archetype: **{docs|glue|logic}** — {Tester off, fast-path file existence check | Tester off, orchestrator spot-checks SWE AC walk | starting the SWE→Tester loop in single-context mode}."

Proceed without blocking.

---

## Step 2 — Create the feature branch (only if currently on `main`)

The branch name is the **fixed default `implementing/from-scratch`** — it is **not** derived from the ticket filename. Every ticket reuses the same long-lived branch, so commits stack on top of each other (typical workshop flow: 24+ commits on one branch by the end). Ticket #001 creates the branch; tickets #002 onward detect they're already on `implementing/from-scratch` and reuse it. If the human pre-checked out their own branch (e.g. `implementing/from-my-idea`) before invoking `/implement-universal`, respect that — the "not on main" path below covers it.

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
- **`CURRENT != main`** — **do not create a new branch.** Stay on the current branch and reuse it. Log to the human:
  > "Already on `{CURRENT}` (not `main`). Reusing this branch — the new commit will land on top of any existing work."
  This covers tickets #002 onward (already on `implementing/from-scratch`) and the "human pre-checked out a custom branch" case.

Edge cases (apply only to the `main` path):

- **Branch already exists**: the `git checkout -b` will fail. Prompt the human "Branch `implementing/from-scratch` already exists. Reuse it (`r`) or recreate (`d`)?" — default to reuse (`git checkout implementing/from-scratch`).
- **Working tree is dirty on `main`**: surface `git status --short` and ask whether to stash, commit on `main` first, or abort. Do not silently `git stash`.

This step is the orchestrator's responsibility. Do NOT defer it to the SWE phase.

---

## Step 3 — Create a visible TaskList

Use your harness's task-tracking tool (`TaskCreate` in Claude Code, or an equivalent visible checklist) to make progress inspectable. If your harness has no task tool, write a plain markdown checklist in the chat.

**Logic ticket** (4 items):

- `[SWE phase] implement {NNN-slug}` (in_progress immediately)
- `[Tester phase] verify {NNN-slug}` — blocked by SWE
- `[Done] move ticket to tasks/done/` — blocked by Tester
- `[Commit] git commit on implementing/from-scratch` — blocked by Done

**Glue/bootstrap ticket** (3 items — Tester phase is skipped):

- `[SWE phase] implement + AC walk {NNN-slug}` (in_progress immediately)
- `[Done] spot-check + move ticket to tasks/done/` — blocked by SWE
- `[Commit] git commit on implementing/from-scratch` — blocked by Done

**Docs ticket** (3 items — Tester HARD-OFF, no AC walk):

- `[SWE phase] write docs {NNN-slug}` (in_progress immediately)
- `[Done] confirm file(s) exist + move ticket to tasks/done/` — blocked by SWE
- `[Commit] git commit on implementing/from-scratch` — blocked by Done

No parallel branches. Mark items complete as each phase finishes.

---

## Step 4 — Software Engineer phase

**Adopt the SWE role.** Open `implement_yourself/.agents/skills/implement-universal/agents/software-engineer.md` (or, if that path resolves through a `.claude/skills/` symlink, the equivalent path under your harness) and read it end-to-end. That file is your role definition for this phase — it overrides any default coding instinct.

Then execute the SWE workflow it describes against this ticket:

- Working directory: `{repo-root}/implement_yourself/`
- Ticket path: `implement_yourself/tasks/{NNN-slug}.groomed.md`
- Ticket archetype: **{docs|glue|logic}** (resolved by the orchestrator in step 1).
- Immutable scaffolding (do NOT modify): `Makefile`, `pyproject.toml`, `.python-version`, `.env.example`, `scripts/`, `src/writing/profiles/*.md`, `LICENSE`, `AGENTS.md`, `CLAUDE.md`, and any file already inside `tasks/done/`. The ticket's "Out of scope" section may list more.
- Run `make format-fix && make lint-fix` until clean. Then run the e2e smoke-test Make target named in the ticket and copy the output into the hand-off — the Tester phase will trust this excerpt and not re-run the target.
- **`make eval-online` is BANNED.** Never run it.

Produce a SWE hand-off message in this conversation that follows the format in `software-engineer.md` for the matching archetype:

- **logic** → Tester-bound hand-off (files changed, format/lint excerpt, e2e excerpt, per-AC implementation summary, "READY FOR QA").
- **glue/bootstrap** → orchestrator-bound hand-off with a complete **AC walk** (PASS + concrete evidence per AC, "READY FOR ORCHESTRATOR SPOT-CHECK").
- **docs** → minimal hand-off (file paths + line counts + outline-match note, "READY FOR FILE-EXISTENCE CHECK").

DO NOT commit. DO NOT move files to `tasks/done/`. The orchestrator handles both in step 7.

When the SWE hand-off is complete, mark the `[SWE phase]` task complete and proceed.

---

## Step 5 — Tester phase (logic tickets only)

**Skip this step on glue/bootstrap tickets** — the SWE's AC walk + the orchestrator's spot-check is the verification.

**HARD-OFF on docs tickets.** Never enter the Tester phase on a docs ticket. Docs tickets get a fast-path: SWE writes the file → orchestrator confirms `ls` returns a real path with non-empty content → commit.

For logic tickets, **switch roles.** This is the most fragile transition in single-context mode — do it deliberately:

1. **Reset your mindset.** Stop thinking like the implementer. The diff you just produced is now an *artifact under review*, not your work product.
2. **Re-read the role file.** Open `implement_yourself/.agents/skills/implement-universal/agents/tester.md` and read it end-to-end. Do not skim from memory — the rubric matters.
3. **Re-read the ticket.** Treat the Acceptance Criteria as a contract you are auditing for the first time.
4. **Treat the SWE hand-off as input.** It is the message you would have received from a separate agent. Quote-confirm the format/lint excerpt and the e2e excerpt; do not re-run the Make target.
5. **Run the role's workflow.** Walk every AC with concrete evidence (file paths, command output, Python expressions). For tickets with branching logic, run the at-most-1 adversarial break path the role file selects. Skip the adversarial pass for tickets where the role file marks it skipped.

Produce a QA Report in the format `tester.md` specifies, ending in **VERDICT: PASS** or **VERDICT: FAIL**.

**Anti-rubber-stamp safeguard for single-context mode.** Before you write `VERDICT: PASS`, ask yourself: "If a stranger handed me this SWE hand-off, would I find the evidence sufficient — or am I leaning on what I remember implementing?" If the answer is the latter, run the verification command yourself (`ls`, `cat`, `uv run python -c "..."`) and quote its output in the report. Memory is not evidence.

When the QA report is complete, mark the `[Tester phase]` task complete and proceed to step 6.

---

## Step 6 — Handle the Tester verdict

### Docs tickets — fast-path verification

For docs tickets the spot-check is just a file existence + non-empty check. Skip the full AC re-read.

```bash
ls -la implement_yourself/path/to/README.md   # confirm exists
wc -l implement_yourself/path/to/README.md    # confirm non-empty (>10 lines)
```

If both succeed, accept and proceed to step 7. If the file is missing or empty, re-enter the SWE phase with the gap. Don't second-guess content quality — that's what the human review of the commit is for.

### Logic + glue tickets — spot-check the AC walk

**Spot-check before accepting** — re-read the ticket's Acceptance Criteria. The verifier is the **Tester phase output** on logic tickets and the **SWE phase's hand-off AC walk** on glue/bootstrap tickets.

For each criterion marked PASS, confirm:

- Evidence is real (a Make target output line, a file path that exists, a Python expression with output, an `ls`/`cat` excerpt).
- The e2e excerpt in the SWE hand-off is credible (right Make target, non-error final line, not fabricated from training data).
- On logic tickets: the 1 break path has a real command + output excerpt.
- On glue/bootstrap tickets: every AC has direct evidence in the SWE's hand-off.
- No criterion was skipped or hand-waved as "covered by other criteria."

Common rubber-stamp red flags (REJECT and re-run the appropriate phase with the gap as feedback):

- The Tester phase fabricated an e2e excerpt rather than quoting the SWE's. (Look for "I ran `make test-...`" without a corresponding entry in the SWE hand-off.)
- AC requiring a runtime file marked PASS without a `ls`/`cat` excerpt.
- AC requiring a budget-cap behavior marked PASS without showing both the success and the `budget_exceeded` payload.
- A logic-ticket break path marked PASS without an output excerpt.
- A glue-ticket AC asserting "prompt is listable" / "resource is readable" / "skill YAML parses" / "README links resolve" marked PASS without showing the proof command.

Outcomes:

- **PASS (verified).** Mark `[Tester phase]` complete (logic tickets) and proceed to step 7.
- **FAIL or PASS-but-rubber-stamped.** Re-enter the SWE phase with concrete feedback (failing AC, evidence gaps, suggested fixes). Re-read `agents/software-engineer.md` to reset, then apply the fixes, re-run `make format-fix && make lint-fix`, re-run the e2e target, and produce a new hand-off. Then re-run step 5 (logic tickets) or re-spot-check the AC walk (glue tickets).

### Cap: 3 FAIL cycles per ticket

If the Tester phase FAILs the same ticket three times without a PASS, stop the pipeline:

- Mark `[Tester phase]` as still in_progress in the TaskList.
- Surface `USER ACTION REQUIRED` with:
  - The ticket ID and title.
  - The last Tester report (verdict + reasons).
  - The last SWE hand-off summary.
  - A suggestion: "The loop is not converging. Consider editing the ticket's spec or pairing on the implementation manually before re-invoking `/implement-universal`."
- End the session. Do **not** mark the ticket done. Do **not** move the file. Do **not** commit. The branch from step 2 is left in place for the human to inspect.

---

## Step 7 — Move file + commit + report

Once verification is PASS *and* you've spot-checked the evidence:

### 7a. Move the file to `tasks/done/`

```bash
mkdir -p implement_yourself/tasks/done
git mv implement_yourself/tasks/{NNN-slug}.groomed.md implement_yourself/tasks/done/{NNN-slug}.groomed.md
```

If `git mv` fails because the file isn't tracked yet, fall back to `mv` — the commit step picks it up via `git add`.

### 7b. Mark `[Done]` complete in the TaskList

### 7c. Commit directly with `git commit`

Pick the type from the ticket archetype:

- `feat:` — implementation tickets (logic, MCP tools, server bootstraps, prompt/resource registration, skill files).
- `docs:` — README-only tickets (#009, #019, #024) or any ticket whose Tags contain `docs`.

Subject template: `<type>: {Title} (#NNN)`.

```bash
git add -A
git commit -m "feat: {Title} (#NNN)"   # or docs: ... for README tickets
```

If the commit fails (pre-commit hook, signing gate, etc.), surface the error to the human and stop. Do **not** retry with `--no-verify` or `-c commit.gpgsign=false` — those require explicit human authorization.

After the commit lands:

- Verify with `git log --oneline -1`.
- Verify with `git status --short` (working tree should be clean).

Mark `[Commit]` complete in the TaskList.

### 7d. Final summary block to the human

Print a single markdown block:

```markdown
## /implement-universal complete — {NNN-slug}: {Title}

**Branch:** `{current branch — `implementing/from-scratch` by default}` ({N} commits ahead of `main`).
**Mode:** single-context (no subagent isolation).
**Archetype:** {logic | glue/bootstrap | docs}. {Tester phase ran | Tester phase skipped — verified via SWE AC walk + orchestrator spot-check | Tester HARD-OFF — verified via `ls` + `wc -l`}.
**Files changed** ({N}): `path/to/a.py`, `path/to/b.py`, …
**E2E command:** `make {target}` — passed (per SWE excerpt).
**Format/lint:** `make format-fix && make lint-fix` — passed.

**Acceptance criteria:**
- [x] AC1 — evidence: `…`
- [x] AC2 — evidence: `…`
- …

**Ticket moved to:** `implement_yourself/tasks/done/{NNN-slug}.groomed.md`.
**Commit:** `{shortsha} {commit subject}`.

**Working tree is clean.** Review the commit (`git show HEAD`), talk the audience through it, optionally amend or push, then run `/implement-universal next` to pick up the following ticket.
```

End the session. Do **not** invoke `/implement-universal` recursively. Do **not** pick the next ticket. Do **not** push — pushing is the human's call.

---

## Notes

- **No retry caps on lint/format.** If lint output is dirty after one pass in the SWE phase, the SWE re-runs `make format-fix && make lint-fix` itself; the orchestrator does not police that.
- **No PM grooming, no PR Reviewer, no On-Call.** Tickets are already groomed; the human plays the diff-review and runtime-watching roles in real time.
- **Dependencies are advisory.** The orchestrator warns when a `Depends on:` ticket is still pending but does not block.
- **`tasks/done/` is sacred.** The orchestrator is the only writer. The SWE and Tester phases are forbidden from touching `tasks/done/`.
- **The skill is tied to `implement_yourself/`.** All paths are rooted there. If invoked from a different cwd, `cd` into `implement_yourself/` before reading role files.
- **Branch + commit are the orchestrator's job.** The SWE and Tester phases remain forbidden from running `git checkout`, `git add`, `git commit`, `git push`, or `git rm`.
- **No push, no PR.** `/implement-universal` stops at the local commit. Pushing the branch and opening a PR is the human's manual step.
- **Why this version exists.** Some harnesses (Cursor, Windsurf, plain Anthropic SDK loops) don't have Claude Code's subagent dispatch. This skill ports the SWE↔Tester pattern into a single-context flow so workshop attendees on any harness can run the loop. The trade-off is weaker Tester independence — counteract it with the anti-rubber-stamp safeguard in step 5.
