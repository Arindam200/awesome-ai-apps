# Author the Evals README

Status: pending
Tags: `docs`, `readme`, `evals`, `okahu`
Depends on: #023
Blocks: —

## Scope

Author a self-contained README for the evals subsystem. Same constraints as the prior READMEs: prerequisites, install, env vars, run instructions via Make + scripts. No marketing or workshop framing.

### File to create

- `implement_yourself/src/writing/evals/README.md`

### Required sections

1. **`# LinkedIn Writer — Evaluation Harness`** + one-paragraph summary: local LLM-as-judge scoring, offline F1 vs human labels, online generate-then-judge runs, and optional Okahu/Monocle tracing.
2. **`## Prerequisites`** — Python ≥ 3.12, `uv`, GNU Make, `NEBIUS_API_KEY`, the `datasets/linkedin_paul_iusztin/` directory, and optional `OKAHU_API_KEY` for cloud trace inspection. Mention symlinking the parent dataset when running standalone.
3. **`## Installation`** — `uv sync`.
4. **`## Configuration`** —
   - `NEBIUS_API_KEY` (required for judge/text LLM calls).
   - `REVIEWER_MODEL` (optional).
   - `OKAHU_API_KEY` (optional).
   - `MONOCLE_EXPORTER` (optional, e.g. `file,okahu`).
   - `OKAHU_WORKFLOW_WRITING` (optional, defaults to `writing-workflow`).
5. **`## Concepts`** —
   - **Dataset splits.** `train_evaluator`, `dev_evaluator`, `test_evaluator`, `online_test`.
   - **Offline evaluation.** Reads pre-generated posts; the judge scores each; the harness computes F1 locally.
   - **Online evaluation.** Generates posts on the fly, then judges them. F1 is computed only when labels exist.
   - **F1 alignment.** Measures agreement between LLM judge predictions and human labels.
   - **Okahu traces.** Monocle exports sample and summary spans to Okahu Cloud for inspection.
6. **`## Architecture`** — directory tree of `src/writing/evals/`: `dataset.py`, `metric.py`, `evaluation.py`, `__init__.py`, plus this README.
7. **`## Running the harness`** —
   - `make eval-dev` — offline F1 on the dev split.
   - `make eval-test` — offline F1 on the test split.
   - `make eval-online` — online evaluation.
   - Direct script invocations with `--split`, `--workers`, `--nb-samples`.
8. **`## Inspecting Okahu traces`** — explain that `eval.*.score` spans carry `expected_label`, `actual_label`, `score`, `critique`, and `reason`; summary spans carry `f_score` and `sample_count`.
9. **`## Authoring labeled samples`** — describe adding `label: pass|fail` and `critique` to `datasets/linkedin_paul_iusztin/index.yaml`.
10. **`## Cost considerations`** — each offline sample runs one judge call; each online sample runs a full writing workflow plus a judge call. Use `--nb-samples`.
11. **`## Troubleshooting`** —
    - `F1=0.000 over 0 samples` → no labeled items match the split.
    - `F1=0.000` on one sample → the sample may be a correctly predicted `fail`; positive-class F1 needs positive examples.
    - No Okahu traces → check `OKAHU_API_KEY` and `MONOCLE_EXPORTER=file,okahu`.
    - Online runs are slow → reduce `--nb-samples`.

### Notes

- Do not include legacy eval-platform instructions, dataset upload commands, or external eval-platform dependencies.
- Cross-link the writing README (`../README.md`) and the research README (`../../research/README.md`).

## Acceptance Criteria

- [ ] `src/writing/evals/README.md` exists with the required sections or equivalent coverage.
- [ ] Markdown renders cleanly. Cross-links resolve.
- [ ] Every eval Make target is listed and explained.
- [ ] Every env var the eval subsystem reads is documented.
- [ ] Okahu trace inspection is explained clearly.
- [ ] No legacy eval-platform references remain.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Engineer onboards onto the evals system

1. Engineer reads `src/writing/evals/README.md`.
2. Sets Nebius and optional Okahu config.
3. Runs `make eval-dev`, `make eval-test`, and `make eval-online`.
4. Uses Okahu Cloud to inspect score spans and summary spans.

### Story: Engineer adds a new labeled sample

1. Reads "Authoring labeled samples".
2. Adds an entry to `index.yaml` with `label: fail`, `critique: ...`, and the right `scope`.
3. Reruns `make eval-dev` and observes the new sample's influence on F1.

---

Blocked by: #023.
