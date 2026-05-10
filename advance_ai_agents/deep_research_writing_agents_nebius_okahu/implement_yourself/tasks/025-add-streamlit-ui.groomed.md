# Add a Streamlit chat UI orchestrating both MCP servers

Status: pending
Tags: `streamlit`, `ui`, `fastmcp-client`, `harness-free`
Depends on: #015, #017
Blocks: —

## Scope

Add a single-file Streamlit chat app at `implement_yourself/streamlit_app.py` that drives the `deep-research` and `linkedin-writer` MCP servers via the FastMCP `Client` (stdio transport) — no AI harness required. The user pastes a topic into the chat input or uploads a `.md` / `.txt` seed file; the app then runs the full pipeline end-to-end (decompose → research per query → compile → guideline synthesis → post generation → image) and renders live per-stage progress in a single assistant chat bubble.

The UI **must not modify the MCP servers**. All progress feedback is derived purely from what each tool returns (the research tools expose per-call `total_sources`; the writing tools are one-shot — `generate_post` only returns after the whole evaluator-optimizer loop finishes, so an indeterminate animation is the right affordance there).

The app must encode the same orchestration logic as the `linkedin_post_workflow` MCP prompt, but inline in Python — *do not* fetch the prompts from the server. We want explicit control over the call sequence and over what's surfaced at each step.

### Files to create

- `implement_yourself/streamlit_app.py`

### Files to modify

- `implement_yourself/pyproject.toml` — add `streamlit>=1.40.0` to `dependencies`. Run `uv sync` after.
- `implement_yourself/Makefile` — add a `run-ui` target between `run-writing-server` and `test-research-workflow`:
  ```makefile
  run-ui: # Run the Streamlit chat UI orchestrating both MCP servers.
	uv run streamlit run streamlit_app.py
  ```

### Public surface

`streamlit_app.py` is a script — no exported functions. Run with `make run-ui` (which shells `uv run streamlit run streamlit_app.py`).

### App structure (top to bottom of the file)

1. **Module imports + `sys.path` shim.** Insert `implement_yourself/src` into `sys.path` so `from writing.config.settings import get_settings` works (we reuse Settings to load `.env` and to access Nebius config for the auxiliary text LLM calls in step 4).

2. **Constants.**
   - `REPO_ROOT = Path(__file__).parent.resolve()`
   - `RESEARCH_SERVER = str(REPO_ROOT / "src" / "research" / "server.py")`
   - `WRITING_SERVER = str(REPO_ROOT / "src" / "writing" / "server.py")`
   - `OUTPUTS_DIR = REPO_ROOT / "outputs"`
   - Two prompt strings: `DECOMPOSE_PROMPT` (asks Gemini to break a topic into 3–5 distinct research queries; structured output via Pydantic) and `GUIDELINE_PROMPT` (asks Gemini to draft a markdown guideline with H2 sections: Topic, Angle, Target Audience, Key Points, Tone — under 200 words).

3. **Indeterminate progress bar.** A small CSS keyframe shimmer injected once at app startup via `st.markdown(INDETERMINATE_BAR_CSS, unsafe_allow_html=True)`. A helper `indeterminate_bar_html(label: str) -> str` returns the bar HTML fragment. Used for the writing + image stages where the MCP server gives no mid-call progress signal.

4. **Pydantic schema + helpers.**
   - `ResearchQueries(BaseModel)` with `queries: list[str] = Field(min_length=2, max_length=6)`.
   - `slugify(text, max_len=60)` → folder slug (lowercase, hyphens, alnum-only).
   - `unwrap(result)` — FastMCP's `Client.call_tool` returns an object with `.data`; tolerate both shapes.
   - Use the shared writing `call_llm(...)` helper for auxiliary topic decomposition and guideline synthesis.

