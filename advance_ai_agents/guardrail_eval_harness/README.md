# Guardrail Evaluation Harness

> A CLI evaluation harness that measures whether an agent's guardrails actually protect its tools, using deterministic offline evidence instead of vibes.

An advanced AI agent project that runs a fictional customer-support agent (built with the OpenAI Agents SDK) against normal and adversarial scenarios, then scores the recorded traces with five deterministic DeepEval custom metrics: tool selection, safety enforcement, refusal behavior, injection resistance, and structured-output validity. Default runs are fully offline: scripted model responses drive real tool execution, no credentials are required, and no network calls are made. Optional live evaluation runs the same agent on a Nebius Token Factory model through the OpenAI-compatible API, reusing the same tools, policy, trace recorder, and metrics.

## 🚀 Features

- **Offline by default**: Scripted model responses exercise the real agent loop (tool calls, policy gates, final output) with zero credentials and networking denied under pytest.
- **Three safe mock tools**: `search_help_articles`, `get_ticket_status` (ownership-authorized), and `create_ticket_draft` (in-memory only; there is no way to submit or send anything).
- **Policy enforced at the tool boundary**: Schema validation, tool allowlists, ticket-ownership authorization, and argument bounds run before any tool body executes; blocked and undispatched attempts are recorded as evidence.
- **Five deterministic DeepEval metrics**: Plain custom metrics with threshold 1.0 — no LLM judges, no cloud calls, no flaky scores.
- **Negative controls**: A dedicated suite of intentionally bad behaviors (wrong arguments, refusal masking an executed action, over-refusal, malformed JSON, injection abandonment) proves the evaluators can fail. The CLI exits 1 there by design while pytest stays green.
- **Bounded CLI reporting**: Compact per-case output, exit codes 0/1/2 (pass / behavioral failures / configuration or runner errors), and optional schema-versioned JSON reports with overwrite protection.
- **Live evaluation on Nebius Token Factory**: The agent under test runs on a real Nebius model via the OpenAI-compatible API — lazy client initialization, model chosen via `--live-model` or `EXAMPLE_MODEL_NAME`, a per-case timeout, and no silent offline fallback.

## 🛠️ Tech Stack

- **Python 3.11+**: Core language
- **OpenAI Agents SDK** (`openai-agents`): Agent loop, tool execution, model interface
- **DeepEval**: Custom metric interface and evaluation execution
- **Pydantic**: Strict schemas for scenarios, traces, and reports
- **Nebius Token Factory**: Model provider for live evaluation via the OpenAI-compatible API (offline runs need no provider)
- **pytest + pytest-socket**: Offline test guarantees with denied networking

## Workflow

`scenario → input + trusted actor context → SDK runner → validated, policy-gated mock tools → recorded trace → DeepEval metrics → console/JSON report`

Scenario files split execution inputs from scoring expectations: the agent never sees what it is supposed to do. Every tool attempt (accepted, blocked, or undispatched) is recorded in a trace with the raw arguments, schema outcome, policy outcome, and execution evidence. Metrics score that evidence deterministically. Offline scripted responses establish harness correctness and enforcement behavior — they do not measure real-model prompt-injection robustness; use live mode (with bounded expectations) for behavioral observation.

