# Strands Temporal Agents

A comparison of two approaches to building AI agents: simple direct execution vs enterprise-grade distributed workflows.

This repository contains two example implementations:
1. **Simple Agent** - Basic file/time/weather operations
2. **Docker Container Health Monitor** - Production-ready DevOps monitoring

## Repository Structure

```
strands-temporal-agents/
├── config.py                    # Shared configuration
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
│
├── simple_agent/               # Basic agent demo
│   ├── agent.py                # Simple agent
│   ├── temporal_agent.py       # Temporal workflows
│   ├── worker.py               # Temporal worker
│   ├── client.py               # Temporal client
│   ├── test_workflow.py        # Tests
│   └── README.md               # Simple agent docs
│
└── docker_monitor/             # Docker monitoring agent
    ├── docker_agent.py         # Simple Docker agent
    ├── docker_temporal_agent.py # Temporal Docker agent
    ├── docker_worker.py        # Temporal worker
    ├── docker_client.py        # Temporal client
    ├── docker_utils.py         # Docker utilities
    ├── docker-compose.demo.yml # Demo containers
    ├── test_docker_agent_basic.py # Tests
    ├── validate_docker_monitor.py # Validation
    ├── README.md               # Docker monitor docs
    └── docs/                   # Demo guides
```

## What's This About?

Two different ways to build the same AI agent to show the trade-offs between simplicity and reliability:

- **Simple version** - Runs directly, great for development
- **Temporal version** - Distributed with retries, monitoring, and fault tolerance

---

## Docker Container Health Monitor

A practical DevOps use case demonstrating AI-powered Docker container monitoring.

**Location:** `docker_monitor/` directory

### Quick Start

```bash
cd docker_monitor

# Start demo containers
docker compose -f docker-compose.demo.yml up -d

# Run simple agent
python docker_agent.py

# Or run Temporal version (3 terminals)
temporal server start-dev    # Terminal 1
python docker_worker.py      # Terminal 2
python docker_client.py      # Terminal 3
```

### Features

- **Container Status Monitoring** - Check running/stopped containers
- **Health Checks** - Verify container health with CPU/memory metrics
- **Log Retrieval & Analysis** - View and analyze container logs
- **Container Restart** - Restart unhealthy containers
- **AI-Powered Interface** - Natural language queries

**See `docker_monitor/README.md` for complete documentation**

---

## Simple Agent (Basic Demo)

Basic file/time/weather operations demonstrating the Temporal pattern.

**Location:** `simple_agent/` directory

### Quick Start

```bash
cd simple_agent

# Run simple agent
python agent.py

# Or run Temporal version (3 terminals)
temporal server start-dev    # Terminal 1
python worker.py             # Terminal 2
python client.py             # Terminal 3
```

### Capabilities

- "What time is it?"
- "List Python files"
- "What's the weather in Tokyo?"

**See `simple_agent/README.md` for complete documentation**

---

## Prerequisites

- **Python 3.8+**
- **Nebius API Key** (for AI model access)
- **Temporal CLI** (for Temporal versions)
- **Docker** (for Docker monitor demo)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

## Configuration

Environment variables (optional):
```bash
export NEBIUS_API_KEY=your_nebius_api_key
export NEBIUS_MODEL_ID=nebius/deepseek-ai/DeepSeek-V3-0324
export TEMPORAL_HOST=localhost:7233
```

All configuration is centralized in `config.py`.

## Why Two Versions?

The simple version is perfect for prototyping and development. The Temporal version adds enterprise features:

- ✅ Automatic retries when things fail
- ✅ Complete execution history
- ✅ Distributed processing
- ✅ Web UI for monitoring at `http://localhost:8233`
- ✅ Fault tolerance

## Architecture

**Simple Agent:**
```
User Query → Agent → Tools → Result
```

**Temporal Agent:**
```
User Query → Client → Temporal Server → Worker → Activities → Result
```

The Temporal version is more complex but handles failures gracefully and scales across multiple machines.

## Screenshots

![Temporal Workflows](images/temporal-workflows-overview.png)
*Workflow monitoring dashboard*

![Workflow Details](images/workflow-execution-details.png)
*Detailed execution traces*

![Activity History](images/activity-execution-history.png)
*Individual activity tracking*

## Documentation

- **simple_agent/README.md** - Simple agent documentation
- **docker_monitor/README.md** - Docker monitor documentation
- **docker_monitor/docs/** - Demo guides and structure

## Troubleshooting

**Worker won't start?** Make sure Temporal server is running first.

**Tasks failing?** Check the Temporal UI at `http://localhost:8233` for error details.

**Nebius model issues?** Verify `NEBIUS_API_KEY` is set and model ID is valid.

**Docker issues?** Ensure Docker Desktop is running with `docker ps`.

## The Point

This shows how you can start simple and add enterprise features when you need them. The core agent logic stays the same - you're just changing how it runs.

Start with the simple version for rapid development, then switch to Temporal when you need production-grade reliability.
