# Coding Harness Starter

A compact, terminal-based OpenAI Agents SDK example powered by Nebius Token Factory for learning a safe coding-agent loop: inspect a small workspace, plan a change, preview a structured patch, request approval, run fixed tests, and review a failure.

It is intentionally a teaching project, not a general-purpose autonomous coding tool. The included `fixture_repo/` starts as a tiny todo application whose tests pass before the example task is implemented.

## Features

- Single-process CLI and a single Agent SDK agent.
- Read-only workspace inspection: list files, read text files, and search text.
- Structured `create` and `update` proposals, locally validated before use.
- A complete unified-diff preview and explicit `y/N` approval before every write.
- A single fixed `unittest` command and at most three approved edit attempts.
- A small, resettable todo fixture for experimenting without risking a real project.

## Requirements

- Python 3.10 or later.
- A [Nebius Token Factory](https://dub.sh/nebius) API key.
- `uv` or `pip` for installation.

The project uses the OpenAI Agents SDK and `python-dotenv`. It does not start a web server or require a browser.

## Install and configure

From the repository root:

```bash
cd starter_ai_agents/coding_harness_starter
python -m venv .venv
```

Activate the environment with `.venv\Scripts\activate` on Windows or `source .venv/bin/activate` on POSIX, then install the project:

```bash
python -m pip install -e .
# or: uv sync
```

Copy `.env.example` to `.env` and set your Nebius API key. On POSIX shells:

```bash
cp .env.example .env
```

In PowerShell:

```powershell
Copy-Item .env.example .env
```

Then edit `.env` with your Nebius settings:

```env
NEBIUS_API_KEY=your_nebius_api_key_here
MODEL_BASE_URL=https://api.tokenfactory.nebius.com/v1
MODEL_NAME=moonshotai/Kimi-K2.7-Code
```

`NEBIUS_API_KEY` is required. `MODEL_BASE_URL` and `MODEL_NAME` are optional overrides; their defaults match the Nebius configuration used by other starter projects in this repository. Never commit `.env`, API keys, certificates, or private workspace files. Configuration errors identify the missing setting without echoing its value.

## Run it interactively

Start without arguments to use the included fixture:

```bash
python main.py
```

The program then asks for a non-empty coding task. It deliberately has no `--task` flag and does not take the task from an environment variable or file. Try this task at the prompt:

```text
Add completed-status filtering to the todo list. Support all, completed, and pending; reject invalid values with a clear error; add tests.
```

For a trusted, small Python workspace of your own, provide its root at startup. The task is still entered only after the program starts:

```bash
python main.py --workspace ../my_small_workspace
```

The custom workspace must have standard-library `unittest` tests discoverable from `tests/`. This MVP is not a runner for pytest, JavaScript, or arbitrary build commands.

## What happens in one run

1. The CLI resolves and locks one workspace root.
2. The agent uses only bounded, read-only inspection tools.
3. It returns a short plan: understanding, files to change, steps, tests, and assumptions.
4. Local code validates the untrusted structured proposal. Invalid model output or a rejected path gets one zero-write correction opportunity with bounded feedback; a second invalid proposal stops before preview, approval, or writes.
5. Once a proposal is valid, the harness displays changed-file categories plus complete unified diffs.
6. Type `y` to approve; anything else (including Enter) declines.
7. The harness applies the validated operations, then runs the fixed test command.
8. A failed test result may be reviewed for a new proposal, with a fresh preview and approval each time. There are at most three edit attempts in one run; approved changes remain if the final test run fails.

## Approval, workspace, and command boundaries

The agent never writes files and never receives a shell or command-execution tool. The deterministic local layer owns validation, diff generation, approval, application, and test execution.

- Every patch path must be a relative path that resolves inside the locked workspace. Absolute paths, `..` traversal, and symbolic-link paths are rejected.
- A `create` operation adds a file only; it does not create directories. Its parent must already exist in the locked workspace. In the default fixture, `todo.py` and `tests/test_todo.py` are already relative to the workspace root, so a new test should use a path such as `tests/test_filtering.py`—not `fixture_repo/tests/test_filtering.py`.
- Only bounded UTF-8 text files with approved extensions are accessible. Sensitive files such as `.env`, keys, and certificates; binary content; oversized files; and common generated/dependency directories are refused.
- The system checks operations as a complete group before writing, detects stale targets before application, and rejects duplicate/conflicting operations.
- For broad OpenAI-compatible endpoint support, the SDK's final text must be exactly one JSON object (a single `json` code fence is also accepted) and is parsed into the strict Pydantic proposal model locally. Surrounding prose, multiple objects, or unknown fields are rejected before preview or approval.
- The only test invocation is displayed before approval and is fixed to `python -m unittest discover -s tests -v` (internally using the current Python executable, argv form, `shell=False`, and the locked workspace as `cwd`). Neither the user nor the model can override it.

These controls reduce accidental damage but are not an operating-system sandbox. Run only against workspaces you trust and review every diff before approval.

## Test the harness and fixture

Run harness tests from this project directory:

```bash
python -m unittest discover -s tests -v
```

The default fixture uses the same fixed discovery contract, but must be run with its directory as the working directory:

```bash
cd fixture_repo
python -m unittest discover -s tests -v
```

Initially, the fixture tests pass and its `list_todos` function only lists all todos. The sample task intentionally asks the agent to add status filtering and new tests.

## Reset the fixture

The default workspace is edited in place. Before experimenting, save unrelated work and inspect the fixture changes afterward:

```bash
git status -- starter_ai_agents/coding_harness_starter/fixture_repo
git diff -- starter_ai_agents/coding_harness_starter/fixture_repo
```

To restore only the tracked fixture files to the committed baseline, use a path-limited command from the repository root:

```bash
git restore --source=HEAD --staged --worktree -- starter_ai_agents/coding_harness_starter/fixture_repo
```

This does not use `git reset --hard` and does not intentionally affect the rest of the repository. If your Git version lacks `restore`, use `git checkout HEAD -- starter_ai_agents/coding_harness_starter/fixture_repo` instead; it is likewise restricted to that path.

## Project layout

```text
coding_harness_starter/
├── coding_harness/       # agent, workspace policy, patching, approval, tests, runner
├── fixture_repo/         # tiny todo workspace used by default
│   ├── todo.py
│   └── tests/test_todo.py
├── tests/                # deterministic harness unit tests
├── .env.example
├── main.py
├── pyproject.toml
└── README.md
```

## Limits

- No multi-agent orchestration, persistent memory, Git automation, IDE/UI, containers, or OS-level sandboxing.
- No arbitrary shell commands, custom runtime test commands, automatic rollback, or support for large monorepos.
- Test output and workspace reads are deliberately size-limited.
- A failed final test run is reported honestly and leaves already approved changes in place.

## License

This example is distributed under the repository's [MIT License](../../LICENSE).

## Contributing

Keep additions small, use explicit tests, do not include real secrets or generated artifacts, and follow the repository's [contribution guide](../../CONTRIBUTING.md).
