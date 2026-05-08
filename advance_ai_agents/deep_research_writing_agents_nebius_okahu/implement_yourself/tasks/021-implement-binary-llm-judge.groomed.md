# Implement the local BinaryLLMJudgeMetric and eval dataset loaders

Status: pending
Tags: `evals`, `okahu`, `llm-judge`, `pydantic`, `dataset`, `nebius`
Depends on: #020
Blocks: #022

## Scope

Implement the LLM-judge half of the eval system without any external eval-platform dependency. The judge scores a generated post as pass/fail against the writing profiles, using few-shot examples from the dataset's `train_evaluator` split. Dataset rows are loaded locally from the workshop dataset files; Okahu/Monocle receives traces later from the harness in #022.

This task introduces the `writing/evals/` package (currently only `__init__.py` exists in the skeleton), specifically `dataset.py` and `metric.py`.

### Files to create

- `implement_yourself/src/writing/evals/dataset.py`
- `implement_yourself/src/writing/evals/metric.py`

### Files to modify

- `implement_yourself/src/writing/app/dataset_loader.py` — add `load_labeled_samples(label_filter: Label | None = None) -> list[LabeledSample]` and define the `LabeledSample(BaseModel)` model: `slug, ground_truth, generated, label: Label, critique: str`.

### Public interfaces

`writing/evals/dataset.py`:

```python
def load_offline_eval_items(split: str) -> list[dict[str, Any]]: ...
def load_online_eval_items(split: str) -> list[dict[str, Any]]: ...
```

`load_offline_eval_items`:

1. `entries = load_by_scope(split)`. If empty, raise `ValueError(f"No entries found for split '{split}'")`.
2. For each entry with both `label` and `critique` set, build an item:
   ```python
   {
     "slug": entry.slug,
     "guideline": entry.guideline_content(DATASET_DIR),
     "research":  entry.research_content(DATASET_DIR),
     "generated_post": entry.generated_content(DATASET_DIR),
     "label":     entry.label.value,
     "critique":  entry.critique,
   }
   ```
3. Skip entries where `generated_post` is empty, with a warning log.
4. Return the list.

`load_online_eval_items`:

- Same source split loading, but items only require `slug`, `guideline`, `research`, and optional `label` / `critique` when present.

`writing/evals/metric.py`:

```python
@dataclass(frozen=True)
class JudgeScore:
    name: str
    value: float
    label: str
    critique: str
    reason: str

class JudgeResult(BaseModel):
    label: str             # "pass" or "fail"
    critique: str          # 1–3 sentences

class BinaryLLMJudgeMetric:
    def __init__(self, name: str = "binary_llm_judge", model: str | None = None) -> None: ...
    def _build_prompt(self, guideline: str, research: str, generated_post: str) -> str: ...
    def score(self, guideline, research, output, **ignored_kwargs) -> JudgeScore: ...
    async def ascore(self, guideline, research, output, **ignored_kwargs) -> JudgeScore: ...
```

Constructor must:

1. Set `self.name = name`.
2. `settings = get_settings()`. Set `self._model = model or settings.reviewer_model`.
3. Use the shared Nebius/LangChain helper (`call_llm`) for scoring, not a direct Gemini text client.
4. Load profiles (`load_profiles()`) and store `structure`, `terminology`, and `character` content strings.
5. Load few-shot examples from `train_evaluator`:
   - `train_entries = load_by_scope("train_evaluator")`.
   - For each with both `label` and `critique`, build a `_FewShotExample` from `guideline_content(DATASET_DIR)` and `generated_content(DATASET_DIR)`.
   - Skip entries where either field is empty.
6. `self._few_shot_section = _build_few_shot_section(few_shot_examples)`.

`_build_few_shot_section`:

- If empty list, return `""`.
- Otherwise, build a heading "**FEW-SHOT EXAMPLES — follow the same labeling logic:**" followed by per-example XML blocks `<example_{i}> <guideline>...</guideline> <generated_post>...</generated_post> <expected_output>label: ... critique: ...</expected_output> </example_{i}>`.

`_build_prompt` formats `JUDGE_PROMPT` with placeholders:

- `{structure_profile}`, `{terminology_profile}`, `{character_profile}` — from loaded profiles.
- `{few_shot_section}` — from `_build_few_shot_section`.
- `{guideline}`, `{research}` (default `"<none>"` if empty), `{generated_post}`.

`score()`:

- Build prompt.
- Call `call_llm(..., model=self._model, response_schema=JudgeResult)`.
- Validate/parse the returned JSON with `JudgeResult.model_validate_json(...)`.
- Normalize label to lowercase.
- Return `JudgeScore(name=self.name, value=1.0 if label == "pass" else 0.0, label=label, critique=result.critique, reason=f"[{label}] {result.critique}")`.

`ascore()` is the awaited variant using the same shared helper.

### `JUDGE_PROMPT` content checklist

Wording does not need to be byte-identical to the reference prompt. It must:

1. State the judge has **no ground truth** — must judge against guideline + profiles only.
2. Inject the three profiles in `<structure_profile>`, `<terminology_profile>`, `<character_profile>` blocks.
3. State **labeling guidelines**: leave room for creativity; flag `fail` only for major violations.
4. Insert `{few_shot_section}` after the labeling guidelines.
5. Provide the actual case under "**NOW EVALUATE THIS:**" with `<guideline>`, `<research_context>`, `<generated_post>` blocks.
6. Demand output of a JSON object: `label` (`"pass"`/`"fail"`) and `critique` (1–3 sentences).

### Notes

- The metric MUST work even if `train_evaluator` produces zero few-shot examples.
- The dataset loaders require `datasets/linkedin_paul_iusztin/index.yaml`. If running `implement_yourself/` standalone, symlink the parent dataset: `cd implement_yourself && ln -s ../datasets ./datasets`.
- Do not add external eval-platform imports, datasets, experiments, upload helpers, or base metric classes.

## Acceptance Criteria

- [ ] `load_offline_eval_items("dev_evaluator")` returns local dictionaries with `slug, guideline, research, generated_post, label, critique`.
- [ ] `load_online_eval_items("online_test")` returns local dictionaries with `slug, guideline, research` and optional labels.
- [ ] `BinaryLLMJudgeMetric().score(guideline=..., research=..., output=...)` returns a `JudgeScore` with `value in {0.0, 1.0}` and a non-empty `reason`.
- [ ] When `train_evaluator` has at least one labeled entry, the prompt includes a `<example_1>` block.
- [ ] When `train_evaluator` has zero labeled entries, `_few_shot_section` is `""` and the prompt still validates.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Judge produces structured output

1. Attendee constructs the metric (`metric = BinaryLLMJudgeMetric()`).
2. Calls `metric.score(guideline="...", research="", output="<a known-bad post full of banned marketing language>")`.
3. Returns `value=0.0`, `label="fail"`, and a reason citing the quality issue.
4. Calls again with a clean post and gets `value=1.0`.

### Story: Few-shot examples shape labels

1. Attendee adds a `train_evaluator` entry with `label: fail` for a borderline post.
2. Reconstructs the metric.
3. The new few-shot example shows up in `_few_shot_section`.
4. Subsequent scoring aligns more closely with the labeled example's reasoning.

---

Blocked by: #020.
