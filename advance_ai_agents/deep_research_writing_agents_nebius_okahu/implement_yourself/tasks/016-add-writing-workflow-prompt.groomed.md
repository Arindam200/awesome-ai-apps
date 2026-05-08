# Register the `linkedin_post_workflow` MCP prompt

Status: pending
Tags: `mcp`, `writing`, `prompts`, `routers`
Depends on: #015
Blocks: #018

## Scope

Add the MCP-prompt registration layer for the LinkedIn Writer server. The prompt teaches the harness how to chain the three writing tools (`generate_post` → `generate_image` → optional `edit_post` loop), declares the input file contract (`guideline.md`, `research.md`), spells out the on-disk artifacts produced, and documents the failure policy.

### Files to create

- `implement_yourself/src/writing/routers/prompts.py`

### Files to modify

- `implement_yourself/src/writing/server.py` — wire `register_mcp_prompts(mcp)` into `create_mcp_server()`.

### Public interface

```python
WORKFLOW_INSTRUCTIONS = """ ... """.strip()

def register_mcp_prompts(mcp: FastMCP) -> None:
    @mcp.prompt()
    async def linkedin_post_workflow() -> str:
        """Complete LinkedIn post writing workflow instructions."""
        return WORKFLOW_INSTRUCTIONS
```

(No Okahu/Monocle tracing yet — that lands in #020.)

### `WORKFLOW_INSTRUCTIONS` content checklist

The prompt MUST cover, in order:

1. **Role line.** "Your job is to execute the LinkedIn post writing workflow below."
2. **Working directory contract.** Explain that all tools take a `working_dir` argument; if not provided, the agent must ask for it. The directory must contain:
   - `guideline.md` — what the post is about.
   - `research.md` — factual material (typically from the research agent).
3. **Workflow** — four numbered phases:
   1. **Setup** — explain steps to the user; verify both inputs exist.
   2. **Generate the post** — call `generate_post(working_dir)`. Describe what happens internally (initial post → review/edit loop → versions in `.memory/` → final `post.md`). Present the post to the user.
   3. **Generate an image** — call `generate_image(working_dir)`. Describe the output (`post_image.png`).
   4. **Edit with feedback (optional, repeat)** — call `edit_post(working_dir, human_feedback)`; explain that human feedback gets highest priority.
4. **File Structure After Completion** — exact tree:
   ```
   working_dir/
   ├── guideline.md
   ├── research.md
   ├── .memory/
   │   ├── reviews_1.json
   │   └── reviews_2.json
   ├── post_0.md
   ├── post_1.md
   ├── post_2.md
   ├── post.md
   └── post_image.png
   ```
5. **Critical Failure Policy.** If a tool reports a failure: halt, name the failing tool, quote the output, ask the user how to proceed.

The wording does not have to be byte-identical to the parent project's prompt. It must (a) make the harness call the tools in the right order and (b) spell out the file artifacts so the user knows what to inspect afterward.

### Notes

- The prompt is registered with `@mcp.prompt()`. Function name `linkedin_post_workflow` becomes the MCP-visible name.
- DO NOT add observability hooks here.
- Keep it under ~150 lines of markdown for legibility.

## Acceptance Criteria

- [ ] `mcp.list_prompts()` includes `linkedin_post_workflow`.
- [ ] Calling the prompt returns a markdown string containing all four phase headers (or equivalent), the working-directory tree, and the failure-policy paragraph.
- [ ] The string explicitly names all three tools at least once.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Harness loads the prompt at session start

1. Attendee triggers the `/write-post` skill (lands in #018) or asks Claude Code to "use the linkedin_post_workflow prompt from linkedin-writer".
2. Harness fetches the prompt and now has explicit step-by-step instructions.
3. Harness asks for a `working_dir`, verifies inputs, then proceeds with `generate_post`.

### Story: Harness halts on tool failure

1. `generate_image` fails (e.g. missing model access). Tool returns or raises.
2. Harness, following the failure policy, stops; reports the failing tool + output to the user; awaits guidance.

---

Blocked by: #015
