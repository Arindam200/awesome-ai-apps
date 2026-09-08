# Coding Harness Starter

> A compact PydanticAI example that inspects a repository, proposes a patch,
> waits for human approval, applies approved changes, and runs a fixed test command.

This starter demonstrates a complete coding-agent development loop without a
multi-agent graph, remote sandbox, or web UI. The language model receives only
read-only tools. Application code owns the approval, write, and test boundaries.

## 🚀 Features

- **Repository inspection**: `list_files` and `read_file` are scoped to one workspace.
- **Structured plan and patch**: Pydantic validates the agent's `ChangeProposal`.
- **Human-in-the-loop gate**: no file is written until the user enters `y` or `yes`.
- **Reviewable diff**: unified diffs are rendered before the approval prompt.
- **Allowlisted testing**: the harness runs only `python -m pytest -q`, without a shell.
- **Machine-readable result**: the proposal and final summary are printed as JSON.

## 🛠️ Tech Stack

- Python 3.10+
- [PydanticAI](https://ai.pydantic.dev/) for the typed agent and read-only tools
- [Nebius Token Factory](https://dub.sh/nebius) for OpenAI-compatible inference
- pytest for the fixture repository and workspace-boundary tests

## Workflow

```text
Task
  ↓
Inspect workspace (read-only tools)
  ↓
Structured plan + file proposal
  ↓
Render unified diff
  ↓
Human approval ── reject ──▶ stop without writes
  ↓ approve
Apply files inside workspace
  ↓
Run fixed pytest command
  ↓
JSON summary
```

The included fixture repository has a deliberately broken `calculator.add`
implementation. The default task asks the agent to repair it and verify the fix.

## 📦 Getting Started

### Prerequisites

- Python 3.10 or newer
- [uv](https://docs.astral.sh/uv/) or pip
- A Nebius Token Factory API key

### Environment Variables

Copy the example configuration and add your key:

```bash
cp .env.example .env
```

```env
NEBIUS_API_KEY="your_nebius_token_factory_api_key"
NEBIUS_MODEL="Qwen/Qwen3-30B-A3B"
```

Never commit the populated `.env` file.

### Installation

```bash
cd starter_ai_agents/coding_harness_starter
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

With uv:

```bash
uv sync --extra dev
```

## ⚙️ Usage

Run the seeded repair task:

```bash
uv run python main.py
```

Or provide another small coding task and workspace:

```bash
uv run python main.py "Add type hints to calculator.py" --workspace fixture_repo
```

The harness first prints the structured proposal and unified diff. Review them,
then enter `y` to approve. Any other response stops the run without writing files.

Run the harness safety tests without making an LLM request:

```bash
uv run pytest tests -q
```

Reset the deliberately broken fixture after a successful demo:

```bash
git restore fixture_repo/calculator.py
```

## Safety Boundaries

- All requested paths are resolved against the configured workspace. Absolute
  paths, `..` traversal, and symlinks that resolve outside the workspace fail.
- `.env`, `.git`, virtual-environment, and cache paths are never exposed through
  the inspection tools, including aliases created with symbolic links.
- The PydanticAI agent receives no write or shell tool. It can only return a
  structured proposal.
- `Workspace.apply_changes()` requires `approved=True`; the CLI supplies it only
  after an explicit `y` or `yes` response.
- Every proposed path is validated before the first file is written.
- A failed multi-file apply restores earlier files, avoiding a partially applied patch.
- Tests use a constant argument list and `shell=False`. The model cannot select or
  modify the command.
- File reads are capped at 50 KB to keep this educational starter bounded.
- Invalid proposals and test timeouts produce the same structured run-summary shape
  as successful and rejected runs.

This is a local workspace boundary, not an operating-system sandbox. For
untrusted repositories or commands, use a container or dedicated sandbox service.

## 📂 Project Structure

```text
coding_harness_starter/
├── agent.py                 # PydanticAI agent; read-only tools only
├── main.py                  # CLI workflow and approval prompt
├── models.py                # Structured proposal and result models
├── tools.py                 # list_files and read_file tools
├── workspace.py             # path boundary, writes, diff, fixed test runner
├── fixture_repo/
│   ├── calculator.py        # deliberately broken sample code
│   └── test_calculator.py   # sample repository tests
├── tests/
│   ├── test_agent.py        # offline structured-agent test
│   └── test_workspace.py    # boundary, approval, and test-loop tests
├── .env.example
├── pyproject.toml
└── README.md
```

## 🤝 Contributing

Contributions are welcome. See the repository's
[CONTRIBUTING.md](../../CONTRIBUTING.md) for the project and pull-request rules.

## 📄 License

This example follows the license of the parent Awesome AI Apps repository.

## 🙏 Acknowledgments

- [PydanticAI](https://ai.pydantic.dev/) for typed agents and dependency-injected tools
- [Nebius Token Factory](https://dub.sh/nebius) for model inference
