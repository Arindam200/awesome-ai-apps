# Diff Stack Code Agent

A multi-agent coding harness where the AI can only **propose** changes. A LangGraph crew — planner, explorer, coder, tester — works on a real repo, but every edit the coder wants to make lands on a **diff stack**: a queue of unified diffs that pauses the graph and waits for *you*. Approve a diff and it's written to disk; reject it with a reason and the coder revises. The tester then runs the pytest suite in an isolated E2B sandbox, and the loop repeats until the tests are green.

## 🚀 Features

- **Diff-stack human-in-the-loop**: the coder never writes to disk. It calls `propose_edit`, which computes a unified diff and queues it for review. LangGraph's native `interrupt()` pauses the run; your per-diff approve/reject decisions resume it via `Command(resume=...)`.
- **Feedback loop on rejection**: rejection reasons are fed back into the coder's next prompt, so it revises instead of retrying blindly.
- **Role-separated agents**: a planner drafts the approach, an explorer reads the code (never guesses), a coder proposes diffs, and a tester reports real pytest results — the coder can't claim tests pass without the tester running them.
- **Sandboxed test runs**: the workspace is uploaded to a fresh [E2B](https://e2b.dev) VM for every test run — nothing executes on your machine.
- **Resumable by design**: a LangGraph checkpointer keeps the paused run's full state across Streamlit reruns; each run is a thread you can abandon and restart with one click.
- **Ships with a real ticket**: a buggy `workspace/cart.py` with 3 failing tests (double-applied discount, crash on removing a missing item, quantity-blind total) so the full loop is exercised out of the box.

## 🛠️ Tech Stack

- **[LangGraph](https://langchain-ai.github.io/langgraph/)** — StateGraph orchestration, `interrupt()` human-in-the-loop, checkpointing
- **[LangChain](https://python.langchain.com/)** + **[langchain-nebius](https://pypi.org/project/langchain-nebius/)** — tool-calling agents on `ChatNebius`
- **[Nebius Token Factory](https://tokenfactory.nebius.com/)** — LLM inference (default: `Qwen/Qwen3-30B-A3B`)
- **[E2B](https://e2b.dev)** — isolated sandbox for running the test suite
- **[Streamlit](https://streamlit.io/)** — diff review UI

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
- A [Nebius Token Factory](https://tokenfactory.nebius.com/) API key
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
cd advance_ai_agents/diff_stack_code_agent

# with uv (preferred)
uv sync

# or with pip
pip install -e .
```

## ⚙️ Usage

```bash
streamlit run app.py
```

1. Keep the default objective (fix the failing `cart.py` tests) or write your own, then click **Start run**.
2. When the diff stack appears, review each diff. Try rejecting one with a reason like *"don't raise, make it a silent no-op"* and watch the coder's next proposal address it.
3. Approve the diffs, let the tester run, and repeat until the banner turns green.

Reset the sample project between runs:

```bash
git restore workspace/
```

> **Note**: the checkpointer is in-memory (`InMemorySaver`), so a paused run survives Streamlit reruns but not a process restart. Swap in `SqliteSaver` from `langgraph-checkpoint-sqlite` if you want durability across restarts.

## 📂 Project Structure

```
diff_stack_code_agent/
├── app.py                  # Streamlit driver: start/resume the graph, render the diff stack
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

- Inspired by the coding-agent harness pattern from [ai-engineering-hub](https://github.com/patchy631/ai-engineering-hub) — reimagined here with a reviewable diff stack instead of direct file writes.
- [Nebius Token Factory](https://tokenfactory.nebius.com/) for inference and [E2B](https://e2b.dev) for sandboxing.
