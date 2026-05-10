# Implement the `compile_research` tool

Status: pending
Tags: `mcp`, `research`, `markdown`, `aggregation`
Depends on: #004
Blocks: #006

## Scope

Replace the `compile_research_tool` shell with a real implementation that walks `<working_dir>/.memory/`, merges the accumulated Exa research results and YouTube transcripts into a single Markdown document, writes it to `<working_dir>/research.md`, and resets the exploration budget so any follow-up session starts fresh.

This task introduces **`utils/markdown_utils.py`** (collapsible `<details>` blocks) and **`app/research_file_handler.py`** (the orchestration of read → format → join).

### Files to create

- `implement_yourself/src/research/utils/markdown_utils.py`
- `implement_yourself/src/research/app/research_file_handler.py`

### Files to modify

- `implement_yourself/src/research/tools/compile_research_tool.py` — replace the placeholder body.

### Public interfaces

`utils/markdown_utils.py`:

- `def markdown_collapsible(title: str, body: str) -> str` — returns an HTML-style collapsible block:
  ```
  <details>
  <summary>{title}</summary>

  {body.strip()}

  </details>
  ```
- `def build_research_results_section(results: list[dict]) -> str` — given a list of dicts each with `query`, `answer`, `sources` (where each source has `url`, `title`), produces:
  ```
  ## Research Results

  <details><summary>{query}</summary>

  {answer}

  **Sources:**
  - [{title}]({url})
  - …

  </details>
  …
  ```
  When `results` is empty, return `"## Research Results\n\n_No research results found._\n"`.
- `def build_sources_section(section_title: str, sources: list[tuple[str, str]], empty_message: str) -> str` — generic; each tuple is `(title, body)`. Used by the YouTube section.
- `def combine_research_sections(*sections: str) -> str` — `"\n\n".join(["# Research", *sections])`.

`app/research_file_handler.py`:

- `def compile_research_file(working_dir: str) -> str` — reads `RESEARCH_RESULTS_FILE` and every `*.md` under `TRANSCRIPTS_FOLDER`, builds the two sections, and returns the combined markdown.

### `compile_research_tool` body

1. `validate_directory(working_dir)`.
2. `final_md = compile_research_file(working_dir)`.
3. `output_path = Path(working_dir) / RESEARCH_MD_FILE`; `write_file(output_path, final_md)`.
4. `reset_exploration_budget(Path(working_dir) / MEMORY_FOLDER)`.
5. Return:
   ```python
   {
     "status": "success",
     "output_path": str(output_path.resolve()),
     "message": f"Generated {RESEARCH_MD_FILE} at {output_path.resolve()}",
   }
   ```

### Edge cases

- `.memory/research_results.json` missing → `load_json(..., default=[])` returns `[]` → "Research Results" section renders the empty placeholder.
- `.memory/transcripts/` missing → "YouTube Video Transcripts" section renders the empty placeholder ("_No YouTube video transcripts found._").
- Transcript files iterated in sorted order (`sorted(dir.glob("*.md"))`) for deterministic output. Filename stem is the section title.

### Notes

- `compile_research` does NOT consume an exploration budget slot — it is the *exit* condition.
- Writing `research.md` overwrites any prior version in the working directory. That's intentional; the agent reruns when the topic changes.
- `reset_exploration_budget` is idempotent — if the state file is already absent, do nothing.

## Acceptance Criteria

- [ ] After running the full workflow, `<working_dir>/research.md` exists and starts with `# Research`.
- [ ] `research.md` contains a `## Research Results` section with one collapsible `<details>` block per `deep_research` query.
- [ ] If at least one transcript exists, `research.md` contains a `## YouTube Video Transcripts` section. Otherwise it shows `_No YouTube video transcripts found._`.
- [ ] Calling `compile_research` deletes `.memory/exploration_state.json` (or leaves it absent if it never existed).
- [ ] After `compile_research`, an immediate follow-up `deep_research` call succeeds with `call=1` (budget reset).
- [ ] `make test-research-workflow` produces a non-empty `test_logic/research.md` (≥ 200 bytes typically).
- [ ] `make test-end-to-end` halts cleanly at the writing step (writing isn't implemented yet) but the research half completes.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: End-to-end research session

1. Attendee runs `make test-research-workflow`.
2. Two `deep_research` calls execute and append to `.memory/research_results.json`.
3. The third tool call is `compile_research` — it succeeds, prints the absolute path, and returns `status="success"`.
4. Opening `test_logic/research.md` reveals a header `# Research`, two collapsible queries with sources, and a YouTube section showing the empty placeholder.
5. `test_logic/.memory/exploration_state.json` no longer exists.

### Story: Reuse the same working directory

1. After step 1's run, attendee runs `make test-research-workflow` again.
2. Because `compile_research` reset the budget, the new two `deep_research` calls succeed (calls 1 and 2 of the new session).
3. `research.md` is regenerated to include the new results too — note that `research_results.json` was *not* cleared (deliberately, so accumulated context is preserved across sessions). The implementer should confirm this is the parent-project behaviour by reading `compile_research_tool.py` in the parent. (If divergence is preferred, document it in the task log.)

### Story: Empty `.memory/`

1. Attendee runs `compile_research` against a brand-new empty directory.
2. Tool returns `status="success"` and writes a `research.md` containing only the empty placeholders for both sections.

---

Blocked by: #004
