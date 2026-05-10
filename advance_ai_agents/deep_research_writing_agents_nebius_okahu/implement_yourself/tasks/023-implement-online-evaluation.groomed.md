# Implement online evaluation with generated posts and Okahu traces

Status: pending
Tags: `evals`, `okahu`, `monocle`, `online`, `generate-on-the-fly`
Depends on: #022
Blocks: #024

## Scope

Add the online evaluation path: generate a post on the fly using the writing workflow, then score it with `BinaryLLMJudgeMetric`. This emulates a production "evaluate the model end-to-end" pipeline. F1 is computed when labels exist in the chosen split; otherwise the run still traces sample scores for inspection.

Wire it through `make eval-online`.

### Files to modify

- `implement_yourself/src/writing/evals/evaluation.py` — add `run_online_evaluation(...)` alongside `run_evaluation`.

### Public interface

```python
def run_online_evaluation(
    split: str = "online_test",
    workers: int = 1,
    nb_samples: int | None = None,
) -> float | None: ...
```

Internally:

1. `items = load_online_eval_items(split)`.
2. If `nb_samples` is set, slice the item list.
3. Instantiate `metric = BinaryLLMJudgeMetric()`.
4. For each sample, wrap the generation and judge call in `trace_span("eval.online.sample", ...)`.
5. Generate the post:
   ```python
   import asyncio
   from writing.app.generate_post import generate_post

   generated = asyncio.run(generate_post(sample["guideline"], sample.get("research", "")))
   generated_post = generated.post.content
   ```
6. Score the generated post with the local judge.
7. Emit `eval.online.score` with `split`, `slug`, `model`, `expected_label`, `actual_label`, `score`, `critique`, and `reason`.
8. If at least one result has an expert label, compute F1 and emit `eval.online.summary` with `f_score`.
9. If no labels exist, return `None` after emitting `eval.online.summary` with `f_score=None`.

### Notes

- `workers=1` by default because generation is heavy and a single trace tree is easier to inspect in Okahu.
- Increasing workers can reduce wall-clock time but may split spans across traces depending on thread context propagation.
- The function must tolerate splits other than `online_test`. For `dev_evaluator` and `test_evaluator`, labels exist and F1 is computable.

### `scripts/run_online_evaluation.py`

Parses `--split` (choices: `dev_evaluator | test_evaluator | online_test`), `--workers`, and `--nb-samples`. Calls `setup_logging`, `configure_okahu`, then `run_online_evaluation(...)`. Prints `F1 score (judge vs expert labels): {f1:.3f}` if F1 returned, else `Online evaluation complete (no F1 — simulating real-world usage).`

## Acceptance Criteria

- [ ] `make eval-online` runs end-to-end. Logs show per-sample generation, then judge scoring.
- [ ] Okahu Cloud shows `eval.online.sample`, `eval.online.score`, and `eval.online.summary` spans under `writing-workflow`.
- [ ] For unlabeled runs, the function returns `None` and the script prints the no-F1 message.
- [ ] For `--split dev_evaluator`, the function returns a float and the script prints F1.
- [ ] The online evaluation respects `--nb-samples 1`.
- [ ] Cost is bounded by using `--nb-samples` while iterating.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Attendee runs the online judge

1. Attendee runs `make eval-online`.
2. Okahu Cloud shows the generated post workflow, judge score, and critique.
3. Console prints F1 when labels exist, otherwise the no-F1 message.

### Story: Attendee runs online evaluation against a labeled split

1. Attendee runs `uv run python scripts/run_online_evaluation.py --split dev_evaluator --workers 1 --nb-samples 5`.
2. Harness generates five posts on the fly, judges each, computes F1 vs the dev labels.
3. Console prints `F1 score (judge vs expert labels): 0.667` or the current score.

### Story: One-sample sanity test

1. Attendee runs `uv run python scripts/run_online_evaluation.py --split online_test --nb-samples 1`.
2. Harness generates one post and judges it, verifying wiring in a bounded run.

---

Blocked by: #022.
