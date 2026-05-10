# Register the three research MCP tool shells

Status: pending
Tags: `mcp`, `research`, `tools`, `routers`, `fastmcp`
Depends on: #001
Blocks: #003, #004, #005

## Scope

Stand up the MCP-tool registration layer for the Deep Research server with **empty shells** for `deep_research`, `analyze_youtube_video`, and `compile_research`. After this task, an MCP client connecting to the server lists three callable tools that each return a deterministic placeholder dict — no provider calls yet, no file I/O.

This task introduces the **routers/ → tools/** call pattern that the rest of the research server follows.

### Files to create

- `implement_yourself/src/research/routers/tools.py`
- `implement_yourself/src/research/tools/deep_research_tool.py`
- `implement_yourself/src/research/tools/analyze_youtube_video_tool.py`
- `implement_yourself/src/research/tools/compile_research_tool.py`

### Files to modify

- `implement_yourself/src/research/server.py` — uncomment / un-stub the call to `register_mcp_tools(mcp)`.

### Interface and contract

`routers/tools.py` exposes one public function:

```python
def register_mcp_tools(mcp: FastMCP) -> None: ...
```

Inside it, declare three async functions decorated with `@mcp.tool()`. Tool signatures match the parent project exactly so later tasks slot in cleanly:

| Tool | Signature | Returns |
|---|---|---|
| `deep_research` | `async def deep_research(working_dir: str, query: str) -> dict[str, Any]` | placeholder dict |
| `analyze_youtube_video` | `async def analyze_youtube_video(working_dir: str, youtube_url: str) -> dict[str, Any]` | placeholder dict |
| `compile_research` | `async def compile_research(working_dir: str) -> dict[str, Any]` | placeholder dict |

Each `@mcp.tool()` body delegates to the corresponding implementation in `tools/*_tool.py`. The implementation files own the docstring (which becomes the MCP tool description) and the actual return logic.

Each `tools/<name>_tool.py` file exports an `async def <name>_tool(...)` function with the **same signature** as the registered tool minus the `mcp` decorator. For this task the body of each `_tool` function returns a hard-coded dict:

```python
{
    "status": "not_implemented",
    "tool": "<tool name>",
    "working_dir": working_dir,
    "message": "Shell only — implementation lands in task #00X.",
}
```

(Where `00X` is `003` for `analyze_youtube_video_tool`, `004` for `deep_research_tool`, `005` for `compile_research_tool`. These references serve as breadcrumbs for the implementer.)

### Tool descriptions (MCP-visible)

The docstring of each tool function in `routers/tools.py` becomes the description the harness sees. Use these exact intents (copy from the parent README's "MCP Primitives" table for canonical wording):

- **`deep_research`** — "Research a topic using Exa search." Args: `working_dir`, `query`.
- **`analyze_youtube_video`** — "Analyze a YouTube video using Gemini's native video understanding." Args: `working_dir`, `youtube_url`.
- **`compile_research`** — "Aggregate all collected research into a single markdown research brief." Args: `working_dir`.

### Notes

- DO NOT add Okahu/Monocle tracing yet — that lands in #020.
- DO NOT add input validation, file I/O, Exa calls, or Nebius calls. The point of this task is "the harness sees the tools."
- Keep the placeholder bodies async-friendly so signatures stay stable when real logic lands.
- Add `from __future__ import annotations` only if needed; otherwise prefer plain forward types (`dict[str, Any]` works on Python ≥ 3.9 with `__future__` and on 3.12 natively).

## Acceptance Criteria

- [ ] `routers/tools.py` defines `register_mcp_tools(mcp: FastMCP) -> None` and registers exactly three tools.
- [ ] `server.py` calls `register_mcp_tools(mcp)` during `create_mcp_server`.
- [ ] Running `uv run python scripts/test_research_workflow.py --working-dir test_logic --iterations 1` succeeds end-to-end with `Status: not_implemented` reported for the only research call. The script also calls `compile_research` at the end, which must also return `Status: not_implemented`. The script must not crash.
- [ ] An MCP client (e.g. `make run-research-server` + `fastmcp` inspector or the test script) lists three tools whose names are `deep_research`, `analyze_youtube_video`, `compile_research`.
- [ ] Tool descriptions render in the MCP listing (i.e. the docstring is non-empty for each).
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Test script runs against the shells

1. The attendee makes sure `.env` has `NEBIUS_API_KEY` and `EXA_API_KEY` populated (still required by `Settings`, even though no provider call is made yet — Pydantic validates at import time).
2. The attendee runs `make test-research-workflow`. The Makefile copies `im-currently-designing-a-second-brain-ai-agent_seed.md` into `test_logic/seed.md` and invokes `scripts/test_research_workflow.py --working-dir test_logic --iterations 2`.
3. The script connects via stdio, lists tools (3 found), runs two `deep_research` calls, skips `analyze_youtube_video` (no `--youtube-url`), then calls `compile_research`.
4. Each call prints `Status: not_implemented` and `Message: Shell only — implementation lands in task #00X.` where X matches the right downstream task number.
5. The script exits 0 even though `research.md` was not created (it warns "WARNING: ... was not created" — that's fine for this task).

### Story: Harness sees three tools

1. The attendee opens Claude Code in `implement_yourself/`.
2. The harness connects to `deep-research` and reports three available tools.
3. Hovering over each tool shows the MCP description and arg schema (`working_dir`, plus the tool-specific param).

---

Blocked by: #001
