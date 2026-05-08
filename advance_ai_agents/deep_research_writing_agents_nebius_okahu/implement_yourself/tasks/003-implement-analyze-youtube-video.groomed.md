# Implement the `analyze_youtube_video` tool

Status: pending
Tags: `mcp`, `research`, `nebius`, `youtube`, `transcripts`
Depends on: #002
Blocks: #004, #005

## Scope

Replace the `analyze_youtube_video_tool` shell with a real implementation that fetches public YouTube captions/transcripts, asks the Nebius text LLM to format and summarize them, and saves timestamped transcript markdown under `<working_dir>/.memory/transcripts/<video_id>.md`.

This task introduces the **app/ business-logic layer** and the **utils/llm + utils/file_utils** support modules. They are reused by `deep_research` and `compile_research` in later tasks.

### Files to create

- `implement_yourself/src/research/app/youtube_handler.py`
- `implement_yourself/src/research/utils/llm.py`
- `implement_yourself/src/research/utils/file_utils.py`

### Files to modify

- `implement_yourself/src/research/config/prompts.py` — add `PROMPT_YOUTUBE_TRANSCRIPTION`.
- `implement_yourself/src/research/tools/analyze_youtube_video_tool.py` — replace the placeholder body with the real flow.

### Public interfaces

`utils/llm.py`:

- `@lru_cache def get_llm(model: str | None = None) -> ChatOpenAI` — creates a LangChain `ChatOpenAI` client backed by Nebius using `NEBIUS_API_KEY` and `NEBIUS_BASE_URL`.
- `async def call_llm(prompt: str, model: str | None = None, response_schema: type[BaseModel] | None = None, system_instruction: str | None = None) -> str` — calls the Nebius-hosted model. For `response_schema`, append the JSON schema to the prompt and validate the returned JSON before returning.
- Add `call_gemini = call_llm` as a backward-compatible alias if earlier task code or fixtures reference that name.

`utils/file_utils.py`:

- `def ensure_memory_dir(working_dir: str) -> Path`
- `def validate_directory(working_dir: str) -> Path`
- `def read_file(path: Path) -> str`
- `def write_file(path: Path, content: str) -> None`
- `def load_json(path: Path, default: Any = None) -> Any`
- `def save_json(path: Path, data: Any) -> None`

`app/youtube_handler.py`:

- `async def analyze_youtube_video(url: str, output_path: Path, timestamp: int = 30) -> str`
  1. Extract the video id with `get_video_id(url)`.
  2. Fetch transcript snippets via `youtube_transcript_api.YouTubeTranscriptApi().fetch(video_id)` in a worker thread.
  3. Format snippets as `[MM:SS] transcript text`.
  4. Build a prompt from `PROMPT_YOUTUBE_TRANSCRIPTION` plus the fetched transcript.
  5. Call `call_llm(prompt, model=settings.youtube_transcription_model)`.
  6. Persist the returned markdown to `output_path`.
  7. If no transcript can be fetched, write and return a helpful fallback message.
- `def get_video_id(url: str) -> str | None` — handles `youtube.com/watch?v=...` and `youtu.be/...`.

### Tool flow

1. `validate_directory(working_dir)`.
2. `memory_path = ensure_memory_dir(working_dir)`.
3. Create `dest_folder = memory_path / TRANSCRIPTS_FOLDER`.
4. `video_id = get_video_id(youtube_url)`. If `None`, fall back to a sanitized URL and log a warning.
5. `output_path = dest_folder / f"{video_id}.md"`.
6. `transcript = await analyze_youtube_video(url=youtube_url, output_path=output_path)`.
7. Return a `status="success"` dict with `youtube_url`, `video_id`, `transcript`, `output_path`, and a concise message.

### `PROMPT_YOUTUBE_TRANSCRIPTION`

A `{timestamp}` placeholder is substituted in `youtube_handler.analyze_youtube_video`. The prompt instructs the model to:

1. Use only the provided transcript.
2. Preserve useful `[MM:SS]` timestamps.
3. Identify speakers when the transcript makes that possible.
4. Add concise summaries for major sections.
5. Explicitly say when visual details are unavailable rather than inventing them.
6. Output Markdown.

### Notes

- Use `settings.nebius_api_key.get_secret_value()` and `settings.nebius_base_url` for text LLM calls.
- Use `asyncio.to_thread(...)` for transcript fetching because the transcript API is synchronous.
- Do not enforce the exploration budget in this task — that lands with `deep_research` in #004 and is retrofitted to this tool there.
- Do not add Okahu/Monocle tracing yet — that lands in #020.

## Acceptance Criteria

- [ ] `analyze_youtube_video_tool` returns a dict with `status="success"`, a non-empty `transcript` or useful fallback message, and an `output_path` pointing to a real file.
- [ ] After invocation, `<working_dir>/.memory/transcripts/<video_id>.md` exists.
- [ ] `get_video_id` returns the right ID for both `https://www.youtube.com/watch?v=dQw4w9WgXcQ` and `https://youtu.be/dQw4w9WgXcQ`, and `None` for `https://example.com/`.
- [ ] `validate_directory("/path/that/does/not/exist")` raises `ValueError`.
- [ ] `make test-research-workflow` followed by passing `--youtube-url` manually produces a transcript file.
- [ ] `deep_research` and `compile_research` still return `not_implemented`.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Attendee summarizes a YouTube talk

1. The attendee runs `mkdir -p test_logic`.
2. They invoke the test script with a public YouTube URL.
3. The script calls `analyze_youtube_video`, then `compile_research` (still a shell).
4. The console shows `Status: success`, the transcript path, and the size in bytes.
5. Opening the saved transcript reveals Markdown with timestamped transcript content and summaries.

### Story: Attendee passes a malformed URL

1. The attendee passes `--youtube-url https://example.com/foo`.
2. The tool logs a warning and writes a fallback/sanitized transcript filename.
3. The tool still returns `status="success"` with a useful message.

---

Blocked by: #002.
