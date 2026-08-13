# Local temporal-memory agent with Lians and PydanticAI

> A deterministic agent that remembers a corrected fact locally while preserving
> the earlier fact for point-in-time recall.

This example shows why durable agent memory needs more than storing conversation
text. A shipping estimate changes from Friday to Monday. Present-time recall
returns only Monday, while a historical query reconstructs the Friday estimate
without leaking the later correction.

## Features

- **Local durable memory:** SQLite storage through the open-source
  [Lians](https://github.com/Lians-ai/Lians) client.
- **Current truth:** Superseded facts are excluded from ordinary recall.
- **Historical truth:** `recall_at` reconstructs what was valid before a change.
- **Real agent tools:** Two explicit memory tools are called by PydanticAI agents.
- **No API keys:** PydanticAI's deterministic `TestModel` keeps the demo free and
  reproducible.
- **Executable verification:** Assertions fail if current and historical facts
  contaminate one another.

## Tech stack

- Python 3.11+
- [PydanticAI](https://ai.pydantic.dev/) for the agent and tool loop
- [Lians](https://github.com/Lians-ai/Lians) for local temporal memory
- SQLite for persistent storage

## Workflow

```text
original fact (Friday) ─┐
                        ├─ Lians local memory ─ current recall ─ Monday
later correction ───────┘                     └ recall_at ───── Friday
```

1. Store the original shipping estimate with its event time.
2. Store a later correction for the same entity and field.
3. Let one PydanticAI tool ask for the currently valid estimate.
4. Let another tool ask what was valid before the correction.
5. Verify that neither query leaks the wrong temporal state.

## Getting started

### Prerequisites

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) or pip

No Lians account, hosted service, model-provider key, or other credential is
required.

This educational example uses synthetic facts, Lians' deterministic local test
embedding, and unencrypted local storage so every contributor sees the same
result. For real data, configure a master encryption key and use the
`sentence-transformers` embedding provider as described in the
[Lians installation guide](https://github.com/Lians-ai/Lians/blob/master/docs/install.md).

### Installation with uv

```bash
git clone https://github.com/Arindam200/awesome-ai-apps.git
cd awesome-ai-apps/memory_agents/lians_temporal_memory_agent
uv sync
```

### Installation with pip

```bash
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e .
```

## Usage

Run the agent with uv:

```bash
uv run python main.py
```

Or, from the activated pip environment:

```bash
python main.py
```

Expected memory results:

```text
Current recall: ["Order 1842 shipping estimate changed to Monday"]
Historical recall: ["Order 1842 shipping estimate is Friday"]
```

Run the executable verification with uv:

```bash
uv run python verify.py
```

Or, from the activated pip environment:

```bash
python verify.py
```

The example stores its SQLite database under `.data/`. Delete that directory to
start with a fresh local memory store. Replace `TestModel` with your normal
PydanticAI model to use the same tools in a live agent.

## Project structure

```text
lians_temporal_memory_agent/
├── .env.example       # Documents that no credentials are needed
├── .gitignore         # Excludes the local database and environment
├── .python-version    # Suggested Python version
├── main.py            # PydanticAI tools and temporal-memory demo
├── pyproject.toml     # Reproducible dependencies
├── README.md          # Setup and architecture
└── verify.py          # Contamination and receipt assertions
```

## Related resources

- [Lians repository](https://github.com/Lians-ai/Lians)
- [Lians local installation guide](https://github.com/Lians-ai/Lians#quickstart)
- [PydanticAI tools documentation](https://ai.pydantic.dev/tools/)

## License

This example is part of the Awesome AI Apps collection and follows the
repository's MIT license.
