# Register the writing MCP resources (`config://settings`, `profiles://all`)

Status: pending
Tags: `mcp`, `writing`, `resources`, `routers`, `config`, `profiles`
Depends on: #010
Blocks: #019

## Scope

Add the MCP-resource registration layer to the LinkedIn Writer server. Expose two read-only resources:

- `config://settings` — server settings (model names, num_reviews, key-presence flags). Never leaks secret values.
- `profiles://all` — full markdown content of the four shipped writing profiles, so harnesses or operators can read them without having to mount the source tree.

### Files to create

- `implement_yourself/src/writing/routers/resources.py`

### Files to modify

- `implement_yourself/src/writing/server.py` — call `register_mcp_resources(mcp)` from `create_mcp_server()`.

### Public interfaces

```python
def register_mcp_resources(mcp: FastMCP) -> None:
    @mcp.resource("config://settings")
    async def get_config() -> str:
        settings = get_settings()
        return json.dumps({
            "server_name": settings.server_name,
            "version": settings.version,
            "writer_model": settings.writer_model,
            "reviewer_model": settings.reviewer_model,
            "image_model": settings.image_model,
            "num_reviews": settings.num_reviews,
            "has_nebius_api_key": settings.nebius_api_key is not None,
            "has_gemini_api_key": settings.gemini_api_key is not None,
            "has_okahu_api_key": settings.okahu_api_key is not None,
            "monocle_exporter": settings.monocle_exporter,
            "okahu_workflow_name": settings.okahu_workflow_name,
        })

    @mcp.resource("profiles://all")
    async def get_profiles() -> str:
        profiles = load_profiles()
        return json.dumps({
            "structure": profiles.structure.content,
            "terminology": profiles.terminology.content,
            "character": profiles.character.content,
            "branding": profiles.branding.content,
        })
```

### Notes

- `load_profiles()` is implemented in #012; if this task ships before #012, stub `profiles://all` to raise `NotImplementedError` until #012 lands. (The dependency-on-#010 is the bare minimum; #012 makes the second resource useful.)
- DO NOT expose `SecretStr` values — only the booleans for keys.
- The two URI schemes (`config://` vs `profiles://`) are intentional — they map to different conceptual buckets.

## Acceptance Criteria

- [ ] `mcp.list_resources()` returns at least the two URIs `config://settings` and `profiles://all`.
- [ ] Reading `config://settings` returns the keys above; no secret values leak.
- [ ] Reading `profiles://all` returns four non-empty markdown strings.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Operator inspects settings

1. Operator boots the server with `make run-writing-server`.
2. Reads `config://settings` from an MCP client and sees `writer_model`, `reviewer_model`, `image_model`, and `num_reviews=4`.

### Story: Harness reads profiles

1. Attendee asks the harness to "show me the structure profile". Harness fetches `profiles://all` and prints the `structure` field.

---

Blocked by: #010 (resource #1) and #012 (resource #2 needs `load_profiles`)
