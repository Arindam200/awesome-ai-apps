"""Nine situations, one task. Every run asks for the same cost report; only the fault changes."""
from __future__ import annotations

import csv
import json

from contracts import REPORT_COLUMNS
from provider_api.server import CATALOG, FAULTS, RETIRED

TASK = "Build the LLM cost report for 2026-11."
REPORT = "reports/cost_report_2026-11.csv"

# expect: which tools must end up repaired. Everything else must be left untouched.
SCENARIOS = [
    {"id": "C0", "name": "Healthy run (control)", "broken": [], "faults": {},
     "expect": "report", "repairs": []},
    {"id": "S1", "name": "API renamed its pricing fields", "broken": ["fetch_pricing"], "faults": {},
     "expect": "report", "repairs": ["fetch_pricing"]},
    {"id": "S2", "name": "Messy log data (counts like \"1,240\")", "broken": ["summarize_usage"],
     "faults": {}, "expect": "report", "repairs": ["summarize_usage"]},
    {"id": "S3", "name": "Silent bad output (CSV drops cost_usd)", "broken": ["export_report"],
     "faults": {}, "expect": "report", "repairs": ["export_report"]},
    {"id": "S4", "name": "Pagination bug (only page 1 read)", "broken": ["fetch_usage"], "faults": {},
     "expect": "report", "repairs": ["fetch_usage"]},
    {"id": "S5", "name": "Rate limited (HTTP 429 twice)", "broken": [],
     "faults": {"rate_limit_pricing": 2}, "expect": "report", "repairs": []},
    {"id": "S6", "name": "Retired model id in the logs (HTTP 404)", "broken": [],
     "faults": {"retired_model_in_logs": True}, "expect": "report", "repairs": []},
    {"id": "S7", "name": "Expired API key (HTTP 401)", "broken": [], "faults": {"expired_key": True},
     "expect": "stop", "repairs": []},
    {"id": "S8", "name": "Two tools broken in one task", "broken": ["fetch_pricing", "export_report"],
     "faults": {}, "expect": "report", "repairs": ["fetch_pricing", "export_report"]},
]


def expected_costs() -> dict[str, float]:
    """Ground truth from the API's own data, computed without any tool."""
    out: dict[str, float] = {}
    for r in FAULTS.rows:
        model = RETIRED.get(r["model"], r["model"])
        inp, cached_p, out_p = CATALOG[model]
        p, c, o = (int(str(r[k]).replace(",", "")) for k in ("prompt_tokens", "cached_tokens", "completion_tokens"))
        out[r["model"]] = out.get(r["model"], 0.0) + ((p - c) * inp + c * cached_p + o * out_p) / 1e6
    return out


def check_report(root) -> tuple[bool, str]:
    path = root / REPORT
    if not path.exists():
        return False, "no report written"
    rows = list(csv.reader(path.open(encoding="utf-8", newline="")))
    if rows[0] != REPORT_COLUMNS:
        return False, f"wrong header {rows[0]}"
    return compare_costs({r[0]: float(r[5]) for r in rows[1:]})


def compare_costs(got: dict[str, float], tolerance: float = 1e-5) -> tuple[bool, str]:
    """Every model's cost must match the API data on its own, not just the total.

    A retired model may appear under its old id (as in the logs) or its new id (as billed),
    so both sides are compared under the id the model is billed as."""
    billed = lambda m: RETIRED.get(m, m)  # noqa: E731
    want: dict[str, float] = {}
    for m, cost in expected_costs().items():
        want[billed(m)] = want.get(billed(m), 0.0) + cost
    have: dict[str, float] = {}
    for m, cost in got.items():
        have[billed(m)] = have.get(billed(m), 0.0) + cost
    if set(have) != set(want):
        return False, f"models differ: got {sorted(have)} want {sorted(want)}"
    wrong = {m: (round(have[m], 6), round(want[m], 6)) for m in want if abs(have[m] - want[m]) >= tolerance}
    if wrong:
        return False, f"per-model costs differ (got, want): {json.dumps(wrong)}"
    return True, f"{len(want)} models, each cost matches the API data (total ${sum(have.values()):.6f})"
