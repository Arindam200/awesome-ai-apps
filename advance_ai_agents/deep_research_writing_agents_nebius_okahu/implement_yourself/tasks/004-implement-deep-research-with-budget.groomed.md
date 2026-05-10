# Implement the `deep_research` tool with Exa and a shared exploration budget

Status: pending
Tags: `mcp`, `research`, `exa`, `nebius`, `pydantic`, `budget`
Depends on: #003
Blocks: #005

## Scope

Implement Exa-backed real-time research and add a hard call-budget cap that protects both `deep_research` and `analyze_youtube_video` from runaway agent loops. After this task, the agent can only run a combined **6 exploration calls** before being forced to call `compile_research` (which lands in #005).

This task introduces the **`models/schemas.py`** Pydantic models for research results, the **`app/research_handler.py`** business logic, the **`app/exploration_budget.py`** budget tracker, the Exa client helper, and the **`PROMPT_RESEARCH`** template.

### Files to create

- `implement_yourself/src/research/app/research_handler.py`
- `implement_yourself/src/research/app/exploration_budget.py`
- `implement_yourself/src/research/models/schemas.py`

### Files to modify

- `implement_yourself/src/research/config/constants.py` — add `EXPLORATION_STATE_FILE = "exploration_state.json"` and `MAX_EXPLORATION_CALLS = 6`.
- `implement_yourself/src/research/config/prompts.py` — add `PROMPT_RESEARCH`.
- `implement_yourself/src/research/utils/llm.py` — add `get_exa_client()` and `call_exa_search(...)`.
- `implement_yourself/src/research/tools/deep_research_tool.py` — replace the placeholder body with the real flow.
- `implement_yourself/src/research/tools/analyze_youtube_video_tool.py` — retrofit shared budget enforcement.

### Public interfaces

`models/schemas.py`:

```python
class ResearchSource(BaseModel):
    url: str
    title: str = ""
    snippet: str = ""

class ResearchResult(BaseModel):
    query: str
    answer: str
    sources: list[ResearchSource] = Field(default_factory=list)
```

`app/research_handler.py`:

```python
async def run_grounded_search(query: str) -> ResearchResult: ...
```

Keep the public function name `run_grounded_search` for compatibility with the rest of the workshop, but implement it with Exa. The function formats `PROMPT_RESEARCH.format(query=query)`, calls `call_exa_search(prompt)`, converts raw source dictionaries into `ResearchSource` models, and returns `ResearchResult(query=query, answer=answer_text, sources=sources)`.

`utils/llm.py` additions:

- `@lru_cache def get_exa_client() -> Exa` — creates an `exa_py.Exa` client from `EXA_API_KEY`.
- `async def call_exa_search(prompt: str) -> tuple[str, list[dict[str, str]]]` — call Exa's answer/search API in a worker thread, return answer text plus source metadata dictionaries containing `url`, `title`, and optional `snippet`.

`app/exploration_budget.py`:

```python
class BudgetExceededError(Exception):
    used_calls: int
    max_calls: int

def record_exploration_call(
    memory_path: Path,
    tool: str,
    query: str,
    *,
    max_calls: int = MAX_EXPLORATION_CALLS,
) -> tuple[int, int]: ...

def reset_exploration_budget(memory_path: Path) -> None: ...
```

State file shape: `{"calls": [{"tool": str, "query": str, "at": float}, ...]}`. Use `time.time()` for `at`. Reuse `load_json`/`save_json` from `utils/file_utils.py`.

### `deep_research_tool` body

1. `validate_directory(working_dir)`; `memory_path = ensure_memory_dir(working_dir)`.
2. Try `record_exploration_call(memory_path, tool="deep_research", query=query)`.
3. On `BudgetExceededError`, return `status="budget_exceeded"` with `used_calls`, `max_calls`, and a message naming `compile_research`.
4. Load existing `.memory/research_results.json` as a list.
5. `result = await run_grounded_search(query)`.
6. Append `result.model_dump()` and save the JSON list.
7. Return `status="success"` with `query`, `answer`, `sources`, `total_sources`, `output_path`, `call`, `max_calls`, `calls_remaining`, and a concise message.

### Retrofit `analyze_youtube_video_tool`

Insert the same `record_exploration_call(..., tool="analyze_youtube_video", query=youtube_url)` step immediately after `ensure_memory_dir`. On success, append `call`, `max_calls`, and `calls_remaining` to both the returned dict and message.

### Notes

- The budget is shared. Six calls combined, not six per tool.
- If `deep_research` is invoked seven times in a row, the seventh should not write a seventh entry to the state file.
- `BudgetExceededError.__str__` should include the words `compile_research`.
- Do not touch `compile_research_tool.py` here; that is #005.

## Acceptance Criteria

- [ ] `Settings` includes `EXA_API_KEY`; `constants.py` exposes `MAX_EXPLORATION_CALLS = 6`.
- [ ] After six successful exploration calls, the seventh returns `status="budget_exceeded"` and does not increment the state file.
- [ ] `deep_research` writes `.memory/research_results.json` containing a list whose last item has `query`, `answer`, and `sources`.
- [ ] Sources contain at least `url` and `title`.
- [ ] `make test-research-workflow` succeeds with `--iterations 2`.
- [ ] `analyze_youtube_video` still works as in #003 and now reports budget metadata.
- [ ] Calling `compile_research` still returns `status="not_implemented"`.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Two Exa queries, then a budget guard

1. Attendee runs `make test-research-workflow`.
2. The script makes two `deep_research` calls. Each returns `status="success"` with non-empty `answer`, sources, and budget metadata.
3. `test_logic/.memory/research_results.json` now has two objects.
4. The attendee continues until the seventh exploration call returns `budget_exceeded`.

### Story: Mixed deep_research + youtube hits the same budget

1. Attendee invokes five `deep_research` calls.
2. Attendee runs `analyze_youtube_video` — succeeds and leaves `calls_remaining=0`.
3. Attendee tries one more `deep_research` — gets `budget_exceeded`.

---

Blocked by: #003.