5. **Stage views (dataclasses owning `st.empty()` placeholders).**

   `ResearchStageView`:
   - `render_init(queries)` writes `### 🔎 Deep research` + a counter slot + a per-query rows slot + a compile slot.
   - `update(idx, *, status, sources=0)` — flips a query from ⚪️ pending → 🟡 running → 🟢 done and updates the live `**X / N searches done · Y sources collected**` counter + per-row tail `— K sources`.
   - `compile_running()` shows `📚 _Compiling research.md..._`.
   - `compile_done(output_path)` shows a green success message with the file size.

   `WritingStageView`:
   - `render_init(num_reviews)` writes `### ✍️ Writing workflow` + caption `Evaluator-optimizer loop · up to {N} review/edit iterations`, allocates four slots: progress / post / image_running / image.
   - `writing_running()` paints the indeterminate bar with label `Running evaluator-optimizer loop...`.
   - `writing_done(post_text, post_path)` flips the bar to ✅ success + an expander containing the rendered post markdown.
   - `image_running()` paints the indeterminate bar with `Generating image with Gemini Image...`.
   - `image_done(image_path)` clears the running bar, shows `### 🖼️ Generated image`, renders `st.image(image_path, width=520)`, captions with the saved path.

6. **Async pipeline.**
   - `decompose_topic(topic) -> list[str]` — one Nebius text LLM call with `response_schema=ResearchQueries`.
   - `synthesize_guideline(topic) -> str` — one Gemini text call returning markdown.
   - `run_research_pipeline(working_dir, queries, view)` — opens an `async with Client(RESEARCH_SERVER) as client:` block, iterates over `queries`, for each: marks running, calls `deep_research(working_dir, query)`, reads `total_sources` from the result, marks done. Then calls `compile_research(working_dir)` and reports the output path.
   - `fetch_num_reviews(client) -> int` — reads `config://settings` from the writing server (#017), JSON-decodes the resource text, returns `cfg.get("num_reviews")`. Falls back to `get_settings().num_reviews` on any error.
   - `run_writing_pipeline(working_dir, skip_image, view)` — opens an `async with Client(WRITING_SERVER) as client:` block, fetches `num_reviews`, calls `view.render_init(num_reviews)`, then awaits `generate_post(working_dir, delete_iterations=False)` (the call is one-shot — the indeterminate bar is the only progress signal we can offer), unwraps `post`/`output_path`, calls `view.writing_done(...)`, then if `skip_image=False` calls `view.image_running()`, awaits `generate_image(working_dir)`, calls `view.image_done(image_path)`.
   - `run_pipeline(topic, research_view, writing_view) -> dict[str, str]` — top-level orchestrator: slugifies the topic, creates `OUTPUTS_DIR / slug`, persists `seed.md`, synthesizes + writes `guideline.md`, decomposes queries, runs research, runs writing. Returns `{working_dir, research, post, image}` paths.

7. **Streamlit UI section.**
   - `st.set_page_config(page_title="Research → Writer", page_icon="✍️", layout="wide")`.
   - Inject `INDETERMINATE_BAR_CSS`.
   - Title `✍️ Research → Writer` + caption `End-to-end pipeline: deep research → LinkedIn post → image. Drives the deep-research and linkedin-writer MCP servers via FastMCP.`.
   - Session state: `run_count`, `processed_seed_file_id`.
   - Suggestion pills (3 hard-coded topics) shown only on the first run; clicking one stores the topic into `st.session_state.prefill`.
   - **Two-column input row:** `st.chat_input("Paste a topic / seed text...")` on the left (4-wide) + `st.file_uploader(label, type=["md","txt"], label_visibility="collapsed")` on the right (1-wide). The file uploader auto-triggers a Streamlit rerun on upload, so the pipeline kicks off immediately when a fresh file is uploaded — no submit click required. Dedupe replays via `seed_file.file_id != st.session_state.processed_seed_file_id`.
   - Topic resolution priority on each rerun: `prefill` (one-shot) → typed chat input → freshly uploaded seed file. If `topic_text` is non-empty, render a user `st.chat_message` with the seed in an expander, then an assistant `st.chat_message` containing two stacked containers (research + writing) and a footer `st.empty()`. Run `asyncio.run(run_pipeline(...))` inside the assistant message.
   - On success, the footer shows a small `### 📁 Artifacts` block with paths to `working_dir`, `research.md`, `post.md`, `post_image.png`. On exception, surface `footer.error(...)`.

### Notes

- **No sidebar settings.** Hardcode `skip_image=False` inside `run_pipeline` and let the MCP servers govern their own behavior (the deep-research call cap from #004 is sufficient; `num_reviews` comes from the writing server's `config://settings` resource).
- The streamlit_app reads `config://settings` to populate the writing-stage caption — this is the only reason it depends on #017 (`add-writing-resources`).
- The MCP servers are spawned automatically by FastMCP's stdio transport when `Client(...)` enters the async context. No need to start `make run-research-server` separately.
- All output paths live under `implement_yourself/outputs/{slug}/` — match the slugging style used by the `/research-and-write` skill so the dataset directories interop.
- Logging: use the module logger (`logger = logging.getLogger(__name__)`); never use `print` (per `CLAUDE.md`).

## Acceptance Criteria

- [ ] `make run-ui` boots a Streamlit server (default port 8501) without import errors. Visiting the URL renders the page with the title `✍️ Research → Writer` and the chat input + file uploader row.
- [ ] Typing a topic and submitting via the chat input kicks off the pipeline. Within ~5s the `🔎 Deep research` stage appears with a `0 / N searches done` counter and per-query rows in pending state.
- [ ] As each `deep_research` call returns, the corresponding row flips to 🟢 with a `— K sources` tail and the running total updates. After the last query, the compile slot transitions to a green `✅ research.md generated (X bytes)` block.
- [ ] The `✍️ Writing workflow` stage renders next with the caption `Evaluator-optimizer loop · up to {num_reviews} review/edit iterations` (the value matches `config://settings.num_reviews`). An animated indeterminate bar shimmers while the call is in flight, then flips to a `✅ Post finalized` success block with an expander containing the rendered post markdown.
- [ ] The image stage shows the indeterminate bar `Generating image with Gemini Image...`, then renders the generated `post_image.png` at width 520 with a caption pointing to the saved path.
- [ ] Uploading a `.md` seed file via the file_uploader (without typing anything) auto-kicks off the pipeline on the next rerun. Re-uploading the same file does NOT trigger a duplicate run (verified via `processed_seed_file_id`).
- [ ] On a forced failure (e.g. delete `.env` mid-session, or kill one of the MCP servers), the footer renders an `st.error(...)` banner with the exception message; the app does NOT crash the Streamlit process.
- [ ] No edits to any file under `implement_yourself/src/research/` or `implement_yourself/src/writing/`. Verified with `git diff --name-only` before submitting.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Quick demo from a one-line topic

1. Attendee opens `implement_yourself/` and runs `make run-ui`.
2. The browser shows the page with three suggestion pills. Attendee clicks one (e.g. "Why single agents beat multi-agent setups").
3. The pipeline runs. Within ~30–90s the attendee sees: 3–5 research queries flip green with source counts, a research.md success bar, the writing workflow's indeterminate bar, the final post in an expander, and the generated image.
4. The footer shows artifact paths under `outputs/why-single-agents-beat-multi-agent-setups/`.

### Story: Drop-in seed file

1. Attendee has a `seed.md` from a prior research session.
2. They drag it into the file uploader on the right of the chat input. No need to type anything or click submit.
3. The pipeline kicks off immediately using the file's contents as the topic. The slug is derived from the first line of the seed.

### Story: Failure visibility

1. Attendee removes `NEBIUS_API_KEY` from `.env`, then triggers a run.
2. The first Nebius call (`decompose_topic`) raises. The assistant chat bubble's footer renders a red `Pipeline failed: ...` banner with the exception text.
3. The Streamlit process keeps running; the attendee can fix `.env`, refresh, and try again.

## Out of scope

- Multi-page Streamlit layout, sidebar widgets, theming, custom CSS beyond the indeterminate bar.
- Showing iteration-by-iteration progress for the evaluator-optimizer loop (the writing server flushes `post_*.md` and `.memory/reviews_*.json` only after the call returns — there is no observable mid-call signal without modifying the server, which is forbidden).
- Editing any file under `implement_yourself/src/`.
- Persisting chat history across reruns (each new submission starts a fresh assistant bubble; prior runs scroll up but are not navigable).
- Authentication, rate limiting, or multi-user state.

---

Blocked by: #015, #017
