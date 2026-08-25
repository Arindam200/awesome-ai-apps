"""LLM-graded evals for the temporal-tx traces.

Same scenarios as test_temporal_tx_coverage.py, but with `check_eval(...)`
lines enabled. These call the Okahu evaluator API and require OKAHU_API_KEY
in the environment (loaded from temporal-tx-agent/.env by conftest.py).

The whole module is skipped when OKAHU_API_KEY is unset, so `pytest evals/`
still runs cleanly with just the offline coverage suite.
"""

import os
from pathlib import Path

import pytest

from monocle_apptrace import setup_monocle_telemetry  # noqa: F401 — side-effect init
setup_monocle_telemetry(workflow_name="temporal-tx")

from monocle_test_tools import TraceAssertion
from monocle_test_tools.span_loader import JSONSpanLoader

pytestmark = pytest.mark.skipif(
    not os.environ.get("OKAHU_API_KEY"),
    reason="OKAHU_API_KEY not set — Okahu evaluator is required for this module.",
)

HERE = Path(__file__).resolve().parent
TRACES = HERE / "traces"
TEMPLATES = HERE / "templates"

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


def test_low_risk_no_hallucination(monocle_trace_asserter: TraceAssertion):
    asserter = _load(monocle_trace_asserter, TRACE_LOW)
    asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


def test_low_risk_no_pii(monocle_trace_asserter: TraceAssertion):
    asserter = _load(monocle_trace_asserter, TRACE_LOW)
    asserter.with_evaluation("okahu").check_eval("pii_leakage", "no_pii")


def test_high_value_no_hallucination(monocle_trace_asserter: TraceAssertion):
    asserter = _load(monocle_trace_asserter, TRACE_HIGH)
    asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


def test_high_value_unbiased(monocle_trace_asserter: TraceAssertion):
    asserter = _load(monocle_trace_asserter, TRACE_HIGH)
    asserter.with_evaluation("okahu").check_eval("bias", "unbiased")


def test_structuring_reasoning_grounded(monocle_trace_asserter: TraceAssertion):
    """Custom template — asserts the fraud-detector reasoning is grounded
    in the transaction facts (no invented history / no fabricated
    counterparties). Template lives at evals/templates/fraud_reasoning.json."""
    asserter = _load(monocle_trace_asserter, TRACE_STRUCT)
    asserter.with_evaluation("okahu")\
        .check_eval(
            template_path=str(TEMPLATES / "fraud_reasoning.json"),
            expected="grounded",
        )


def test_wire_over_limit_no_hallucination(monocle_trace_asserter: TraceAssertion):
    asserter = _load(monocle_trace_asserter, TRACE_WOL)
    asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


def test_ambiguous_no_hallucination(monocle_trace_asserter: TraceAssertion):
    """The 'ambiguous' scenario is where AI regressions bite hardest — this
    is the primary red-light test to inject a prompt regression against."""
    asserter = _load(monocle_trace_asserter, TRACE_AMBIG)
    asserter.with_evaluation("okahu").check_eval("hallucination", "no_hallucination")


def test_ambiguous_no_pii(monocle_trace_asserter: TraceAssertion):
    asserter = _load(monocle_trace_asserter, TRACE_AMBIG)
    asserter.with_evaluation("okahu").check_eval("pii_leakage", "no_pii")


def test_ambiguous_unbiased(monocle_trace_asserter: TraceAssertion):
    asserter = _load(monocle_trace_asserter, TRACE_AMBIG)
    asserter.with_evaluation("okahu").check_eval("bias", "unbiased")
