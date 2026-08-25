"""Offline trace recorder.

Runs each scenario in `scenarios/*.json` directly against the AI
clients (no Temporal, no Couchbase, no FastAPI) so we can produce Monocle
trace fixtures for the pytest eval suite without needing the full stack.

For each scenario we snapshot the `.monocle/` folder before the call,
run the scenario, wait for the batch exporter to flush, and merge every
new trace file's spans into a single fixture at
`evals/traces/<scenario_id>.json`. Merging keeps one file per scenario
even though each `analyze_transaction` and `generate_embedding` call
produces its own trace.

Without OPENAI_API_KEY, `LLMClient` and `EmbeddingClient` fall back to
their built-in mock outputs — traces still get emitted and instrumented,
they just don't reflect real reasoning. Set OPENAI_API_KEY in
`temporal-tx-agent/.env` for real reasoning traces.

Usage (from repo root):
    python record_from_scenarios.py
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "temporal-tx-agent"
sys.path.insert(0, str(APP))

# Triggers setup_monocle_telemetry(workflow_name="temporal-tx") + our WrapperMethods.
import monocle_bootstrap  # noqa: F401,E402

from ai.embedding_client import embedding_client  # noqa: E402
from ai.llm_client import llm_client  # noqa: E402
from opentelemetry import trace as _otel_trace  # noqa: E402

SCENARIOS_DIR = ROOT / "scenarios"
TRACES_OUT = ROOT / "evals" / "traces"

# The Monocle file exporter writes .monocle/ relative to the current
# working directory of the process, not relative to any package. Force a
# stable location so we know where to look.
MONOCLE_DIR = ROOT / ".monocle"


def _txt(tx: dict) -> str:
    sender = tx.get("sender", {})
    recipient = tx.get("recipient", {})
    return (
        f"{tx.get('transaction_type', '')} "
        f"{tx.get('amount', 0)} {tx.get('currency', 'USD')} "
        f"{sender.get('name', '')} -> {recipient.get('name', '')} "
        f"({sender.get('country', '')} -> {recipient.get('country', '')})"
    )


def _snapshot() -> set:
    if not MONOCLE_DIR.exists():
        return set()
    return {p.name for p in MONOCLE_DIR.glob("monocle_trace_temporal-tx_*.json")}


def _run_one(scenario_path: Path) -> None:
    scenario = json.loads(scenario_path.read_text())
    tx = scenario["transaction"]
    print(f"\n=== {scenario['id']} ===")
    print(scenario["description"])

    before = _snapshot()

    embedding = embedding_client.generate_embedding(_txt(tx))
    result = llm_client.analyze_transaction(
        tx,
        context={
            "similar_transactions": [],
            "risk_score": 0,
            "embedding_dims": len(embedding) if embedding else 0,
        },
    )
    print(f"decision={result['decision']} confidence={result['confidence']}")
    print(f"reasoning: {result['reasoning'][:200]}")

    # Force the BatchSpanProcessor to flush this scenario's spans to disk
    # so the snapshot diff below picks them up deterministically.
    _otel_trace.get_tracer_provider().force_flush()
    time.sleep(0.2)

    after = _snapshot()
    new_files = sorted(after - before)
    if not new_files:
        print(f"  WARNING: no new trace files produced for {scenario['id']}")
        return

    merged: list = []
    for name in new_files:
        merged.extend(json.loads((MONOCLE_DIR / name).read_text()))

    TRACES_OUT.mkdir(parents=True, exist_ok=True)
    dst = TRACES_OUT / f"{scenario['id']}.json"
    dst.write_text(json.dumps(merged, indent=2))
    print(f"  merged {len(new_files)} trace file(s), {len(merged)} spans -> evals/traces/{dst.name}")


def main() -> int:
    scenarios = sorted(SCENARIOS_DIR.glob("*.json"))
    if not scenarios:
        print(f"No scenarios found under {SCENARIOS_DIR}")
        return 1
    # Fresh start so _snapshot() diff logic is clean. Delete only the old
    # trace files, not the directory itself — the file exporter doesn't
    # recreate the dir on write, so removing it would break subsequent runs.
    MONOCLE_DIR.mkdir(exist_ok=True)
    for old in MONOCLE_DIR.glob("monocle_trace_temporal-tx_*.json"):
        old.unlink()
    for s in scenarios:
        _run_one(s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
