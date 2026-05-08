# Add the evaluator-optimizer loop to `generate_post`

Status: pending
Tags: `mcp`, `writing`, `evaluator-optimizer`, `gemini`, `pydantic`, `structured-output`
Depends on: #012
Blocks: #014

## Scope

Extend `generate_post` from a one-shot writer into the parent project's full **generate → [review → edit] × N** loop. Add the reviewer (`review_post`) and editor (`edit_post` business-logic function — distinct from the MCP tool of the same name in #014). After this task, the workflow performs `num_reviews` review/edit iterations (default 4 from `Settings`), saves intermediate `post_N.md` versions, and persists structured review JSON in `.memory/reviews_N.json`.

This task introduces **structured output via Pydantic `response_schema`**: the reviewer returns `PostReviews` which the model must emit as JSON.

### Files to create

- `implement_yourself/src/writing/app/post_reviewer_handler.py`

### Files to modify

- `implement_yourself/src/writing/config/prompts.py` — add `PROMPT_REVIEW_POST` and `PROMPT_EDIT_POST`.
- `implement_yourself/src/writing/app/post_writer_handler.py` — add an `edit_post(...)` async function alongside `write_post(...)`.
- `implement_yourself/src/writing/app/generate_post.py` — add the iteration loop after the initial `write_post`.
- `implement_yourself/src/writing/tools/generate_post_tool.py` — write each version + each `reviews_N.json` to disk (only when `delete_iterations=False`).

### Public interfaces

`app/post_reviewer_handler.py`:

```python
async def review_post(
    post: Post,
    guideline: str,
    profiles: Profiles,
    human_feedback: str | None = None,
    max_reviews: int = 5,
) -> PostReviews: ...
```

- Builds an optional **human feedback section** (only emitted if `human_feedback` is truthy):
  ```
  **IMPORTANT — Human Feedback (highest priority):**
  The user provided the following feedback. Address it before checking profiles.

  <human_feedback>
  {human_feedback}
  </human_feedback>
  ```
- Formats `PROMPT_REVIEW_POST` with placeholders: `{post}`, `{guideline}`, `{structure_profile}`, `{terminology_profile}`, `{character_profile}`, `{human_feedback_section}`, `{max_reviews}`.
- Calls `call_gemini(prompt, model=settings.reviewer_model, response_schema=PostReviews)` — the response is JSON conforming to `PostReviews`.
- Returns `PostReviews.model_validate_json(response)`.

`app/post_writer_handler.py` additions:

```python
def _format_reviews(reviews: list[Review]) -> str:
    """Format reviews as `1. [profile] @ location\\n   comment\\n` blocks."""

async def edit_post(
    post: Post,
    reviews: list[Review],
    guideline: str,
    research: str,
    profiles: Profiles,
    post_examples: str = "<none>",
) -> Post: ...
```

`edit_post` formats `PROMPT_EDIT_POST` with placeholders `{guideline}`, `{research}`, `{structure_profile}`, `{terminology_profile}`, `{character_profile}`, `{post}`, `{reviews}`, `{post_examples}`. Calls `call_gemini(prompt)` (default model = writer_model). Returns `Post(content=response)`.

`app/generate_post.py` updated body:

```python
async def generate_post(guideline, research) -> GeneratePostResult:
    settings = get_settings()
    profiles = load_profiles()
    examples = load_examples()
    post_examples_text = examples.format_post_examples()

    post = await write_post(guideline, research, profiles, post_examples_text)
    versions: list[Post] = [post]
    all_reviews: list[PostReviews] = []

    for i in range(settings.num_reviews):
        reviews_result = await review_post(post, guideline, profiles)
        all_reviews.append(reviews_result)
        if not reviews_result.reviews:
            continue                        # no issues; skip edit, do not re-add to versions
        post = await edit_post(
            post, reviews_result.reviews, guideline, research, profiles, post_examples_text
        )
        versions.append(post)

    return GeneratePostResult(post=post, versions=versions, reviews=all_reviews)
```

### Tool flow updates (`generate_post_tool.py`)

After `result = await generate_post(...)`:

