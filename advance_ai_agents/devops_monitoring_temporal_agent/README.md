# Ops Sentinel: Temporal Runtime Operations Assistant

Ops Sentinel is a workflow-driven operations assistant for Docker environments. It combines Temporal orchestration, Docker runtime activities, and an LLM-based planner to convert natural language requests into reliable operational steps.

## Project Structure

```
devops_monitoring_temporal_agent/
├── config.py
├── requirements.txt
├── .env.example
└── ops_sentinel/
    ├── __init__.py
    ├── console.py
    ├── doctor.py
    ├── runtime_gateway.py
    ├── workflow_runtime.py
    ├── stack.compose.yml
    ├── test_ops_sentinel.py
    └── README.md
```

## Core Features

- Service inventory and state inspection
- Health diagnostics (probe status + resource thresholds)
- Log retrieval for targeted services
- Recovery actions via service recycle (restart)
- Workflow-level retries, execution history, and fault tolerance
- AI-assisted plan generation from user requests

## Quick Start

Install dependencies:

```bash
pip install -r requirements.txt
```

Start demo runtime:

```bash
cd ops_sentinel
docker compose -f stack.compose.yml up -d
```

Start Temporal:

```bash
temporal server start-dev
```

Start worker:

```bash
python console.py worker
```

Run console:

```bash
python console.py
```

## Configuration

Set these in your environment or `.env`:

- `TEMPORAL_HOST`
- `OPS_SENTINEL_TASK_QUEUE`
- `NEBIUS_API_KEY`
- `NEBIUS_MODEL_ID`
- `DOCKER_HOST`
- `DOCKER_TIMEOUT`

## Validation

```bash
cd ops_sentinel
python doctor.py
pytest test_ops_sentinel.py
```

Detailed package documentation is in [ops_sentinel/README.md](ops_sentinel/README.md).
