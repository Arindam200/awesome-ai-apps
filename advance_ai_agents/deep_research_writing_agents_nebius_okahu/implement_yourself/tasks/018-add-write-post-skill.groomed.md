# Add the `/write-post` Claude Code skill

Status: pending
Tags: `claude-code`, `skill`, `writing`, `harness`
Depends on: #016
Blocks: #019

## Scope

Author the `.claude/skills/write-post/SKILL.md` skill that drives the LinkedIn writing workflow from the harness. Triggering `/write-post` (or any natural-language equivalent listed in the description) sets up `outputs/{slug}/` with a guideline + research, loads the `linkedin_post_workflow` prompt from `linkedin-writer`, and runs the tools in sequence.

### Files to create

- `implement_yourself/.claude/skills/write-post/SKILL.md`

### File contents — frontmatter and structure

YAML frontmatter (exact keys):

```yaml
---
name: write-post
description: "Generate a LinkedIn post using the LinkedIn Writer MCP server. Use this skill whenever the user wants to write a LinkedIn post, create social media content, draft a post from research, or generate a post with an image. Triggers on: 'write a post', 'create a LinkedIn post', 'draft a post about', 'turn this into a post', 'generate a post', or any request involving LinkedIn content creation. Also use when the user has a guideline.md and research.md ready."
---
```

Body sections (H2):

1. **`# Write LinkedIn Post`** title + one-liner.
2. **`## Working Directory`** — slug derivation rules:
   - From a referenced seed/guideline filename (e.g. `my-topic_seed.md` → `my-topic`).
   - Otherwise, slugify the topic (lowercase, hyphens, no special chars, max 60 chars).
   - All output goes to `outputs/{slug}/`.
3. **`## Input Preparation`** — instruct the agent how to build the working directory:
   - The directory needs `guideline.md` and `research.md`.
   - If the user provides raw text, write it into `guideline.md` using a markdown template:
     ```markdown
     # LinkedIn Post Guideline
     ## Topic
     ## Angle
     ## Target Audience
     ## Key Points to Cover
     ## Tone
     ```
   - If `research.md` is elsewhere, copy it into the working directory.
4. **`## Execution`** — instruct the agent to load the `linkedin_post_workflow` MCP prompt from `linkedin-writer` and follow its steps; pass `outputs/{slug}/` as the `working_dir` to every tool call.
5. **`## After Completion`** — present the final `outputs/{slug}/post.md` content; mention `outputs/{slug}/post_image.png` if generated.

### Notes

- The skill must be discoverable on `/reload-plugins`.
- Keep the body terse — the heavy lifting is delegated to the MCP prompt itself.

## Acceptance Criteria

- [ ] `implement_yourself/.claude/skills/write-post/SKILL.md` exists with the frontmatter above.
- [ ] Body contains the four numbered sections + title.
- [ ] Reloading the harness (`/reload-plugins` in Claude Code) lists the new `write-post` skill.
- [ ] Saying "write a LinkedIn post about how AI agents handle tools" causes the harness to invoke the skill, build `outputs/how-ai-agents-handle-tools/{guideline.md}`, and run the workflow.
- [ ] The path `outputs/{slug}/post.md` is presented at the end.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Free-form post

1. Attendee types `/write-post how AI agents use long-context coding`.
2. Harness creates `outputs/how-ai-agents-use-long-context-coding/`, writes a `guideline.md` from the template + the topic, copies/produces `research.md` (running `/research` first if needed), then loads the `linkedin_post_workflow` prompt and proceeds.
3. Harness presents the final post and image path.

### Story: With prepared inputs

1. Attendee already has `outputs/my-topic/guideline.md` and `outputs/my-topic/research.md` from a previous `/research` run.
2. Types `/write-post outputs/my-topic`.
3. Harness skips guideline creation, runs the workflow.

---

Blocked by: #016
