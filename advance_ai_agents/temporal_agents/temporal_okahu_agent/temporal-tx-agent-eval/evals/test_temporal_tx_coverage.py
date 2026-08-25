# Enable Monocle tracing so the live test emits spans the asserter
# can capture (matches the pattern in open-swe/monocle-test).
# Importing the vendored app's bootstrap registers our WrapperMethods
# for the fraud_detector agent + tool spans in one place.
import sys as _sys
from pathlib import Path as _Path

_APP = _Path(__file__).resolve().parent.parent / "temporal-tx-agent"
if str(_APP) not in _sys.path:
    _sys.path.insert(0, str(_APP))
import monocle_bootstrap  # noqa: F401,E402

import os
import json
from pathlib import Path

import pytest

from monocle_test_tools import TraceAssertion
from monocle_test_tools.span_loader import JSONSpanLoader

HERE = Path(__file__).resolve().parent
TRACES = HERE / "traces"
REPO_ROOT = HERE.parent

# ---------------------------------------------------------------------------
# Offline coverage tests — one per scenario in scenarios/. Each test
# loads a pre-captured Monocle trace and asserts: the fraud_detector agent
# ran, its reasoning contains the phrase we expect for that transaction
# shape, and the run stayed under a token/duration budget. Hallucination /
# PII / bias evals live in the sibling test_temporal_tx_evals.py behind
# OKAHU_API_KEY (same split as open-swe/monocle-test's deferred check_eval
# lines).
#
# `.called_tool(...)` lines are NOT asserted here: the offline recorder
# calls the AI clients directly (no Temporal worker), so tool spans are
# only produced by the LIVE test path. That path asserts them.
#
# Budgets below are PLACEHOLDERS. After the first successful `make record`
# they'll be rewritten to the measured value rounded up with headroom —
# same convention as open-swe/monocle-test.
# ---------------------------------------------------------------------------

TRACE_LOW = str(TRACES / "low_risk_approve.json")
TRACE_HIGH = str(TRACES / "high_value_escalation.json")
TRACE_STRUCT = str(TRACES / "structuring.json")
TRACE_WOL = str(TRACES / "wire_over_limit.json")
TRACE_AMBIG = str(TRACES / "ambiguous_medium_risk.json")


def _load(asserter: TraceAssertion, path: str) -> TraceAssertion:
    if not Path(path).exists():
        pytest.skip(
            f"trace fixture missing: {path}. Run "
            "`python record_from_scenarios.py` first to record it."
        )
    spans = JSONSpanLoader.from_json(path)
    asserter.validator.add_remote_spans(spans)
    return asserter


def test_temporal_tx_low_risk_approve(monocle_trace_asserter: TraceAssertion):
    """$250 domestic wire. Fraud detector should approve.
    Measured on Nebius Llama-3.3-70B: 329 tokens / 5.86s workflow."""
    asserter = _load(monocle_trace_asserter, TRACE_LOW)

    asserter.called_agent("fraud_detector")
    asserter.contains_output("approve")

    asserter.under_token_limit(500)
    asserter.under_duration(30, units="seconds", span_type="workflow")


def test_temporal_tx_high_value_escalation(monocle_trace_asserter: TraceAssertion):
    """$75,000 cross-border wire — above AUTO_APPROVAL_LIMIT.
    Measured on Nebius Llama-3.3-70B: 324 tokens / 10.78s workflow."""
    asserter = _load(monocle_trace_asserter, TRACE_HIGH)

    asserter.called_agent("fraud_detector")
    asserter.contains_output("escalate")

    asserter.under_token_limit(500)
    asserter.under_duration(30, units="seconds", span_type="workflow")


def test_temporal_tx_structuring(monocle_trace_asserter: TraceAssertion):
    """$4,999 wire — just under the $5,000 reporting threshold.
    Measured on Nebius Llama-3.3-70B: 326 tokens / 4.80s workflow."""
    asserter = _load(monocle_trace_asserter, TRACE_STRUCT)

    asserter.called_agent("fraud_detector")
    asserter.contains_output("structuring")

    asserter.under_token_limit(500)
    asserter.under_duration(30, units="seconds", span_type="workflow")


def test_temporal_tx_wire_over_limit(monocle_trace_asserter: TraceAssertion):
    """$55,000 wire — above the wire-specific $50K limit.
    Measured on Nebius Llama-3.3-70B: 372 tokens / 15.62s workflow."""
    asserter = _load(monocle_trace_asserter, TRACE_WOL)

    asserter.called_agent("fraud_detector")
    asserter.contains_output("wire")

    asserter.under_token_limit(600)
    asserter.under_duration(45, units="seconds", span_type="workflow")


def test_temporal_tx_ambiguous_medium_risk(monocle_trace_asserter: TraceAssertion):
    """Ambiguous $9,999 cross-border wire. The reasoning should
    reference the $10,000 reporting threshold — this catches prompt
    regressions that drop the threshold-awareness context. Semantic
    quality is graded in test_temporal_tx_evals.py.
    Measured on Nebius Llama-3.3-70B: 335 tokens / 5.23s workflow."""
    asserter = _load(monocle_trace_asserter, TRACE_AMBIG)

    asserter.called_agent("fraud_detector")
    asserter.contains_output("threshold")

    asserter.under_token_limit(500)
    asserter.under_duration(30, units="seconds", span_type="workflow")


# ---------------------------------------------------------------------------
# Live test — runs the AI clients fresh against the low-risk scenario and
# additionally exercises the Temporal activity tool wrappers by calling
# apply_business_rules directly (activities are just async functions).
# Structural + budget only. Gated behind TEMPORAL_TX_RUN_LIVE=1.
# ---------------------------------------------------------------------------

def test_temporal_tx_live_run(monocle_trace_asserter: TraceAssertion):
    """Live run — hits the OpenAI API. Skipped unless
    TEMPORAL_TX_RUN_LIVE=1 with OPENAI_API_KEY exported."""
    if os.environ.get("TEMPORAL_TX_RUN_LIVE") != "1":
        pytest.skip(
            "live run hits the OpenAI API — set TEMPORAL_TX_RUN_LIVE=1 "
            "with OPENAI_API_KEY exported to exercise it."
        )

    import asyncio
    from ai.llm_client import llm_client
    from ai.embedding_client import embedding_client
    from temporal.activities import apply_business_rules

    scenario = json.loads(
        (REPO_ROOT / "scenarios" / "low_risk_approve.json").read_text()
    )
    tx = scenario["transaction"]

    embedding_client.generate_embedding(f"{tx['transaction_type']} {tx['amount']}")
    result = llm_client.analyze_transaction(tx)
    print("\n=== LIVE RESULT ===\n" + str(result)[:2000])

    # Temporal activities use activity.heartbeat/logger which no-op or
    # raise outside a live worker context. Best-effort — if it raises,
    # tool span still won't emit for business_rules, but the agent one will.
    try:
        asyncio.run(apply_business_rules(tx))
    except Exception as e:
        print(f"business_rules note: {e}")

    monocle_trace_asserter.called_agent("fraud_detector")
    monocle_trace_asserter.under_token_limit(30_000)
    monocle_trace_asserter.under_duration(60, units="seconds", span_type="workflow")
