# Implement the `edit_post` tool

Status: pending
Tags: `mcp`, `writing`, `human-in-the-loop`, `gemini`
Depends on: #013
Blocks: #015

## Scope

Implement the `edit_post` MCP tool — a single-pass review + edit driven by **explicit human feedback**, which takes priority over every profile and the guideline. The tool reads `post.md` (must already exist — `generate_post` was run first), runs one `review_post(...)` with the human feedback injected, then one `edit_post(...)` (the business-logic function from #013), and writes the new post back to `post.md` plus a versioned `post_N.md`.

### Files to modify

- `implement_yourself/src/writing/tools/edit_post_tool.py` — replace the placeholder body.

### Tool flow

1. Resolve paths: `post.md`, `guideline.md`, `research.md`. `post.md` must exist (raise `FileNotFoundError` "Run generate_post first." if missing). `guideline.md` must exist. `research.md` is optional (read empty string if absent).
2. Load the four profiles via `load_profiles()` and the few-shot examples via `load_examples()`.
3. Construct `post = Post(content=<post.md content>)`.
4. Call `reviews_result = await review_post(post, guideline, profiles, human_feedback=human_feedback)`.
5. If `delete_iterations=False`: write `[r.model_dump() for r in reviews_result.reviews]` to `working_dir / .memory / reviews_edit.json` (note the filename suffix — distinct from `reviews_N.json` written by `generate_post`).
6. If `reviews_result.reviews` is empty:
   - Log "No issues found. Post unchanged."
   - Return:
     ```python
     {
       "status": "success",
       "reviews_count": 0,
       "output_path": str(post_path.resolve()),
       "message": "No issues found based on feedback. Post unchanged.",
       "post": post.content,
     }
     ```
7. Otherwise, call `edited_post = await edit_post_business_fn(post, reviews_result.reviews, guideline, research, profiles, post_examples_text)` (the `edit_post` from `app/post_writer_handler.py`).
8. If `delete_iterations=False`: pick the next free `post_N.md` filename (`next_version = len(sorted(working_path.glob("post_*.md")))`) and write `edited_post.content` there.
9. Always overwrite `post.md` with `edited_post.content`.
10. Return:
    ```python
    {
      "status": "success",
      "reviews_count": len(reviews_result.reviews),
      "output_path": str(post_path.resolve()),
      "message": (
        f"Applied {len(reviews_result.reviews)} review(s) based on feedback. "
        f"Updated post saved to {POST_FILE}\n\nReviews addressed:\n{reviews_summary}"
      ),
      "post": edited_post.content,
    }
    ```
    where `reviews_summary = "\n".join(f"- [{r.profile}] {r.location}: {r.comment}" for r in reviews_result.reviews)`.

### Naming conflicts

The MCP tool is `edit_post`. The business-logic function in `app/post_writer_handler.py` is also called `edit_post`. Inside `tools/edit_post_tool.py`, import the business function as e.g. `from writing.app.post_writer_handler import edit_post` — and then your tool function lives in this module as `edit_post_tool`. The naming clash with the registered tool name is resolved by the MCP decorator using its function name in `routers/tools.py` (`async def edit_post(...)` calling `edit_post_tool(...)`). DO NOT rename either; this matches the parent project.

### Notes

- The workflow tolerates a missing `research.md` because attendees may want to manually edit a post that was generated outside the research workflow.
- `human_feedback` is mandatory and pure user text; do not lint or transform it.
- `delete_iterations=True` short-circuits both the `reviews_edit.json` write and the versioned `post_N.md` write.

## Acceptance Criteria

- [ ] After `generate_post` runs, calling `edit_post(working_dir, "Make the hook more provocative.")`:
  - Returns `Status: success` with `reviews_count >= 1` (typically).
  - Updates `post.md` in place.
  - Creates `post_K.md` where `K = previous_max + 1` (unless `delete_iterations=True`).
  - Writes `.memory/reviews_edit.json` (unless `delete_iterations=True`).
- [ ] If `post.md` is missing, the tool raises `FileNotFoundError` with a message that mentions `Run generate_post first.`.
- [ ] If `reviews_result.reviews` is empty, the post file is unchanged on disk (no rewrite even of the same content), and the tool returns the "No issues found" message.
- [ ] `make test-writing-workflow` reports `Status: success` for both `generate_post` and `edit_post`. The `edit_post` step uses the canned feedback from the script: "Make the hook more provocative. Add a stronger call-to-action at the end."
- [ ] `generate_image` still returns `not_implemented` (lands in #015).
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Attendee asks for a punchier hook

1. After `generate_post` writes `post.md`, attendee invokes `edit_post(working_dir="test_logic", human_feedback="Make the hook more provocative. Add a stronger CTA at the end.")`.
2. The tool runs one review pass; the human feedback ends up at the top of the prompt with "highest priority" framing.
3. Reviews flag the existing hook and CTA. The editor rewrites both. `post.md` reflects the new hook + CTA.
4. The console prints the bulleted summary of addressed reviews.

### Story: Feedback applies cleanly to an empty/optional review

1. Attendee asks `edit_post(working_dir, human_feedback="Looks great as is, no changes needed.")`.
2. The reviewer correctly emits 0 reviews.
3. The tool returns `reviews_count: 0`, `post.md` is unchanged.

### Story: Attendee runs `delete_iterations=True`

1. Same as above with `delete_iterations=True`.
2. `post.md` updates (if reviews exist), but no `post_N.md` and no `.memory/reviews_edit.json` files are written.

---

Blocked by: #013