1. If `delete_iterations=False`:
   - For each `idx, version in enumerate(result.versions)`: write `working_dir / f"post_{idx}.md"`.
   - For each `idx, reviews_result in enumerate(result.reviews)`: write `working_dir / MEMORY_FOLDER / f"reviews_{idx + 1}.json"` containing the JSON dump of `[r.model_dump() for r in reviews_result.reviews]`. Create `.memory/` if it doesn't exist.
2. Always write `result.post.content` to `post.md`.
3. Return the same dict shape as #012, but `review_iterations` now reflects truth.

### `PROMPT_REVIEW_POST` shape

The reviewer prompt declares it must comply with:

1. The guideline (highest priority).
2. The structure profile.
3. The terminology profile.
4. The character profile.

Followed by `{human_feedback_section}` (may be empty), then the `<post>`, `<guideline>`, and three `<*_profile>` XML-style sections, then instructions:

- Compare the post against each profile and the guideline.
- For each violation, produce a `Review(profile, location, comment)`.
- Return at most `{max_reviews}` reviews. Skip profiles where the post is compliant.
- Return as structured JSON (the `response_schema` enforces this).

### `PROMPT_EDIT_POST` shape

The editor prompt provides `<guideline>`, `<research>`, three profile sections, `<post_examples>`, `<current_post>`, and `<reviews>`. Instructions:

1. Read each review.
2. Prioritize: human feedback > guideline > profile.
3. Apply edits while preserving flow and coherence.
4. Match the example posts' rhythm and energy.
5. Anchor facts in `<research>` — do not invent.
6. Return ONLY the edited post text.

### Notes

- A "no reviews" iteration is treated as a no-op — no edit happens, no new version is appended, but the empty `reviews_result` IS appended to `all_reviews` so consumers see the full audit trail.
- Default `num_reviews=4` means up to 4 review/edit cycles. With early no-op iterations the workflow may run shorter than 4 edits, which is fine.
- The reviewer model and writer model can differ via `Settings.reviewer_model` / `writer_model` — keep them as separate settings even though the parent project defaults both to the same Nebius-hosted model.
- `Settings.reviewer_model` must reliably follow the JSON schema instruction. If a model returns malformed JSON, `review_post` should surface that error rather than silently swallowing it.

## Acceptance Criteria

- [ ] `generate_post` runs `num_reviews` (default 4) review/edit cycles.
- [ ] After a default run, `working_dir/` contains: `post.md`, `post_0.md`, `post_1.md`, …, `post_K.md` (where `K` ≤ `num_reviews` because some iterations may be no-ops). `K + 1 == len(result.versions)`.
- [ ] After a default run, `working_dir/.memory/reviews_1.json`, …, `reviews_{num_reviews}.json` all exist (one per iteration, even no-op iterations get an empty `[]`). They contain valid JSON arrays of `Review` dicts (`profile`, `location`, `comment`).
- [ ] `delete_iterations=True` skips writing `post_*.md` (only `post.md` exists) and skips writing `reviews_*.json`.
- [ ] If the reviewer ever returns 0 reviews, the loop continues to the next iteration without modifying the post.
- [ ] `make test-writing-workflow` reports a `Status: success` for `generate_post` and the produced post visibly differs from the initial draft (compare `post_0.md` vs `post.md`).
- [ ] `edit_post` and `generate_image` tools still return `not_implemented` (they're #014 and #015).
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Loop refines a draft

1. Attendee runs `make test-writing-workflow`.
2. The script's `generate_post` step runs ~30s longer than after #012 because of the review/edit loop.
3. `post_0.md` reads less polished; `post.md` (final) reads tighter, hits the structure rules harder, and avoids banned terminology.
4. `.memory/reviews_1.json` shows several reviews; `reviews_4.json` may be empty `[]` — meaning the loop converged.

### Story: Convergence short-circuits gracefully

1. With a very strong initial draft, the first `review_post` returns `[]`.
2. The loop runs all 4 iterations but no `edit_post` is called.
3. `post.md` equals `post_0.md`. All `reviews_*.json` are `[]`.
4. The tool still reports `Status: success`.

### Story: Reviewer enforces structured output

1. The reviewer LLM call uses `response_schema=PostReviews`.
2. If the model returns malformed JSON, `PostReviews.model_validate_json` raises — the tool surfaces the error to the harness rather than silently swallowing.

---

Blocked by: #012
