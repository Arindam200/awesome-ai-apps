# Bootstrap the Deep Research MCP server

Status: pending
Tags: `mcp`, `research`, `bootstrap`, `pydantic-settings`, `fastmcp`
Depends on: None
Blocks: #002, #007, #010

## Scope

Wire the boot path of the `deep-research` MCP server so that `make run-research-server` launches a FastMCP process exposing zero tools but a healthy `name` and `version`. No tools, prompts, or resources are registered yet — those land in later tasks.

### Files to create

- `implement_yourself/src/research/config/settings.py`
- `implement_yourself/src/research/config/constants.py`
- `implement_yourself/src/research/config/prompts.py` *(empty placeholder module — populated in #003)*
- `implement_yourself/src/research/utils/logging.py`

### Files to populate

- `implement_yourself/src/research/server.py` — currently a one-line module docstring; expand to the full FastMCP entrypoint.
- `implement_yourself/.mcp.json` — ensure the `deep-research` entry is present while preserving any existing entries such as `linkedin-writer` or `okahu`.
- `implement_yourself/.env.example` — already lists `NEBIUS_API_KEY`, `EXA_API_KEY`, and optional Okahu/Monocle env vars; add a `LOG_LEVEL` line if you reference `LOG_LEVEL` from `Settings`.

### Interface and contract

`config/settings.py` defines a Pydantic-Settings `Settings` class with these fields (env var alias in parens):

| Field | Type | Default | Notes |
|---|---|---|---|
| `server_name` | `str` | `"Deep Research MCP Server"` | |
| `version` | `str` | `"0.1.0"` | |
| `log_level` | `int` | `logging.INFO` (`LOG_LEVEL`) | Pydantic alias `LOG_LEVEL` |
| `llm_model` | `str` | `"meta-llama/Llama-3.3-70B-Instruct"` | Default Nebius-hosted model |
| `youtube_transcription_model` | `str` | `"meta-llama/Llama-3.3-70B-Instruct"` | Nebius model for transcript summarization |
| `nebius_base_url` | `str` | `"https://api.studio.nebius.com/v1/"` | OpenAI-compatible Nebius base URL |
| `nebius_api_key` | `SecretStr` | required | Pydantic alias `NEBIUS_API_KEY` |
| `exa_api_key` | `SecretStr` | required | Pydantic alias `EXA_API_KEY` |
| `okahu_api_key` | `SecretStr \| None` | `None` | Alias `OKAHU_API_KEY`; reserved for #020 |
| `monocle_exporter` | `str \| None` | `"file"` | Alias `MONOCLE_EXPORTER`; reserved for #020 |
| `okahu_workflow_name` | `str` | `"research-agent"` | Alias `OKAHU_WORKFLOW_RESEARCH`; reserved for #020 |

`Settings` uses `SettingsConfigDict(env_file=".env", extra="ignore", env_file_encoding="utf-8")`. Provide a `@lru_cache`-decorated `get_settings() -> Settings` factory so the singleton is shared.

`config/constants.py` declares the file/folder name string constants used across the package — populate with at least:

- `RESEARCH_MD_FILE = "research.md"`
- `RESEARCH_RESULTS_FILE = "research_results.json"`
- `MEMORY_FOLDER = ".memory"`
- `TRANSCRIPTS_FOLDER = "transcripts"`

(Subsequent tasks will add `EXPLORATION_STATE_FILE` and `MAX_EXPLORATION_CALLS`.)

`utils/logging.py` exposes `setup_logging(level: int = logging.INFO) -> None` that calls `logging.basicConfig` with the format `"%(asctime)s - %(name)s - %(levelname)s - %(message)s"`.

`server.py` exports a module-level `mcp` object so `fastmcp run src/research/server.py` finds it. Public surface:

- `def create_mcp_server() -> FastMCP` — constructs a `FastMCP(name=settings.server_name, version=settings.version)` and *will* call `register_mcp_tools/resources/prompts(mcp)` once those routers exist (in later tasks). For this task, leave the registration calls commented out or guarded so the module imports clean.
- Module-level: call `setup_logging(level=get_settings().log_level)`, then `mcp = create_mcp_server()`. Add an `if __name__ == "__main__": mcp.run()` for local sanity.
- DO NOT import `register_mcp_tools` etc. yet — those modules don't exist. Leave a `# TODO(#002)` marker where they will be wired in.

`.mcp.json` includes the `deep-research` entry:

```json
{
  "mcpServers": {
    "deep-research": {
      "command": "uv",
      "args": ["run", "fastmcp", "run", "src/research/server.py"],
      "env": { "ENV_FILE_PATH": ".env" }
    }
  }
}
```

Do **not** delete existing MCP server entries — merge/preserve them.

### Notes

- The package name is `research`, not `src.research`. The Makefile already exports `PYTHONPATH=./src/`, so absolute imports look like `from research.config.settings import get_settings`.
- The `[tool.hatch.build.targets.wheel] packages = ["src/research", "src/writing"]` line in `pyproject.toml` already declares both packages — do not modify.
- The `__init__.py` files inside `config/`, `utils/`, `routers/`, `tools/`, `app/`, `models/` already exist and are empty. Leave them empty unless you need to re-export something.

## Acceptance Criteria

- [ ] `Settings` class exists in `src/research/config/settings.py` with the fields and defaults above; `get_settings()` is `@lru_cache`d and returns a singleton.
- [ ] `setup_logging` works and is called once at server import time.
- [ ] `src/research/server.py` exposes a module-level `mcp` whose `name == "Deep Research MCP Server"` and `version == "0.1.0"`.
- [ ] `make run-research-server` boots the server without raising and prints (via stderr/log) the configured server name and version. The agent kills the process within ~5s — the goal is to prove startup, not to keep it running.
- [ ] `.mcp.json` contains a valid `deep-research` server entry pointing at `src/research/server.py`.
- [ ] `make format-check && make lint-check` pass after running the corresponding `*-fix` targets.

## User Stories

### Story: Workshop attendee boots the empty research server

1. The attendee runs `cp .env.example .env` and adds real `NEBIUS_API_KEY` and `EXA_API_KEY` values.
2. The attendee runs `make run-research-server`.
3. The terminal shows a log line like `INFO - research.server - Deep Research MCP Server v0.1.0` (or the FastMCP banner).
4. The process stays alive on stdio, waiting for a client.
5. The attendee hits Ctrl-C; the process exits cleanly.

### Story: Harness lists the server but finds zero tools

1. The attendee opens Claude Code or Cursor in the `implement_yourself/` directory.
2. The harness reads `.mcp.json` and connects to `deep-research`.
3. The MCP client lists tools — the list is empty (no tools registered yet).
4. The harness reports the connection as healthy. No errors.

### Story: Lint and format are green from day 1

1. The attendee runs `make format-fix && make lint-fix`.
2. Then runs `make format-check && make lint-check`.
3. Both checks return zero with no diagnostics.

---

Blocked by: (none)
