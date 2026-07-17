# Coding Agent Harness

A deep coding agent built as a complete harness: planning, repository exploration, code generation, human approval, sandboxed test execution, and iterative repair. A LangGraph crew of planner, explorer, coder, and tester agents works on a real sample repo. The coder can only **propose** file changes. The graph pauses before disk writes, waits for your approval or rejection feedback, then verifies approved code in an isolated E2B sandbox.

The terminal is the primary experience, like the harness in [ai-engineering-hub PR #252](https://github.com/patchy631/ai-engineering-hub/pull/252). This version uses LangGraph and Nebius, adds per-file patch review, and keeps Streamlit as an optional visual reviewer.

## 🚀 Features

- **Human-gated file edits**: the coder never writes to disk. It calls `propose_edit`, which computes a unified diff and queues it for review. LangGraph's native `interrupt()` pauses the run; your per-file approve/reject decisions resume it via `Command(resume=...)`.
- **Feedback loop on rejection**: rejection reasons are fed back into the coder's next prompt, so it revises instead of retrying blindly.
- **Role-separated agents**: a planner drafts the approach, an explorer reads the code (never guesses), a coder proposes diffs, and a tester reports real pytest results — the coder can't claim tests pass without the tester running them.
- **Sandboxed test runs**: the workspace is uploaded to a fresh [E2B](https://e2b.dev) VM for every test run — nothing executes on your machine.
- **Resumable by design**: a LangGraph checkpointer keeps the paused run's full state across Streamlit reruns; each run is a thread you can abandon and restart with one click.
- **Ships with a real ticket**: a buggy `workspace/cart.py` with 3 failing tests (double-applied discount, crash on removing a missing item, quantity-blind total) so the full loop is exercised out of the box.
- **Terminal-first demo**: the Rich CLI prints the real failing suite, streams the crew handoff, renders unified diffs, and collects approval or rejection feedback without leaving the terminal.
- **Offline rehearsal mode**: `--preview` walks through the ticket, plan, diff, and review decision with no API calls and no file writes.

## 🛠️ Tech Stack

- **[LangGraph](https://langchain-ai.github.io/langgraph/)** — StateGraph orchestration, `interrupt()` human-in-the-loop, checkpointing
- **[LangChain](https://python.langchain.com/)** + **[langchain-nebius](https://pypi.org/project/langchain-nebius/)** — tool-calling agents on `ChatNebius`
- **[Nebius Token Factory](https://dub.sh/nebius)** — LLM inference (default: `Qwen/Qwen3-30B-A3B`)
- **[E2B](https://e2b.dev)** — isolated sandbox for running the test suite
- **[Rich](https://rich.readthedocs.io/)** — terminal diff, status, and review presentation
- **[Streamlit](https://streamlit.io/)** — diff review UI

## Harness Architecture

| Layer | This project |
|---|---|
| Brain | Nebius-hosted tool-calling model, configurable with `NEBIUS_MODEL` |
| Hands | Scoped `list_dir`, `read_file`, and `propose_edit` workspace tools |
| Specialists | Planner, codebase explorer, coder, and sandbox tester |
| Orchestrator | LangGraph state machine with explicit routing and iteration limits |
| Deep-work loop | Plan → inspect → propose → review → test → revise until green |
| Permission layer | `interrupt()` stops execution before the only disk-write node |
| Checkpoint | `InMemorySaver` preserves the full paused graph state during the process |
| Sandbox | E2B receives the workspace and runs pytest in an ephemeral VM |

The approval boundary is enforced by graph structure, not by asking the model to behave. The coder does not receive a write tool. Only `apply_diffs_node`, which runs after human approval, can modify `workspace/`.

## Workflow

```
START ──▶ planner ──▶ explorer ──▶ coder ──▶ diff_review ⏸️ (interrupt: you review)
                                     ▲              │
                                     │              ▼ approved diffs only
                                     │         apply_diffs ──▶ tester (E2B sandbox)
                                     │                            │
                                     └── tests fail / rejected ◀──┤
                                         (with your feedback)     └── tests pass ──▶ END
```

1. **Planner** turns your objective + the workspace file tree into a short numbered plan.
2. **Explorer** reads the relevant files with `read_file`/`list_dir` and briefs the coder.
3. **Coder** proposes edits via `propose_edit` — full new file content, diffed mechanically with `difflib` (LLMs are unreliable at hand-writing valid patch hunks, so the diff is computed, not generated).
4. **Diff review** — the graph pauses on `interrupt()`. The Streamlit UI renders each pending diff with approve/reject controls. Your batched decisions resume the graph.
5. **Apply** — approved diffs are written to `workspace/`; rejections (with reasons) go into the coder's next briefing.
6. **Tester** uploads the workspace to an E2B sandbox and runs `pytest`. Green → done; red → back to the coder, up to `MAX_ITERATIONS`.

## 📦 Getting Started

### Prerequisites

- Python 3.10+
- A [Nebius Token Factory](https://dub.sh/nebius) API key
- An [E2B](https://e2b.dev) API key

### Environment Variables

```bash
cp .env.example .env
```

```env
NEBIUS_API_KEY="your_nebius_token_factory_api_key"
NEBIUS_MODEL="Qwen/Qwen3-30B-A3B"
E2B_API_KEY="your_e2b_api_key"
MAX_ITERATIONS="4"
```

### Installation

```bash
cd advance_ai_agents/coding_agent_harness

# with uv (preferred)
uv sync

# or with pip
pip install -e .
```

## ⚙️ Usage

### Terminal demo (recommended)

Run the real LangGraph crew and review every proposed patch in the terminal:

```bash
uv run python cli.py
```

The CLI first runs the seeded local suite so the audience sees the exact `3 failed, 2 passed` starting state. It then starts the planner, explorer, and coder. When a diff is ready, execution pauses and asks:

```text
Approve this patch? [y/n]
```

Choose `n` to give the coder a concrete revision request, or `y` to apply the diff and send the workspace to E2B for verification.

For a reliable rehearsal or recorded walkthrough with no keys, latency, API calls, or file writes:

```bash
uv run python cli.py --preview
```

For a non-interactive preview that ends on the approval outcome:

```bash
uv run python cli.py --preview --preview-decision approve
```

Pass a different ticket with `--objective`, or inspect every option with `--help`.

### Streamlit review UI

```bash
uv run streamlit run app.py
```

1. Keep the default objective (fix the failing `cart.py` tests) or write your own, then click **Start run**.
2. When the proposed changes appear, review each file. Try rejecting one with a reason like *"don't raise, make it a silent no-op"* and watch the coder's next proposal address it.
3. Approve the diffs, let the tester run, and repeat until the banner turns green.

Reset the sample project between runs:

```bash
git restore workspace/
```

> **Note**: the checkpointer is in-memory (`InMemorySaver`), so a paused run survives Streamlit reruns but not a process restart. Swap in `SqliteSaver` from `langgraph-checkpoint-sqlite` if you want durability across restarts.

## 📂 Project Structure

```
coding_agent_harness/
├── cli.py                  # Rich terminal runner + offline walkthrough
├── app.py                  # Optional Streamlit runner and visual change reviewer
├── demo_data.py            # Stable seeded ticket and representative patch for both demos
├── graph.py                # AgentState + planner/explorer/coder/diff_review/apply/tester nodes
├── tools.py                # read_file, list_dir, propose_edit (diff builder — never writes)
├── sandbox.py              # E2B wrapper: run pytest in an isolated VM
├── workspace/              # the "repo" the agents work on
│   ├── cart.py             # buggy shopping cart (3 seeded bugs)
│   └── tests/test_cart.py  # pytest suite: 3 failing, 2 passing
├── pyproject.toml
└── .env.example
```

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss the change, then submit a pull request. See the repo's [CONTRIBUTING.md](../../CONTRIBUTING.md).

## 📄 License

This project is part of the [awesome-llm-apps](https://github.com/Arindam200/awesome-llm-apps) collection and follows the repository's license.

## 🙏 Acknowledgments

- Inspired by [Add Coding Agent Harness, PR #252](https://github.com/patchy631/ai-engineering-hub/pull/252) — rebuilt with LangGraph, Nebius, and a per-file approval gate before disk writes.
- [Nebius Token Factory](https://dub.sh/nebius) for inference and [E2B](https://e2b.dev) for sandboxing.
