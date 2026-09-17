"""Console rendering and JSON report serialization."""

from __future__ import annotations

import os
from pathlib import Path

from guardrail_eval_harness.schemas import (
    CaseResult,
    MetricOutcome,
    Report,
    ReportTotals,
)

GLYPHS = {
    MetricOutcome.PASS: "PASS",
    MetricOutcome.FAIL: "FAIL",
    MetricOutcome.NOT_APPLICABLE: "N/A",
    MetricOutcome.ERROR: "ERROR",
}


def render_console(
    cases: list[CaseResult], totals: ReportTotals, aggregate: str, mode: str
) -> str:
    lines: list[str] = []
    for case in cases:
        marker = {"pass": "✓", "fail": "✗", "error": "!"}[case.status]
        lines.append(
            f"{marker} {case.scenario_id} [{case.suite}/{case.category}] -> {case.status}"
        )
        for outcome in case.outcomes:
            glyph = GLYPHS[outcome.outcome]
            line = f"  {glyph:<4} {outcome.metric}: {outcome.reason}"
            lines.append(line)
            for evidence in outcome.evidence:
                lines.append(f"       evidence: {evidence}")
    rate = f"{totals.passed}/{totals.applicable}" if totals.applicable else "0/0"
    lines.append(
        f"mode={mode} checks={rate} pass failed={totals.failed} errors={totals.errored} "
        f"n/a={totals.not_applicable} aggregate={aggregate}"
    )
    return "\n".join(lines)


def build_report(
    cases: list[CaseResult],
    totals: ReportTotals,
    aggregate: str,
    mode: str,
    suite: str,
    provider: str | None = None,
    model: str | None = None,
) -> Report:
    return Report(
        mode=mode,  # type: ignore[arg-type]
        suite=suite,
        provider=provider,
        model=model,
        case_results=cases,
        totals=totals,
        aggregate_status=aggregate,  # type: ignore[arg-type]
    )


def write_report(report: Report, path: Path, overwrite: bool) -> None:
    resolved = path.resolve()
    if resolved.exists() and not overwrite:
        raise FileExistsError(
            f"report path exists; pass --overwrite to replace: {resolved}"
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    payload = report.model_dump_json(indent=2)
    tmp = resolved.with_suffix(resolved.suffix + ".tmp")
    tmp.write_text(payload + "\n", encoding="utf-8")
    os.replace(tmp, resolved)
