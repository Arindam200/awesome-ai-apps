# Implement `generate_post` (no evaluator-optimizer loop yet)

Status: pending
Tags: `mcp`, `writing`, `gemini`, `pydantic`, `prompt-engineering`
Depends on: #011
Blocks: #013

## Scope

Implement an end-to-end one-shot LinkedIn post generator. After this task, the `generate_post` tool reads `guideline.md` + `research.md` from `working_dir`, loads the four shipped writing profiles + few-shot post examples from the dataset, calls the Nebius text LLM once via the `PROMPT_WRITE_POST` template, and saves the result to `post.md`.

There is **no review/edit iteration** yet — that lands in #013. `num_reviews` from `Settings` is unused here. The internal `versions` and `reviews` lists exist only to keep the `GeneratePostResult` shape stable for #013.

### Files to create

- `implement_yourself/src/writing/utils/llm.py`
- `implement_yourself/src/writing/models/schemas.py`
- `implement_yourself/src/writing/app/profile_loader.py`
- `implement_yourself/src/writing/app/dataset_loader.py`
- `implement_yourself/src/writing/app/post_writer_handler.py`
- `implement_yourself/src/writing/app/generate_post.py`

### Files to modify

- `implement_yourself/src/writing/config/prompts.py` — add `PROMPT_WRITE_POST`.
- `implement_yourself/src/writing/tools/generate_post_tool.py` — replace placeholder with real flow.

### Public interfaces

`models/schemas.py` (Pydantic):

```python
class Profile(BaseModel):
    name: str
    content: str

class Profiles(BaseModel):
    structure: Profile
    terminology: Profile
    character: Profile
    branding: Profile

class Post(BaseModel):
    content: str

class Review(BaseModel):           # placeholder — populated in #013
    profile: str
    location: str
    comment: str

class PostReviews(BaseModel):      # placeholder — populated in #013
    reviews: list[Review] = Field(default_factory=list)

class GeneratePostResult(BaseModel):
    post: Post
    versions: list[Post] = Field(default_factory=list)
    reviews: list[PostReviews] = Field(default_factory=list)
```

`utils/llm.py`:

- `@lru_cache get_llm(model: str | None = None) -> ChatOpenAI` — same shape as research utils, reads `settings.nebius_api_key.get_secret_value()` and `settings.nebius_base_url`.
- `async def call_gemini(prompt, model=None, response_schema=None, system_instruction=None) -> str` — defaults `model` to `settings.writer_model`. Mirrors the research package's signature.

`app/profile_loader.py`:

- `def load_profiles() -> Profiles` — reads the four `*_profile.md` files from `PROFILES_DIR`. Raises `FileNotFoundError` with the missing path if any are absent.

`app/dataset_loader.py` (initial scope — only what `generate_post` needs):

- Module-level `DATASET_DIR = Path(__file__).parent.parent.parent.parent / "datasets" / "linkedin_paul_iusztin"` (resolves to `<repo-root>/datasets/linkedin_paul_iusztin/`).
- Pydantic models:
  - `class Label(StrEnum): PASS = "pass"; FAIL = "fail"`
  - `class DatasetEntry(BaseModel)` — fields: `slug`, optional `urn`, `linkedin_url`, `local_post`, `local_media: list[str] | None`, `reactions/comments/shares: int | None`, `local_guideline`, `local_seed`, `local_research`, `scope: list[str] | None`, `local_generated_post`, `label: Label | None`, `critique: str | None`. Helpers: `_read_file(field, base_dir)`, `post_content(base_dir)`, `generated_content(base_dir)`, `guideline_content(base_dir)`, `seed_content(base_dir)`, `research_content(base_dir)`, `media_paths(base_dir) -> list[Path]`. Each helper resolves the path relative to `base_dir`, lstrip `./`.
  - `class PostExample(BaseModel)`: `slug: str`, `content: str`.
  - `class MediaExample(BaseModel)`: `slug: str`, `media_path: Path`.
  - `class DatasetExamples(BaseModel)`: `post_examples: list[PostExample]`, `media_examples: list[MediaExample]`. Method `format_post_examples() -> str` — join examples as `--- Example {i} ---\n{content}\n--- End Example {i} ---` separated by blank lines; `"<none>"` if empty.
