# Register the three writing MCP tool shells

Status: pending
Tags: `mcp`, `writing`, `tools`, `routers`, `fastmcp`
Depends on: #010
Blocks: #012, #014, #015

## Scope

Register `generate_post`, `edit_post`, and `generate_image` as **empty shells** on the `linkedin-writer` server. After this task an MCP client lists three callable tools that all return placeholder dicts — no provider calls, no file I/O.

Mirror the layering from #002: `routers/tools.py` registers, `tools/<name>_tool.py` implements (just a placeholder body for now).

### Files to create

- `implement_yourself/src/writing/routers/tools.py`
- `implement_yourself/src/writing/tools/generate_post_tool.py`
- `implement_yourself/src/writing/tools/edit_post_tool.py`
- `implement_yourself/src/writing/tools/generate_image_tool.py`

### Files to modify

- `implement_yourself/src/writing/server.py` — call `register_mcp_tools(mcp)` from `create_mcp_server()`.

### Tool signatures

| Tool | Signature | Purpose (description shown to harness) |
|---|---|---|
| `generate_post` | `async def generate_post(working_dir: str, delete_iterations: bool = False) -> dict[str, Any]` | "Generate a LinkedIn post with an evaluate-optimize loop." |
| `edit_post` | `async def edit_post(working_dir: str, human_feedback: str, delete_iterations: bool = False) -> dict[str, Any]` | "Edit an existing LinkedIn post based on human feedback." |
| `generate_image` | `async def generate_image(working_dir: str) -> dict[str, Any]` | "Generate a LinkedIn post image using Gemini image generation." |

Each registered tool delegates to the corresponding `<name>_tool` function in `tools/`.

Each `<name>_tool` returns:

```python
{
  "status": "not_implemented",
  "tool": "<tool name>",
  "working_dir": working_dir,
  "message": "Shell only — implementation lands in task #00X.",
}
```

(`X` = `12` for `generate_post_tool`, `14` for `edit_post_tool`, `15` for `generate_image_tool`.)

### Notes

- DO NOT add Okahu/Monocle tracing yet — that comes in #020.
- DO NOT validate inputs; this is a pure shell task.
- DO NOT touch the existing `__init__.py` files unless you have a re-export reason.

## Acceptance Criteria

- [ ] `register_mcp_tools(mcp)` registers exactly three tools with the listed signatures and descriptions.
- [ ] `make run-writing-server` boots cleanly.
- [ ] `make test-writing-workflow` runs end-to-end (without `--skip-image`) and prints `Status: not_implemented` for all three steps. The script does not crash even though `post.md` won't exist; the test script's tail tolerates a missing `post.md` (it only warns).
- [ ] An MCP client lists three tools: `generate_post`, `edit_post`, `generate_image`.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Test script walks all three shells

1. Attendee runs `make test-writing-workflow`. The Makefile copies the dataset's `_guideline.md` and `_research.md` into `test_logic/`.
2. The script connects via stdio, finds 3 tools, calls each in order.
3. Console prints three `Status: not_implemented` messages with the right downstream task numbers.

### Story: Harness lists writing tools

1. Attendee opens Claude Code in `implement_yourself/`.
2. Harness lists 6 tools total: 3 from `deep-research`, 3 from `linkedin-writer`.

---

Blocked by: #010
