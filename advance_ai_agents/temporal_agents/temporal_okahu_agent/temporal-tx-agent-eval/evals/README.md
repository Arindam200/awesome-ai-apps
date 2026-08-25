# Monocle test tools — trace-based tests for temporal-tx

Automated tests that check the vendored temporal transaction-processing
agent's behaviour by inspecting the telemetry it emits, using
[Monocle](https://github.com/monocle2ai/monocle) and its test tools.

## What's here

- `test_temporal_tx_coverage.py` — the fluent test suite (5 offline + 1 live), no OKAHU_API_KEY required
- `test_temporal_tx_evals.py` — same 5 scenarios with LLM-graded `check_eval(...)` enabled (needs OKAHU_API_KEY)
- `templates/fraud_reasoning.json` — custom eval template asserting the fraud reasoning is grounded in the transaction facts
- `traces/` — recorded trace fixtures the offline tests run against (populated by `record_from_scenarios.py`)
- `requirements.txt` — `monocle_test_tools`

## How it works

Monocle records each run as a structured trace (every OpenAI call, tool
call, token count, timing). A **fluent test** chains assertions over a
trace, reading like a sentence:

```python
asserter.contains_output("escalate")
asserter.under_token_limit(30_000)
asserter.under_duration(45, units="seconds", span_type="workflow")
asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")
```

Each offline test loads a recorded trace and asserts: the reasoning
contains the phrase we expect for that transaction shape, and the run
stayed under a token/duration budget measured from that trace (budgets
placeholder until first recording — see below). The live test runs the
AI client fresh and asserts structure + budget only.

## Coverage

Budgets below are the measured value on Nebius Llama-3.3-70B rounded up
with generous headroom to survive latency variance. Same convention as
`open-swe/monocle-test` — a regression that drops a phrase or blows the
budget fails the test.

| Test                                     | Scenario                                 | Reasoning must contain  | Budget          |
| ---------------------------------------- | ---------------------------------------- | ----------------------- | --------------- |
| `test_temporal_tx_low_risk_approve`      | `$250` domestic wire, individuals        | `approve`               | <500 tok / <30s |
| `test_temporal_tx_high_value_escalation` | `$75,000` cross-border wire              | `escalate`              | <500 tok / <30s |
| `test_temporal_tx_structuring`           | `$4,999` — just under $5K threshold      | `structuring`           | <500 tok / <30s |
| `test_temporal_tx_wire_over_limit`       | `$55,000` wire, over $50K limit          | `wire`                  | <600 tok / <45s |
| `test_temporal_tx_ambiguous_medium_risk` | `$9,999` cross-border, vague description | `threshold`             | <500 tok / <30s |
| `test_temporal_tx_live_run`              | (live) low-risk approve, fresh           | structure + budget only | opt-in          |

## Run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r evals/requirements.txt
pip install -r temporal-tx-agent/requirements.txt

# 1) Record trace fixtures once (needs OPENAI_API_KEY):
python record_from_scenarios.py

# 2) Run the offline suite — fast, no network, no keys:
pytest evals/test_temporal_tx_coverage.py -v

# 3) Run the LLM-graded eval suite (needs OKAHU_API_KEY):
pytest evals/test_temporal_tx_evals.py -v

# 4) Live run:
TEMPORAL_TX_RUN_LIVE=1 pytest evals/test_temporal_tx_coverage.py::test_temporal_tx_live_run -v
```

### Cloud-graded suite results

`test_temporal_tx_evals.py` splits each eval into its own test (10 total)
so you can see exactly which one flakes. Expect roughly 6 of 10 to pass
on a fresh run:

- ✅ `pii_leakage` — reliably grades both scenarios as `no_pii`.
- ✅ `hallucination` on `structuring` and `wire_over_limit` — passes.
- ✅ Custom template `fraud_reasoning_grounded` — passes.
- ⚠️ `hallucination` on `low_risk_approve` and `ambiguous_medium_risk` —
  Okahu grades these as `major_hallucination` with explanation
  "_claims not supported by any tool output_". This is a legitimate
  observability finding: the fraud verdict lives inside the agent
  invocation's LLM inference span, but Okahu doesn't count LLM inference
  as grounding evidence — only tool outputs. Two ways to satisfy the
  grader: (a) restructure the agent to call a `decide` tool, or
  (b) accept the finding as-is and use it in the article to explain what
  Okahu's hallucination eval actually checks.
- ⚠️ `bias` on both scenarios — Okahu returns
  `{'message': 'Job submitted', 'result': []}` — the eval job never
  resolves back to the sync client. Backend flake, not our bug. Report
  to Mohammed's team.

### After the first recording

Replace the placeholder budgets in `test_temporal_tx_coverage.py` with
the real numbers measured from that trace, rounded up with headroom.
Same convention as `open-swe/monocle-test` — a regression that blows
the budget then fails the test.

### Instrumentation

All Monocle wiring lives in `temporal-tx-agent/monocle_bootstrap.py`.
The vendored sample is otherwise untouched — only two single-line
`import monocle_bootstrap` additions at the top of `api/main.py` and
`temporal/run_worker.py` (unavoidable, telemetry has to init inside
each process).

The bootstrap registers `WrapperMethod`s that produce proper
`agentic.invocation` and `agentic.tool.invocation` spans:

- `LLMClient.analyze_transaction` → agent `"fraud_detector"`
- `EmbeddingClient.generate_embedding` → tool `"embed_transaction"`
- each Temporal activity (`apply_business_rules`, `search_similar_transactions`,
  `save_decision`, `update_transaction_status`, `create_human_review`) → tool

The tool spans point back to `fraud_detector` via `entity.2.name`, so
`called_tool("business_rules", agent_name="fraud_detector")` matches.

The offline recorder only exercises the agent + embed_transaction path
(it calls the AI clients directly, no Temporal worker). Full tool
coverage lives in the live test.
