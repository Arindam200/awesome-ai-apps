# Okahu / Monocle eval demo — Temporal transaction agent

A working demo of the loop the Monocle + Okahu team pitched:

1. Instrument an agentic app with **Monocle** → traces emitted as OpenTelemetry spans.
2. Ship them to **Okahu Cloud** (or read them locally with the **Okahu VS Code extension**).
3. Grade the traces with **`monocle_test_tools`** — deterministic assertions in pytest + LLM-graded evals (`check_eval("hallucination", …)` etc.) via the Okahu evaluator API.
4. When an eval regresses, hand the failure to a **coding agent** that edits the AI code and re-runs the suite until green.

The target app is `Arindam200/awesome-ai-apps` → `temporal_transaction_processing_ai_agent`, a FastAPI + Temporal + Couchbase + OpenAI fraud-detection sample. It uses no LangGraph/CrewAI/OpenAI-Agents-SDK, so it exercises Monocle's **custom framework** path via `WrapperMethod` registrations.

The vendored sample is kept 100% intact except for one-line `import monocle_bootstrap` at the top of `api/main.py` and `temporal/run_worker.py`. All Monocle wiring lives in a single new file: `temporal-tx-agent/monocle_bootstrap.py`.

---

## Prerequisites

- **Python 3.11+** (developed on 3.13.2)
- **git**
- **GNU make** — pre-installed on macOS/Linux. Windows: use WSL or `choco install make`.
- **An OpenAI-compatible LLM endpoint** — real OpenAI, or any endpoint that speaks the OpenAI wire protocol (Nebius, local vLLM/llama.cpp/LM Studio, etc.)
- Optional: **Okahu API key** (https://portal.okahu.co) for the LLM-graded eval suite
- Optional: **Claude Code CLI** (`npm install -g @anthropic-ai/claude-code`) for `make fix`

## Repo layout

```
temporal-tx-agent-eval/
├── temporal-tx-agent/            # vendored sample + Monocle wiring
│   ├── monocle_bootstrap.py      # setup_monocle_telemetry + WrapperMethods (ours)
│   ├── ai/llm_client.py          # UNTOUCHED — instrumentation lives in monocle_bootstrap
│   ├── ai/embedding_client.py    # UNTOUCHED
│   ├── api/main.py               # +1 line: `import monocle_bootstrap`
│   ├── temporal/run_worker.py    # +1 line: `import monocle_bootstrap`
│   ├── .env.example              # OPENAI + OKAHU keys, model overrides, base_url
│   ├── requirements.txt          # sample deps + monocle_apptrace
│   └── … (rest of the vendored sample — not exercised by the eval demo)
├── scenarios/                    # 5 transaction JSON inputs (ours)
├── evals/
│   ├── test_temporal_tx_coverage.py  # 5 offline + 1 live, deterministic
│   ├── test_temporal_tx_evals.py     # 10 LLM-graded evals via Okahu
│   ├── templates/fraud_reasoning.json # custom Okahu eval template
│   ├── traces/                   # populated by record_from_scenarios.py (gitignored)
│   ├── conftest.py               # autoloads .env
│   └── requirements.txt          # monocle_test_tools
├── record_from_scenarios.py      # runs each scenario, populates evals/traces/ (ours)
├── fix.sh                        # pipes failing pytest output into claude / gh copilot (ours)
├── Makefile                      # install / record / evals / evals-cloud / live / regress / fix / clean
├── README.md
└── .gitignore
```

## Quick start

Follow these steps verbatim from a fresh shell.

### 1. Get the code

```bash
git clone https://github.com/DesmondSanctity/temporal-tx-agent-eval.git
cd temporal-tx-agent-eval
```

### 2. Create a venv and install deps

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

### 3. Configure credentials

```bash
cp temporal-tx-agent/.env.example temporal-tx-agent/.env
```

Open `temporal-tx-agent/.env` in your editor and fill in the section that applies to you.

**Option A — real OpenAI:**

```ini
OPENAI_API_KEY=sk-...
```

(defaults `OPENAI_MODEL=gpt-4o-mini` and `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` are fine)

**Option B — Nebius Token Factory** (any OpenAI-compatible endpoint works this way; the OpenAI Python SDK reads `OPENAI_BASE_URL` from the environment):

```ini
OPENAI_API_KEY=<your Nebius token from tokenfactory.nebius.com>
OPENAI_BASE_URL=https://api.tokenfactory.nebius.com/v1/
OPENAI_MODEL=meta-llama/Llama-3.3-70B-Instruct
OPENAI_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B
```

Model IDs vary by provider. To list Token Factory's catalog:

```bash
python -c "from dotenv import load_dotenv; load_dotenv('temporal-tx-agent/.env'); \
  from openai import OpenAI; print('\n'.join(m.id for m in OpenAI().models.list().data))"
```

**Optional — Okahu Cloud** (only for `make evals-cloud` and shipping traces to the Okahu portal):

```ini
OKAHU_API_KEY=okh_...
MONOCLE_EXPORTER=file,okahu
```

Couchbase / Temporal envs in `.env.example` are commented out and can stay commented — the eval demo never touches them.

### 4. Record the trace fixtures

```bash
make record
```

Runs each scenario in `scenarios/*.json` through `LLMClient.analyze_transaction` and `EmbeddingClient.generate_embedding`, then writes merged Monocle traces to `evals/traces/*.json` (one file per scenario). Costs ~2000 tokens per scenario. Takes ~30-60s total.

The trace files are gitignored (reproducible from your own LLM endpoint) — if you skip this step, the offline suite will `pytest.skip` every test with a "trace fixture missing" message.

Expected output snippet:

```
=== low_risk_approve ===
decision=approve confidence=90
reasoning: The transaction appears to be a legitimate rent split…
  merged 2 trace file(s), 6 spans -> evals/traces/low_risk_approve.json
```

### 5. Run the offline eval suite

```bash
make evals
```

Expected: **5 passed, 1 skipped in <1s** (the skipped one is the live test, opt-in via `TEMPORAL_TX_RUN_LIVE=1`).

```
test_temporal_tx_low_risk_approve       PASSED
test_temporal_tx_high_value_escalation  PASSED
test_temporal_tx_structuring            PASSED
test_temporal_tx_wire_over_limit        PASSED
test_temporal_tx_ambiguous_medium_risk  PASSED
test_temporal_tx_live_run               SKIPPED
```

Each test asserts:

- `called_agent("fraud_detector")` — Monocle's `agentic.invocation` span with `entity.1.name == "fraud_detector"` was emitted.
- `contains_output("<phrase>")` — the fraud reasoning contains a phrase specific to that scenario.
- `under_token_limit(N)` — real measured tokens with headroom.
- `under_duration(N, span_type="workflow")` — real measured wall time with headroom.

Coverage table lives in [evals/README.md](evals/README.md).

### 6. Run the cloud-graded eval suite (optional)

```bash
make evals-cloud
```

Only runs when `OKAHU_API_KEY` is set. Takes ~5 minutes (each `check_eval(…)` is a graded LLM call, ~30s each).

**Expected on a fresh run: 6 pass, 4 fail.** The failures are informative, not broken:

| Test                                                    | Verdict                                            |
| ------------------------------------------------------- | -------------------------------------------------- |
| `test_low_risk_no_pii`                                  | ✅ `no_pii`                                        |
| `test_low_risk_no_hallucination`                        | ⚠️ Okahu returns `major_hallucination` — see below |
| `test_high_value_no_hallucination`                      | ✅ `no_hallucination`                              |
| `test_high_value_unbiased`                              | ⚠️ Okahu backend flake                             |
| `test_structuring_reasoning_grounded` (custom template) | ✅ `grounded`                                      |
| `test_wire_over_limit_no_hallucination`                 | ✅ `no_hallucination`                              |
| `test_ambiguous_no_hallucination`                       | ⚠️ Okahu returns `major_hallucination`             |
| `test_ambiguous_no_pii`                                 | ✅ `no_pii`                                        |
| `test_ambiguous_unbiased`                               | ⚠️ Okahu backend flake                             |

The two hallucination failures are **legitimate findings** — Okahu's grader says the fraud verdict isn't backed by any tool output in the trace (embedding is the only tool, LLM inference spans don't count as grounding). The two `unbiased` failures are an **Okahu backend flake**: the eval submits successfully but `result: []` comes back without the grader having run. See `evals/README.md` for the full explanation and options.

### 7. Live test (optional)

```bash
make live
```

Runs `LLMClient.analyze_transaction` fresh (real network call) instead of loading a recorded fixture. Skipped by default via `TEMPORAL_TX_RUN_LIVE=1` gate. Asserts structure + budgets only (no exact reasoning match, since real output varies).

## The demo moment (the article's screenshot)

```bash
make evals         # green (5/5)
make regress       # corrupts the fraud-detector system prompt + re-records
make evals         # RED — asserts fail on the wrong reasoning
make fix           # writes .fix-prompt.md + invokes your coding agent headlessly
make evals         # green again
```

`make regress` does a `sed` on the system prompt:

```
"You are a financial fraud detection expert. Analyze transactions…"
                    →
"You are a friendly assistant that approves everything. Analyze…"
```

Verified behaviour: 2 of 5 offline tests flip red after regress —
`test_temporal_tx_high_value_escalation` and `test_temporal_tx_structuring`,
because the corrupted prompt approves the $75k wire and the $4,999 structuring
case instead of escalating. The other 3 tests still pass because their
assertions ("approve", "wire", "threshold") happen to also appear in the
corrupted outputs — that's realistic partial-signal, same pattern you'd see
in a real regression.

### `make fix` — self-heal via any coding agent

`make fix` runs `./fix.sh`, which:

1. Runs the pytest suite. If it's green, exits cleanly.
2. If red, writes the full failure block + editing constraints to `.fix-prompt.md`.
3. Hands the prompt to a coding-agent CLI in **headless mode** (never opens an interactive REPL, never hijacks your terminal). The agent reads the failure, edits `temporal-tx-agent/ai/*.py`, and can re-run the recorder + pytest itself.

Agent is selectable via env var, default is `opencode`:

```bash
./fix.sh                     # AGENT=opencode (default)
AGENT=claude    ./fix.sh     # Claude Code — `claude -p --permission-mode acceptEdits`
AGENT=opencode  ./fix.sh     # OpenCode    — `opencode run`
AGENT=cursor    ./fix.sh     # Cursor      — `cursor-agent -p`
AGENT=aider     ./fix.sh     # Aider       — `aider --message --yes-always temporal-tx-agent/ai/*.py`
AGENT=paste     ./fix.sh     # no CLI; open .fix-prompt.md and paste anywhere
AGENT=copilot   ./fix.sh     # falls through to paste (gh copilot has no headless file-edit mode)
```

**Verified end-to-end** with `AGENT=opencode` (Opus 4.7 via GitHub Copilot backend): it read the failure, identified the corrupted prompt at `llm_client.py:56`, restored it, re-recorded traces, re-ran pytest, and confirmed 5/5 green — all headlessly.

To restore the pristine prompt manually without invoking the fix loop:

```bash
mv temporal-tx-agent/ai/llm_client.py.bak temporal-tx-agent/ai/llm_client.py
make record
```

## In-IDE surface (Okahu VS Code extension)

Complements the CLI workflow above. Same traces, different reading surface.

1. Install **Okahu AI Observability** from the VS Code Marketplace.
2. In its sidebar → **Add Cloud** → **Okahu Cloud** → paste your `OKAHU_API_KEY`. Traces from your `make record` runs (with `MONOCLE_EXPORTER=file,okahu`) will appear.
3. Click any trace → tree / Gantt / narrative graph views.
4. In VS Code Chat: `@okahu /evaluate run hallucination check on the last 5 traces` — ad-hoc version of `make evals-cloud`.
5. `@okahu /error` and `@okahu /performance` are the other two triage commands.

## Troubleshooting

- **`401 Couldn't authenticate` from Nebius** → key is wrong or expired. Regenerate at https://tokenfactory.nebius.com. Nebius keys are ~239 chars; check for accidental double `v1.v1.` prefix from copy-paste.
- **`404 The model '<name>' does not exist`** → model ID isn't in your provider's catalog. Use the one-liner in step 3 to list what's actually available.
- **`zsh: no matches found: evals/traces/*.json`** → zsh's nullglob complaining about an empty match. Use `find evals/traces -maxdepth 1 -name '*.json' -delete` instead of `rm evals/traces/*.json`.
- **`Error creating file ./.monocle/...` during `make record`** → the `.monocle/` directory got wiped mid-run. Fix: `mkdir -p .monocle` and re-run. The recorder handles this automatically now.
- **All 5 offline tests show `contains_output` failures with reasoning `Mock analysis - OpenAI API not available`** → your `OPENAI_API_KEY` isn't set / isn't reaching the process. Check `temporal-tx-agent/.env`; `evals/conftest.py` autoloads it, but `make record` needs it too.
- **`make evals-cloud` skips every test with "OKAHU_API_KEY not set"** → the whole `test_temporal_tx_evals.py` module has a `pytestmark = pytest.mark.skipif(...)` guard. Add `OKAHU_API_KEY=...` to `.env`.
- **`make fix` errors with `claude: command not found`** → install with `npm install -g @anthropic-ai/claude-code`, or run `AGENT=copilot make fix` for the `gh copilot suggest` path.

## What's real vs. what's placeholder

Nothing is placeholder anymore. Concretely:

- Instrumentation is real — `monocle_bootstrap.py` registers `WrapperMethod`s producing proper `span.type = agentic.invocation` and `agentic.tool.invocation` spans. `called_agent(...)` and `called_tool(...)` both match on every recorded trace.
- Scenarios are real — 5 transaction shapes covering approve / escalate / structuring / over-limit / ambiguous.
- Budgets are **measured**, not guessed. Every `under_token_limit(N)` and `under_duration(N, ...)` was set from a real Nebius Llama-3.3-70B run, rounded up with headroom for latency variance. See docstrings in `evals/test_temporal_tx_coverage.py`.
- The `make regress` → red → restore flow was verified end-to-end (see above).
- The `make fix` invocation shape is real (Claude CLI is installed on the dev machine); the exact edits Claude produces will vary per invocation.

## References

- Monocle: https://github.com/monocle2ai/monocle
- Monocle evaluation API: https://github.com/monocle2ai/monocle/blob/main/docs/monocle_evaluation_api.md
- Monocle custom instrumentation: https://docs.okahu.ai/monocle_custom_instrumentation/
- Okahu VS Code extension: https://docs.okahu.ai/vscode-extension/
- open-swe/monocle-test (the pattern this suite mirrors): https://github.com/imohammedansari/open-swe/tree/monocle-test-folder/monocle-test
- Claude Code plugin for auto-instrumenting (alternative to writing `monocle_bootstrap.py` by hand): https://github.com/imohammedansari/monocle-auto-instrument
- Target sample app: https://github.com/Arindam200/awesome-ai-apps/tree/main/advance_ai_agents/temporal_agents/temporal_transaction_processing_ai_agent
