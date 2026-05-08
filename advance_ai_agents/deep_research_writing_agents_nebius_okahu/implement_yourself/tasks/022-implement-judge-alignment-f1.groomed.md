# Implement the offline evaluation harness with local F1 and Okahu traces

Status: pending
Tags: `evals`, `okahu`, `monocle`, `f1`, `alignment`, `harness`
Depends on: #021
Blocks: #023

## Scope

Implement the offline evaluation harness: run `BinaryLLMJudgeMetric` against pre-generated posts in a dataset split, compute F1 between judge predictions and human expert labels in Python, and emit Okahu/Monocle spans for each sample score and the final summary.

This task introduces `writing/evals/evaluation.py`. The metric and local dataset layer (#021) are already in place.

### Files to create

- `implement_yourself/src/writing/evals/evaluation.py`

### Public interface

```python
def run_evaluation(
    split: str = "test_evaluator",
    workers: int = 1,
    nb_samples: int | None = None,
) -> float: ...
```

Internally:

1. `items = load_offline_eval_items(split)`.
2. If `nb_samples` is set, slice `items = items[:nb_samples]`.
3. Instantiate `metric = BinaryLLMJudgeMetric()`.
4. For each sample, wrap the score call in:
   ```python
   with trace_span(
       "eval.offline.sample",
       {"split": split, "slug": sample["slug"], "model": metric._model, "expected_label": sample.get("label")},
   ):
       ...
   ```
5. Score the sample with `metric.score(guideline=..., research=..., output=...)`.
6. Emit a short `eval.offline.score` span with `split`, `slug`, `model`, `expected_label`, `actual_label`, `score`, `critique`, and `reason`.
7. Compute F1 using `_compute_f1(results)`.
8. Emit an `eval.offline.summary` span with `split`, `model`, `f_score`, and `sample_count`.
9. Return the F1 float.

### `_compute_f1(results: list[EvalResult]) -> float`

For each result:

- Skip samples where `expected_label is None`.
- Convert true labels to integers (`pass` → 1, anything else → 0).
- Convert judge score to integers (`1.0` → 1, `0.0` → 0).

If no labeled samples were collected, log a warning and return `0.0`.

Otherwise compute:

- `tp = sum(t == 1 and p == 1 ...)`.
- `fp = sum(t == 0 and p == 1 ...)`.
- `fn = sum(t == 1 and p == 0 ...)`.
- `precision = tp / (tp + fp)` or `0.0`.
- `recall = tp / (tp + fn)` or `0.0`.
- `f1 = 2 * precision * recall / (precision + recall)` or `0.0`.
- Log: `F1=0.812 (precision=..., recall=...) over N samples`.

### Notes

- `pass` is the positive class by convention. A tiny one-sample run containing only `fail` can be correct and still report F1 `0.000`.
- Default `workers=1` is intentional: it keeps Okahu traces grouped into one clean trace tree. Users may pass `--workers N` for speed, but parallel workers can split spans across multiple traces depending on context propagation.
- Do not call any external eval service. Okahu is for traces/inspection; F1 is computed locally.

### `scripts/run_evaluation.py`

The shipped script:

- Parses `--split {dev_evaluator|test_evaluator}`, `--workers`, `--nb-samples`.
- Calls `setup_logging`, `configure_okahu`, then `run_evaluation(...)`.
- Prints `F1 score (judge vs expert labels): {f1:.3f}`.

## Acceptance Criteria

- [ ] `make eval-dev` runs end-to-end and prints `F1 score (judge vs expert labels): 0.xxx`.
- [ ] `make eval-test` runs against the test split with the same shape.
- [ ] With `OKAHU_API_KEY` and `MONOCLE_EXPORTER=file,okahu`, Okahu Cloud shows `eval.offline.score` spans and an `eval.offline.summary` span.
- [ ] The summary span includes `f_score`, `sample_count`, `split`, and `model`.
- [ ] If a labeled split has zero usable items, the harness logs a warning and returns `0.000`.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Attendee runs alignment on the dev split

1. Attendee runs `make eval-dev`.
2. Logs show evaluation progress per item.
3. Final line: `F1 score (judge vs expert labels): 0.857` or the current score.
4. Okahu Cloud shows per-sample judge labels, score, critique, and the aggregate `f_score`.

### Story: Iterate on the metric

1. Attendee tweaks `JUDGE_PROMPT` or the few-shot section in #021's metric.
2. Reruns `make eval-dev` to compare F1 across runs.
3. Once dev F1 is acceptable, runs `make eval-test` on the held-out split.

### Story: Quick sanity check

1. Attendee runs `uv run python scripts/run_evaluation.py --split dev_evaluator --nb-samples 3`.
2. The harness evaluates only the first three dataset items and prints F1 over those.

---

Blocked by: #021.