## 📦 Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) or pip
- No API keys needed for offline runs
- A free [Nebius Token Factory](https://studio.nebius.com/) API key for live evaluation only — new accounts include trial credit and no credit card is required

### Environment Variables

None are required offline. For live evaluation, copy `.env.example` to `.env` (the CLI loads it automatically; exported variables work too):

```env
NEBIUS_API_KEY="your_nebius_api_key"
EXAMPLE_MODEL_NAME="Qwen/Qwen3-30B-A3B-Instruct-2507"
EXAMPLE_BASE_URL="https://api.tokenfactory.nebius.com/v1"  # optional override
```

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `NEBIUS_API_KEY` | Live only | Nebius Token Factory API key from [studio.nebius.com](https://studio.nebius.com/) |
| `EXAMPLE_MODEL_NAME` | Live only, unless `--live-model` is passed | Default live model; must support tool calling |
| `EXAMPLE_BASE_URL` | No | Nebius OpenAI-compatible endpoint override |

`--live-model` always wins over `EXAMPLE_MODEL_NAME`, and live mode never falls back to offline silently. See `.env.example`.

### Installation

1. **Clone the repository:**

   ```bash
   git clone https://github.com/Arindam200/awesome-ai-apps.git
   cd awesome-ai-apps/advance_ai_agents/guardrail_eval_harness
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
   ```

3. **Install dependencies:**

   - **Using `uv` (recommended):**

     ```bash
     uv pip install -e '.[dev]'
     ```

   - **Using `pip`:**

     ```bash
     pip install -e '.[dev]'
     ```

## ⚙️ Usage

Run the default offline suite (normal + guarded scenarios; exits 0 when every applicable check passes):

```bash
python -m guardrail_eval_harness
```

Run one case, or write a JSON report:

```bash
python -m guardrail_eval_harness --case owned-ticket
python -m guardrail_eval_harness --report reports/offline.json
```

Run the negative-control suite (intentionally bad behavior; visible FAILs and exit 1 are the expected result):

```bash
python -m guardrail_eval_harness --suite negative-controls
```

Live evaluation on a Nebius Token Factory model (requires `NEBIUS_API_KEY`; the model comes from `EXAMPLE_MODEL_NAME` or `--live-model`):

```bash
# Model from .env (EXAMPLE_MODEL_NAME)
python -m guardrail_eval_harness --mode live --case owned-ticket

# Model chosen explicitly (must support tool calling)
python -m guardrail_eval_harness --mode live --case owned-ticket --live-model "Qwen/Qwen3-30B-A3B-Instruct-2507"
```

Exit codes: `0` all applicable checks passed, `1` completed evaluation with behavioral/schema failures, `2` invalid configuration, runner/provider errors, report-write failure, or empty selection.

### Live evaluation with Nebius Token Factory

Live mode sends each selected scenario's input to a real model hosted on Nebius Token Factory through the OpenAI-compatible API, records the resulting tool calls and final answer, and scores the trace with the same five metrics used offline.

1. **Get a key**: sign up at [studio.nebius.com](https://studio.nebius.com/). New accounts include free trial credit and no credit card is required — a full live suite here costs only a few thousand tokens (fractions of a cent).
2. **Configure**: `cp .env.example .env`, then set `NEBIUS_API_KEY`.
3. **Pick a tool-calling model** (required — the mock tools are the point of the harness). List current IDs:

   ```bash
   curl -s "$EXAMPLE_BASE_URL/models" -H "Authorization: Bearer $NEBIUS_API_KEY"
   ```

   Good current picks: `Qwen/Qwen3-30B-A3B-Instruct-2507`, `nvidia/nemotron-3-nano-30b-a3b`.
4. **Run**:

   ```bash
   python -m guardrail_eval_harness --mode live --report reports/live.json
   ```

Notes:

- The JSON report records `provider: "nebius"` and the exact `model` used, so every result is attributable and reproducible.
- Scenarios marked `"live_suitable": false` are skipped in live mode; everything else runs against the real model.
- A live model can genuinely fail adversarial cases — that is the harness measuring real guardrail behavior, not a bug. Offline runs prove harness correctness and policy enforcement; live runs show how a real model behaves against the same policy.

### Interpreting results

Each case prints per-metric lines: `PASS`, `FAIL`, `N/A`, or `ERROR`, with expected-versus-observed reasons. Metric semantics are deliberately separated:

- A model **attempting** a forbidden call can fail tool-selection or injection checks while safety enforcement passes, because execution was blocked. Both findings are printed; a blocked attempt is not proof the model is safe.
- A refusal after a prohibited executed action fails refusal behavior — refusal text does not undo execution.
- Errors (timeouts, scripted-response exhaustion, evaluator exceptions) are reported separately and never counted as passes.
- Offline results prove harness correctness and policy enforcement; they do not claim real-model security. Live output may still contain sensitive user-supplied text.

### Running the tests

```bash
python -m pytest
```

`pytest-socket` denies all sockets during tests (local Unix sockets excepted), and the project pins DeepEval/SDK telemetry opt-outs before import, so the suite cannot reach the network or cloud services.

## 📂 Project Structure

```
guardrail_eval_harness/
├── guardrail_eval_harness/   # Package source
│   ├── __main__.py           # python -m entry point
│   ├── cli.py                # Argument parsing and exit codes
│   ├── agent.py              # Scenario runner around the SDK
│   ├── backends.py           # Scripted offline model + live adapter use
│   ├── tools.py              # Three instrumented mock tools
│   ├── policy.py             # Fixtures, allowlists, authorization
│   ├── metrics.py            # Five DeepEval custom metrics
│   ├── evaluation.py         # Scenario evaluation engine
│   ├── scenarios.py          # Scenario loading/validation
│   ├── scenarios.json        # 20 focused cases (default + negative-controls)
│   ├── schemas.py            # Pydantic contracts (trace, report, final output)
│   ├── reporting.py          # Console rendering and JSON reports
│   ├── live.py               # Nebius live backend + live-model resolution
│   └── env.py                # Telemetry/tracing opt-outs applied pre-import
├── tests/                    # pytest suite (sockets denied)
├── pyproject.toml            # Dependencies, pytest/ruff/mypy config
├── .env.example              # Optional live-mode placeholders
└── README.md
```

## Extending

- Add a scenario: append a case to `scenarios.json` (unique ID, category, scripted responses, expectations). Validate with `python -m pytest tests/test_harness.py::TestScenarioLoading`.
- Add a metric: subclass `HarnessMetric` in `metrics.py`, register it in `METRIC_CLASSES`, and list it in `applicable_metrics` if category-gated.
- Swap the model: implement the SDK `Model` interface in `backends.py`; live mode wires any OpenAI-compatible client through `live.py`.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. See the [CONTRIBUTING.md](https://github.com/Arindam200/awesome-ai-apps/blob/main/CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](https://github.com/Arindam200/awesome-ai-apps/blob/main/LICENSE) file for details.

## 🙏 Acknowledgments

- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python) for the agent runtime.
- [DeepEval](https://github.com/confident-ai/deepeval) for the metric interface.
- [Nebius Token Factory](https://studio.nebius.com/) for live-model inference.
