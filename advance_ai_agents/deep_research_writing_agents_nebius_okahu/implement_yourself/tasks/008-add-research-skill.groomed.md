# Add the `/research` Claude Code skill

Status: pending
Tags: `claude-code`, `skill`, `research`, `harness`
Depends on: #006
Blocks: #009

## Scope

Author the `.claude/skills/research/SKILL.md` skill that drives the deep research workflow from the harness. Triggering `/research` (or any of the natural-language phrases the skill description lists) loads the `research_workflow` prompt from the `deep-research` MCP server, picks a working directory under `outputs/{slug}/`, and runs the tools in sequence.

### Files to create

- `implement_yourself/.claude/skills/research/SKILL.md`

### File contents — exact frontmatter and structure

The file must start with YAML frontmatter:

```yaml
---
name: research
description: "Run deep research on any topic using the Deep Research MCP server. Use this skill whenever the user wants to research a topic, gather information, find sources, or create a research document. Triggers on: 'research this', 'find out about', 'gather information on', 'I need to understand', 'deep dive into', or any request that involves investigating a topic."
---
```

Body sections (use H2 headings):

1. **`# Research`** title and a one-line summary stating the skill uses the `deep-research` MCP server.
2. **`## Working Directory`** — explain the slug-derivation rule:
   - If the user references a dataset seed file like `my-topic_seed.md`, derive `slug=my-topic`.
   - Otherwise, slugify the topic (lowercase, hyphens, no special chars, max 60 chars).
   - All output goes to `outputs/{slug}/` relative to the project root.
   - Create the directory if it doesn't exist.
3. **`## Execution`** — instruct the agent to:
   1. Load the `research_workflow` MCP prompt from the `deep-research` server.
   2. Follow that prompt's instructions, using the tools `deep_research`, `analyze_youtube_video`, `compile_research`.
   3. Use `outputs/{slug}/` as the `working_dir` argument for every tool call.
4. **`## After Completion`** — instruct the agent to show the path to `outputs/{slug}/research.md` and a brief summary of what was found.

### Notes

- The skill file is markdown with YAML frontmatter. Do not nest other frontmatter inside the body.
- Keep the instructions terse — the harness inlines the prompt loaded from the MCP server, so the skill only needs the orchestration glue around it.
- The `description` field is what the harness uses to decide whether to invoke the skill. Phrasing matters; it should be discoverable by the trigger phrases listed.

## Acceptance Criteria

- [ ] `implement_yourself/.claude/skills/research/SKILL.md` exists and parses as valid YAML frontmatter + markdown body.
- [ ] The frontmatter has the exact `name: research` and a `description` containing the trigger phrases listed above.
- [ ] The body covers the four sections (Working Directory, Execution, After Completion, plus the title).
- [ ] Reloading skills in Claude Code (or running `/reload-plugins` in the harness) surfaces the new skill.
- [ ] Issuing the prompt "research how AI agents handle long-context coding tasks" causes the harness to invoke the skill, create `outputs/how-ai-agents-handle-long-context-coding-tasks/`, fetch the MCP prompt, and run the tools.
- [ ] `make format-check && make lint-check` pass (skill files are markdown; ruff ignores them — but make sure no Python files were touched accidentally).

## User Stories

### Story: Attendee runs `/research` for a free-form topic

1. Attendee types `/research how do AI agents handle long-context coding tasks`.
2. Harness invokes the skill, slugifies → `how-do-ai-agents-handle-long-context-coding-tasks`, and `mkdir -p outputs/how-do-ai-agents-handle-long-context-coding-tasks/`.
3. Harness fetches the `research_workflow` prompt from the `deep-research` server.
4. The harness runs 4–6 `deep_research` calls, then `compile_research`, all against the new working directory.
5. The harness reports the path to `outputs/.../research.md` and a paragraph summarizing the findings.

### Story: Attendee references a dataset seed

1. Attendee types `/research im-currently-designing-a-second-brain-ai-agent_seed.md` (the seed file shipped with the dataset).
2. Slug becomes `im-currently-designing-a-second-brain-ai-agent`.
3. The skill copies / writes the seed text into context, runs the workflow, produces `outputs/im-currently-designing-a-second-brain-ai-agent/research.md`.

---

Blocked by: #006
