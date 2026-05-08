# Register the `research_workflow` MCP prompt

Status: pending
Tags: `mcp`, `research`, `prompts`, `routers`
Depends on: #005
Blocks: #008

## Scope

Add the MCP-prompt registration layer for the Deep Research server. The prompt teaches the harness (Claude Code, Cursor, etc.) how to chain the three tools, when to use each, and how to self-pace within the 6-call exploration budget so the agent never trips `budget_exceeded` accidentally.

### Files to create

- `implement_yourself/src/research/routers/prompts.py`

### Files to modify

- `implement_yourself/src/research/server.py` — wire `register_mcp_prompts(mcp)` into `create_mcp_server()`.

### Public interface

`routers/prompts.py`:

```python
WORKFLOW_INSTRUCTIONS = """
... long, hand-authored markdown explaining the workflow ...
""".strip()

def register_mcp_prompts(mcp: FastMCP) -> None:
    @mcp.prompt()
    async def research_workflow() -> str:
        """Research workflow instructions."""
        return WORKFLOW_INSTRUCTIONS
```

DO NOT add Okahu/Monocle tracing yet — that lands in #020.

### `WORKFLOW_INSTRUCTIONS` body — content checklist

The prompt MUST cover, in this order:

1. **Role line.** "You are a deep research agent. Use the available tools to thoroughly research a topic."
2. **Available Tools** section — three numbered entries describing `deep_research(working_dir, query)`, `analyze_youtube_video(working_dir, youtube_url)`, and `compile_research(working_dir)`. For each, name the input/outputs in plain English.
3. **Workflow** section — five numbered steps:
   1. Decompose the user's topic into multiple specific queries.
   2. Call `deep_research` per query; review and identify gaps.
   3. If YouTube URLs were provided, call `analyze_youtube_video` for each.
   4. Run additional `deep_research` calls to fill gaps.
   5. Call `compile_research` once at the end.
4. **Hard limit** section — make this loud:
   - State the cap is **6 exploration calls** total (`deep_research` + `analyze_youtube_video` combined).
   - Mention the server tracks calls in `.memory/exploration_state.json` and refuses the 7th call with `status: "budget_exceeded"`.
   - Tell the agent each successful response carries `call`, `max_calls`, `calls_remaining` so it can self-pace.
   - Frame the budget as roughly **3 rounds of ~2 queries each**.
5. **Notes** — `working_dir` is the current working directory, all intermediates live in `.memory/`, the agent decides query count within the 3-round budget.

The wording does not need to be byte-identical to the parent project's prompt. It must be self-sufficient — the harness should be able to drive the system from this prompt alone.

### Notes

- The prompt is registered with `@mcp.prompt()` (no name argument needed; FastMCP uses the function name).
- Returning a single string is fine — FastMCP will surface it as a Prompt with one user-message slot.
- If the implementer is tempted to template anything (e.g. injecting `MAX_EXPLORATION_CALLS`), do not — the prompt is hand-authored markdown, and the constant is already 6 in production. Keep it readable.

## Acceptance Criteria

- [ ] `register_mcp_prompts` exists and is called from `create_mcp_server`.
- [ ] `mcp.list_prompts()` (via an MCP client) returns one prompt named `research_workflow`.
- [ ] Calling the prompt returns a markdown string containing the substrings: `deep_research`, `analyze_youtube_video`, `compile_research`, `compile_research`, `6 exploration calls`, `.memory/exploration_state.json`, `budget_exceeded`, `calls_remaining`.
- [ ] The prompt does not crash when invoked (no template placeholders left unfilled).
- [ ] `make test-research-workflow` still passes.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Harness fetches the prompt at session start

1. Attendee invokes the `/research` skill (lands in #008) or directly asks Claude Code to "use the research_workflow prompt from deep-research".
2. The harness fetches the prompt and now has explicit, complete instructions for sequencing the three tools.
3. The harness plans 5 queries, sees the budget warning, and trims to 4 queries upfront.

### Story: Agent self-paces

1. Harness runs `deep_research` four times. Response payloads show `calls_remaining` decrementing 5 → 2.
2. Harness reads the prompt's hard-limit section and decides to call `compile_research` rather than risk the 7th call.
3. `compile_research` succeeds; budget resets.

---

Blocked by: #005
