# Wire Okahu/Monocle observability into both MCP servers

Status: pending
Tags: `observability`, `okahu`, `monocle`, `tracing`, `nebius`, `exa`
Depends on: #009, #019
Blocks: #021

## Scope

Hook Monocle tracing into both servers so major workflow stages, MCP tools, prompts, LLM calls, and eval runs are traced locally and optionally exported to Okahu Cloud. The feature is optional and additive: the system continues to work end-to-end when `OKAHU_API_KEY` is unset and `MONOCLE_EXPORTER` is not configured for cloud export.

This task introduces:

- `utils/okahu_utils.py` in both packages.
- `configure_okahu(workflow_name: str | None = None) -> bool` boot configuration.
- `trace_span(...)` / `atrace_span(...)` helpers wrapping Monocle's sync and async trace utilities.
- Tool, prompt, and major pipeline-stage spans with useful metadata.

### Files to create

- `implement_yourself/src/research/utils/okahu_utils.py`
- `implement_yourself/src/writing/utils/okahu_utils.py`

### Files to modify

- `implement_yourself/src/research/server.py` and `implement_yourself/src/writing/server.py` — call `configure_okahu()` at startup after `setup_logging`.
- `implement_yourself/src/research/routers/tools.py` and `implement_yourself/src/writing/routers/tools.py` — wrap each tool body in `atrace_span(...)`.
- `implement_yourself/src/research/routers/prompts.py` and `implement_yourself/src/writing/routers/prompts.py` — wrap each prompt body in `atrace_span(...)`.
- `implement_yourself/src/research/routers/resources.py` and `implement_yourself/src/writing/routers/resources.py` — expose Okahu/Monocle config fields without leaking secrets.
- `implement_yourself/.env.example` — document `OKAHU_API_KEY`, `MONOCLE_EXPORTER`, `OKAHU_WORKFLOW_RESEARCH`, and `OKAHU_WORKFLOW_WRITING`.
- `implement_yourself/.mcp.json` — include an Okahu MCP server example:
  - URL: `https://mcp.okahu.co/mcp`
  - header: `x-api-key: <OKAHU_API_KEY>`

### `okahu_utils.py` interface

The two package copies are intentionally separate because each package reads its own `Settings`.

```python
def configure_okahu(workflow_name: str | None = None) -> bool: ...

@contextmanager
def trace_span(span_name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]: ...

@asynccontextmanager
async def atrace_span(span_name: str, attributes: dict[str, Any] | None = None) -> AsyncIterator[None]: ...
```

Implementation requirements:

- Read `OKAHU_API_KEY`, `MONOCLE_EXPORTER`, and package-specific workflow name from settings.
- Set `os.environ["OKAHU_API_KEY"]` and `os.environ["MONOCLE_EXPORTER"]` before calling Monocle.
- Enable tracing when either:
  - `file` is present in `MONOCLE_EXPORTER`, or
  - `okahu` is present and `OKAHU_API_KEY` is set.
- Call `setup_monocle_telemetry(workflow_name=workflow)` exactly once per workflow per process.
- If Monocle setup fails, log the exception and return `False` without breaking the app.
- `trace_span` / `atrace_span` should fall back to a plain yielded block when Monocle cannot be imported, but must not swallow exceptions raised by the wrapped workflow body.
- When possible, set OpenTelemetry span status to OK on successful completion and ERROR on exceptions.

### Tool / prompt tracing pattern

`routers/tools.py` example:

```python
from research.utils.okahu_utils import atrace_span

@mcp.tool()
async def deep_research(working_dir: str, query: str) -> dict[str, Any]:
    """Research a topic using Exa search."""
    async with atrace_span(
        "mcp.tool.deep_research",
        {"working_dir": working_dir, "query": query},
    ):
        return await deep_research_tool(working_dir, query)
```

`routers/prompts.py` example:

```python
from research.utils.okahu_utils import atrace_span

@mcp.prompt()
async def research_workflow() -> str:
    """Return workflow instructions."""
    async with atrace_span("mcp.prompt.research_workflow"):
        return WORKFLOW_INSTRUCTIONS
```

### Server boot integration

After `setup_logging`, call `configure_okahu()`. If it returns `True`, log:

```text
Okahu/Monocle tracing enabled for workflow: <workflow-name>
```

## Acceptance Criteria

- [ ] With only `MONOCLE_EXPORTER=file`, `make test-research-workflow` and `make test-writing-workflow` both succeed and `.monocle/` trace files are created.
- [ ] With `OKAHU_API_KEY` and `MONOCLE_EXPORTER=file,okahu`, traces are visible in Okahu Cloud under `research-agent` and `writing-workflow`.
- [ ] Tool and prompt spans include useful attributes such as `working_dir`, `query`, `youtube_url`, `post_path`, and workflow name.
- [ ] No legacy eval-platform package, decorator, context helper, workspace/project config, or dataset upload flow remains.
- [ ] Resource endpoints expose `has_okahu_api_key`, `monocle_exporter`, and the relevant workflow name, never the secret key value.
- [ ] `make format-check && make lint-check` pass.

## User Stories

### Story: Operator with Okahu Cloud

1. Operator sets `OKAHU_API_KEY` and `MONOCLE_EXPORTER=file,okahu` in `.env`.
2. Reruns `make test-research-workflow`.
3. Opens Okahu Cloud and sees a `research-agent` workflow trace with tool spans.
4. Drills into a `mcp.tool.deep_research` span and sees query metadata and nested model/search spans.

### Story: Operator using only local tracing

1. Operator sets `MONOCLE_EXPORTER=file` and leaves `OKAHU_API_KEY` blank.
2. Both test workflows still pass.
3. Local `.monocle/` JSON traces are created; no cloud export is attempted.

### Story: Tracing never masks failures

1. A tool raises a real exception.
2. The exception propagates to the caller.
3. The span is marked as an error when Monocle/OpenTelemetry status is available.

---

Blocked by: #009 and #019.
