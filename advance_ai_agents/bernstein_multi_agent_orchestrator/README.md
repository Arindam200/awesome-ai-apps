# Bernstein Multi-Agent Orchestrator

> One command. Multiple AI agents. Your codebase moves forward while you sleep.

A deterministic multi-agent orchestrator that spawns parallel CLI coding agents (Claude Code, Codex CLI, Gemini CLI), verifies results with tests, and commits clean code. Zero LLM tokens spent on coordination.

## Features

- **Parallel Agent Orchestration**: Spawns multiple AI agents working simultaneously in isolated git worktrees
- **Provider-Agnostic**: Works with Claude Code, Codex CLI, Gemini CLI, or Qwen — mix models in the same run
- **Built-in Verification**: Janitor checks that tests pass, linter is clean, and no regressions before merging
- **Deterministic Scheduling**: Pure Python orchestration with zero LLM overhead on coordination
- **Live Dashboard**: Web UI and terminal TUI for monitoring agent progress
- **Self-Evolution**: Agents can improve their own prompts with safety gates

## Tech Stack

- **Python 3.12+**: Core language
- **Flask**: Demo application (the target that agents improve)
- **Bernstein**: Multi-agent orchestrator
- **Claude Code / Codex CLI / Gemini CLI**: AI coding agents (use whichever you have installed)
- **pytest**: Test verification

## How It Works

1. **Start** with a minimal Flask TODO API — intentionally missing validation, error handling, and tests
2. **Run** `bernstein` — it reads the goal from `bernstein.yaml`
3. **Bernstein** decomposes the goal into parallel tasks and assigns them to agents by role (`backend`, `qa`)
4. **Each agent** gets an isolated git worktree to work in — no conflicts, no interference
5. **The janitor** verifies each agent's output: tests pass, linter clean, no regressions
6. **Results merge** automatically into a clean commit history

```
bernstein.yaml          app.py (before)
     │                       │
     ▼                       ▼
┌─────────────────────────────────────┐
│           Bernstein                 │
│  ┌──────────┐  ┌──────────┐        │
│  │ backend  │  │    qa    │        │
│  │  agent   │  │  agent   │        │
│  └────┬─────┘  └────┬─────┘        │
│       │              │              │
│       ▼              ▼              │
│    Janitor: tests pass? lint ok?    │
└──────────────────┬──────────────────┘
                   ▼
           app.py (after)
      + validation + error handling
      + full test suite
      + clean git history
```

## Getting Started

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) or pip
- At least one AI coding agent installed:
  - [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (`npm install -g @anthropic-ai/claude-code`)
  - [Codex CLI](https://github.com/openai/codex) (`npm install -g @openai/codex`)
  - [Gemini CLI](https://github.com/google-gemini/gemini-cli) (`npm install -g @anthropic-ai/gemini-cli`)

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/advance_ai_agents/bernstein_multi_agent_orchestrator
   ```

2. **Install dependencies:**

   ```bash
   uv sync
   ```

3. **Install Bernstein:**

   ```bash
   pipx install bernstein
   # or: uv tool install bernstein
   ```

### Usage

1. **Run the "before" app** to see its current state:

   ```bash
   python app.py
   # Visit http://localhost:5000/todos
   ```

2. **Run Bernstein** to improve it with parallel agents:

   ```bash
   bernstein
   ```

   Bernstein reads `bernstein.yaml`, spawns agents, and produces validated results.

3. **Check the results** — Bernstein commits directly:

   ```bash
   git log --oneline
   ```

### Configuration

Edit `bernstein.yaml` to customize the orchestration:

```yaml
goal: "Add input validation, error handling, and tests to the TODO API"
cli: claude          # or: codex, gemini, qwen
team: [backend, qa]  # agent roles
budget: "$5"         # safety spend limit
```

## Project Structure

```
bernstein_multi_agent_orchestrator/
├── app.py              # Flask TODO API (the "before" state)
├── bernstein.yaml      # Orchestration config
├── pyproject.toml      # Python dependencies
└── README.md           # This file
```

## Resources

- [Bernstein GitHub](https://github.com/chernistry/bernstein)
- [Documentation](https://chernistry.github.io/bernstein/)
- [Examples](https://github.com/chernistry/bernstein/tree/main/examples)

## License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.