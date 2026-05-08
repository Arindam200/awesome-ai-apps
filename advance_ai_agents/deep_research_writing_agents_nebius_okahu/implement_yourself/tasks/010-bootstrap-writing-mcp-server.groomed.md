# Bootstrap the LinkedIn Writer MCP server

Status: pending
Tags: `mcp`, `writing`, `bootstrap`, `pydantic-settings`, `fastmcp`
Depends on: #001
Blocks: #011, #017

## Scope

Wire the boot path of the `linkedin-writer` MCP server so that `make run-writing-server` launches a FastMCP process that imports cleanly, configures logging, builds a `FastMCP(name=…, version=…)` object, and exposes zero tools / resources / prompts (those land in #011 / #015 / #016 / #017). Register the server in `.mcp.json` alongside `deep-research` from #001.

Mirror the shape of the research server tightly — every layer (`routers/`, `tools/`, `app/`, `models/`, `config/`, `utils/`) exists as an empty package and gets populated in later tasks.

### Files to create

- `implement_yourself/src/writing/config/settings.py`
- `implement_yourself/src/writing/config/constants.py`
- `implement_yourself/src/writing/config/prompts.py` *(empty placeholder; populated in #012)*
- `implement_yourself/src/writing/utils/logging.py`

### Files to populate

- `implement_yourself/src/writing/server.py` — currently a one-line module docstring; expand to the full FastMCP entrypoint.
- `implement_yourself/.mcp.json` — add the `linkedin-writer` entry next to `deep-research`.

### Interface and contract

`config/settings.py` defines `Settings(BaseSettings)` with these fields:

| Field | Type | Default | Notes |
|---|---|---|---|
| `server_name` | `str` | `"LinkedIn Writer MCP Server"` | |
| `version` | `str` | `"0.1.0"` | |
| `log_level` | `int` | `logging.INFO` (`LOG_LEVEL`) | |
| `writer_model` | `str` | `"meta-llama/Llama-3.3-70B-Instruct"` | Nebius model used by `write_post` / `edit_post` |
| `reviewer_model` | `str` | `"meta-llama/Llama-3.3-70B-Instruct"` | Nebius model used by `review_post` and the LLM judge |
| `image_model` | `str` | `"gemini-2.5-flash-image"` | Used by `generate_image` (#015) |
| `nebius_base_url` | `str` | `"https://api.studio.nebius.com/v1/"` | OpenAI-compatible Nebius base URL |
| `num_reviews` | `int` | `4` | Number of evaluator-optimizer iterations (#013) |
| `nebius_api_key` | `SecretStr` | required | Alias `NEBIUS_API_KEY` |
| `gemini_api_key` | `SecretStr` | required | Alias `GEMINI_API_KEY` for image generation |
| `okahu_api_key` | `SecretStr \| None` | `None` | Alias `OKAHU_API_KEY`; reserved for #020 |
| `monocle_exporter` | `str \| None` | `"file"` | Alias `MONOCLE_EXPORTER`; reserved for #020 |
| `okahu_workflow_name` | `str` | `"writing-workflow"` | Alias `OKAHU_WORKFLOW_WRITING`; reserved for #020 |

`@lru_cache` `get_settings()` factory.

`config/constants.py` declares:

- `RESEARCH_FILE = "research.md"`
- `GUIDELINE_FILE = "guideline.md"`
- `POST_FILE = "post.md"`
- `IMAGE_FILE = "post_image.png"`
- `MEMORY_FOLDER = ".memory"`
- `PROFILES_DIR = Path(__file__).parent.parent / "profiles"` — points at the four shipped profile markdown files.

`utils/logging.py` exposes the same `setup_logging(level: int = logging.INFO)` function as the research package. (You can copy the implementation from #001 verbatim — both packages own their own copy on purpose, so each package is independently importable.)

`server.py` mirrors the research server's structure:

```python
from fastmcp import FastMCP
from writing.config.settings import get_settings
from writing.utils.logging import setup_logging

logger = logging.getLogger(__name__)

def create_mcp_server() -> FastMCP:
    settings = get_settings()
    mcp = FastMCP(name=settings.server_name, version=settings.version)
    # register_mcp_tools(mcp) — wired in #011
    # register_mcp_resources(mcp) — wired in #017
    # register_mcp_prompts(mcp) — wired in #016
    return mcp

setup_logging(level=get_settings().log_level)
mcp = create_mcp_server()

if __name__ == "__main__":
    mcp.run()
```

`.mcp.json` contains both local MCP servers and preserves any Okahu MCP entry:

```json
{
  "mcpServers": {
    "deep-research": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/research/server.py"],
      "env": { "ENV_FILE_PATH": ".env" }
    },
    "linkedin-writer": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/writing/server.py"],
      "env": { "ENV_FILE_PATH": ".env" }
    }
  },
  "inputs": []
}
```

### Notes

- `PROFILES_DIR` resolves to `src/writing/profiles/` — those four markdown files (`structure_profile.md`, `terminology_profile.md`, `character_profile.md`, `branding_profile.md`) already ship with the skeleton and are immutable.
- The two packages are intentionally independent — duplicating `setup_logging` is fine and matches the parent project's layout.
- Pydantic Settings ignores extra env vars (`extra="ignore"`); a `LOG_LEVEL` set in `.env` for the research server will be silently honored by the writing server too.

## Acceptance Criteria

- [ ] `Settings` exists with the 11 fields above and the listed defaults.
- [ ] `make run-writing-server` boots the FastMCP server without raising. The agent kills the process within ~5s.
- [ ] `.mcp.json` contains both the `deep-research` (from #001) and `linkedin-writer` entries.
- [ ] Importing `writing.server` from a Python REPL works and produces an `mcp` object.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Two MCP servers boot side by side

1. Attendee runs `make run-writing-server`. Server launches, logs `LinkedIn Writer MCP Server v0.1.0`. Ctrl-C exits cleanly.
2. Attendee opens Claude Code in `implement_yourself/`; harness reads `.mcp.json` and connects to both servers.
3. Both servers report zero tools (yet).

### Story: Settings reads from `.env`

1. Attendee adds `OKAHU_WORKFLOW_WRITING=workshop-test` to `.env`.
2. `get_settings().okahu_workflow_name == "workshop-test"`.
3. Removes the line — falls back to default `"writing-workflow"`.

---

Blocked by: #001
