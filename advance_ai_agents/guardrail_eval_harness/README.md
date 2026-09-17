# Guardrail Evaluation Harness

> A CLI evaluation harness that measures whether an agent's guardrails actually protect its tools, using deterministic offline evidence instead of vibes.

An advanced AI agent project that runs a fictional customer-support agent (built with the OpenAI Agents SDK) against normal and adversarial scenarios, then scores the recorded traces with five deterministic DeepEval custom metrics: tool selection, safety enforcement, refusal behavior, injection resistance, and structured-output validity. Default runs are fully offline: scripted model responses drive real tool execution, no credentials are required, and no network calls are made. Optional live evaluation against a Nebius model reuses the same tools, policy, trace recorder, and metrics.

## 🚀 Features

- **Offline by default**: Scripted model responses exercise the real agent loop (tool calls, policy gates, final output) with zero credentials and networking denied under pytest.
- **Three safe mock tools**: `search_help_articles`, `get_ticket_status` (ownership-authorized), and `create_ticket_draft` (in-memory only; there is no way to submit or send anything).
- **Policy enforced at the tool boundary**: Schema validation, tool allowlists, ticket-ownership authorization, and argument bounds run before any tool body executes; blocked and undispatched attempts are recorded as evidence.
- **Five deterministic DeepEval metrics**: Plain custom metrics with threshold 1.0 — no LLM judges, no cloud calls, no flaky scores.
- **Negative controls**: A dedicated suite of intentionally bad behaviors (wrong arguments, refusal masking an executed action, over-refusal, malformed JSON, injection abandonment) proves the evaluators can fail. The CLI exits 1 there by design while pytest stays green.
- **Bounded CLI reporting**: Compact per-case output, exit codes 0/1/2 (pass / behavioral failures / configuration or runner errors), and optional schema-versioned JSON reports with overwrite protection.
- **Optional live mode**: Opt-in Nebius evaluation with lazy client initialization, explicit model selection, a per-case timeout, and no silent offline fallback.

## 🛠️ Tech Stack

- **Python 3.11+**: Core language
- **OpenAI Agents SDK** (`openai-agents`): Agent loop, tool execution, model interface
- **DeepEval**: Custom metric interface and evaluation execution
- **Pydantic**: Strict schemas for scenarios, traces, and reports
- **Nebius Token Factory** (optional): Live model provider via the OpenAI-compatible API
- **pytest + pytest-socket**: Offline test guarantees with denied networking

## Workflow

`scenario → input + trusted actor context → SDK runner → validated, policy-gated mock tools → recorded trace → DeepEval metrics → console/JSON report`

Scenario files split execution inputs from scoring expectations: the agent never sees what it is supposed to do. Every tool attempt (accepted, blocked, or undispatched) is recorded in a trace with the raw arguments, schema outcome, policy outcome, and execution evidence. Metrics score that evidence deterministically. Offline scripted responses establish harness correctness and enforcement behavior — they do not measure real-model prompt-injection robustness; use live mode (with bounded expectations) for behavioral observation.

## 📦 Getting Started

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) or pip
- No API keys needed for offline runs

### Environment Variables

None are required offline. For optional live evaluation, create a `.env` file (or export the variables) with:

```env
NEBIUS_API_KEY="your_nebius_api_key"
EXAMPLE_BASE_URL="https://api.tokenfactory.nebius.com/v1"  # optional override
```

An explicit model name is required on every live run; live mode never falls back to offline silently. See `.env.example`.

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

Optional live evaluation against Nebius (requires `NEBIUS_API_KEY` and an explicit tool-capable model):

```bash
python -m guardrail_eval_harness --mode live --case owned-ticket --live-model "meta-llama/Llama-3.3-70B-Instruct"
```

Exit codes: `0` all applicable checks passed, `1` completed evaluation with behavioral/schema failures, `2` invalid configuration, runner/provider errors, report-write failure, or empty selection.

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
│   ├── live.py               # Optional Nebius live backend
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
- [Nebius Token Factory](https://studio.nebius.com/) for optional inference.
