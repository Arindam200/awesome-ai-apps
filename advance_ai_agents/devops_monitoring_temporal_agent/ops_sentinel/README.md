# Ops Sentinel

Ops Sentinel is a Temporal-first runtime operations assistant for containerized services. It uses workflow orchestration, AI-assisted plan generation, and Docker runtime activities to execute operational requests reliably.

## Capabilities

- Runtime service discovery (running/all/filter by name)
- Health inspection with CPU/memory/restart signals
- Log collection per service with configurable line count
- Service recycle actions (restart + post-check)
- Natural language request planning into deterministic workflow steps

## Package Layout

- `runtime_gateway.py` - Docker runtime adapter and domain models
- `workflow_runtime.py` - Temporal activities and workflow logic
- `console.py` - Interactive console + worker launcher
- `doctor.py` - Validation diagnostics for local setup
- `test_ops_sentinel.py` - Quick structural tests
- `stack.compose.yml` - Sample local stack for demos

## Quick Start

```bash
cd ops_sentinel
docker compose -f stack.compose.yml up -d
```

Start Temporal:

```bash
temporal server start-dev
```

Start worker in a second terminal:

```bash
python console.py worker
```

Open console in a third terminal:

```bash
python console.py
```

## Example Requests

- `show running containers`
- `inspect health for demo-api`
- `fetch logs for demo-worker 50`
- `restart demo-cache and inspect health`

## Configuration

Use environment variables from the project root `.env.example`:

- `TEMPORAL_HOST`
- `OPS_SENTINEL_TASK_QUEUE`
- `NEBIUS_API_KEY`
- `NEBIUS_MODEL_ID`
- `DOCKER_HOST`
- `DOCKER_TIMEOUT`

## Validation

Run validation diagnostics:

```bash
python doctor.py
```

Run lightweight tests:

```bash
pytest test_ops_sentinel.py
```