- Functions:
  - `def load_dataset() -> list[DatasetEntry]` — reads `DATASET_DIR / "index.yaml"` via `yaml.safe_load`, returns parsed entries. Returns `[]` if the file is missing (with a warning log).
  - `def load_by_scope(scope: str) -> list[DatasetEntry]` — filter by `scope in entry.scope`.
  - `def load_examples() -> DatasetExamples` — for each entry whose `scope` contains `"train_generator"`, append a `PostExample(slug, content=entry.post_content(DATASET_DIR))`. For each entry whose `scope` contains `"train_image_generator"`, append a `MediaExample(slug, media_path=entry.media_paths(DATASET_DIR)[0])`.
  - (`load_labeled_samples` exists in the parent for evals — DO NOT add it here; it lands in #021.)

`app/post_writer_handler.py`:

```python
async def write_post(
    guideline: str,
    research: str,
    profiles: Profiles,
    post_examples: str = "<none>",
) -> Post: ...
```

Builds `PROMPT_WRITE_POST.format(...)` (placeholders enumerated below), `call_gemini(prompt)`, returns `Post(content=response)`.

`app/generate_post.py`:

```python
async def generate_post(guideline: str, research: str) -> GeneratePostResult: ...
```

For this task: load profiles + examples, call `write_post(...)`, return `GeneratePostResult(post=post, versions=[post], reviews=[])`. The `versions` list always contains the one initial post.

### `tools/generate_post_tool.py` body

1. Validate `guideline.md` + `research.md` exist in `working_dir`. Raise `FileNotFoundError` otherwise.
2. Read both files into strings.
3. `result = await generate_post(guideline, research)`.
4. If `delete_iterations` is `False`: write each `result.versions[idx]` to `working_dir / f"post_{idx}.md"`. (For now there's only one version; `post_0.md` is created.)
5. Always write `result.post.content` to `working_dir / POST_FILE` (`post.md`).
6. Return:
   ```python
   {
     "status": "success",
     "review_iterations": settings.num_reviews,   # value reported even though unused this task
     "output_path": str((working_dir / POST_FILE).resolve()),
     "message": f"Generated LinkedIn post with {settings.num_reviews} review/edit iterations. "
                f"Final post saved to {POST_FILE}",
     "post": result.post.content,
   }
   ```

Note: the `message` is forward-compatible — it lies slightly until #013 lands, but matches the parent's wire format.

### `PROMPT_WRITE_POST` shape

A markdown prompt with these placeholders (exact names):

- `{guideline}`, `{research}`
- `{structure_profile}`, `{terminology_profile}`, `{character_profile}`
- `{post_examples}`

The prompt instructs the model to:

- Treat the profiles as binding rules (structure → length/format/hook/CTA; terminology → word choice; character → persona/voice — write AS this person, do NOT name them).
- Study the examples for rhythm and energy.
- Extract relevant facts only from the research; do not dump it.
- Return ONLY the post text — no preamble, no commentary.

Wording does not need to be byte-identical to the parent's `PROMPT_WRITE_POST`; semantic equivalence and the exact placeholder names are required.

### Notes

- The character profile says to write *as* the persona but not to name them — preserve that instruction.
- `delete_iterations=True` skips writing `post_0.md` and any `.memory/reviews_*.json` files, leaving only `post.md`.
- `format_post_examples()` returns `"<none>"` when no `train_generator` entries exist — the prompt template handles that string via the `{post_examples}` slot. Make sure the template tolerates the literal `<none>`.
- Make `dataset_loader.DATASET_DIR` resilient: if the dataset folder is missing, `load_dataset()` returns `[]` and `load_examples()` returns an empty `DatasetExamples`. The prompt then receives `<none>` for examples — the workflow degrades gracefully.

## Acceptance Criteria

- [ ] `generate_post_tool` writes a non-empty `post.md` whose contents match `result.post.content`.
- [ ] `delete_iterations=False` (default): `post_0.md` exists and equals `post.md`.
- [ ] `delete_iterations=True`: `post_0.md` is absent.
- [ ] If `guideline.md` or `research.md` is missing in `working_dir`, the tool raises `FileNotFoundError` with a helpful message (not a generic stack trace).
- [ ] Profiles loaded from `src/writing/profiles/` (4 files); missing file raises `FileNotFoundError`.
- [ ] `make test-writing-workflow` reports `Status: success` for the `generate_post` step. The `edit_post` and `generate_image` steps still print `Status: not_implemented` (those are #014 and #015).
- [ ] Generated post visibly follows the four profiles (no markdown headers, no hashtags, hook in first 2 lines, CTA at end). Spot-check by reading the output.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Attendee runs the writing test

1. Attendee runs `make test-writing-workflow`.
2. Makefile copies the seed's `_guideline.md` + `_research.md` into `test_logic/`.
3. Script calls `generate_post(working_dir="test_logic")`. Tool returns `Status: success` and prints the post.
4. `test_logic/post.md` (and `post_0.md`) now exist with the same content.

### Story: Few-shot examples drive style

1. Attendee inspects `<repo-root>/datasets/linkedin_paul_iusztin/index.yaml` and observes several entries scoped `train_generator`.
2. The generated post visibly imitates that style (short paragraphs, no emoji unless the persona uses them, no markdown headers).
3. Removing all `train_generator` entries from the index makes `format_post_examples()` return `<none>` — the post generator still works but produces less stylistically anchored output.

### Story: Missing inputs error helpfully

1. Attendee runs the tool against an empty directory.
2. Tool raises `FileNotFoundError: guideline.md not found in test_logic`.

---

Blocked by: #011
