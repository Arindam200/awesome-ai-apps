"""Plain-text rendering of an agent result for the terminal."""

from __future__ import annotations

import textwrap

from .agent import AgentResult


def wrap(text: str, indent: str = "  ") -> str:
    return textwrap.fill(text, width=92, initial_indent=indent, subsequent_indent=indent)


def _tool_label(call: dict) -> str:
    args = call["args"] if isinstance(call["args"], dict) else {}
    return f"{call['tool']}({args['vital']})" if args.get("vital") else call["tool"]


def render(result: AgentResult, patient_label: str) -> str:
    a, e = result.assessment, result.explanation
    n2, q = a["news2"], a["qsofa"]
    lines = [
        f"Clinical early-warning report — {patient_label}",
        "=" * 72,
        f"Level: {a['level']}   Score: {a['score']}/100   Suggested review: {a['urgency']}",
        f"NEWS2: {n2['total']} ({n2['band']})   qSOFA: {q['score']}/3{'  SEPSIS FLAG' if q['sepsis_flag'] else ''}",
        "",
        "Summary" + (f" (Gemini · {result.model})" if result.source == "gemini" else " (offline)"),
        wrap(e["clinician_summary"]),
    ]
    if e.get("key_findings"):
        lines += ["", "Key findings"] + [wrap(f"- {f}") for f in e["key_findings"]]
    lines += ["", "Contributing factors (points add up to the score)"]
    lines += [wrap(f"{f['points']:>5}  {f['detail']}") for f in a["factors"]] or ["  none — within this patient's normal range"]
    if e.get("patient_message"):
        lines += ["", "For the patient", wrap(e["patient_message"])]
    if result.trace:
        lines += ["", wrap("Tools called: " + ", ".join(_tool_label(t) for t in result.trace), indent="")]
    if result.note:
        lines += ["", f"Note: {result.note}"]
    lines += ["", result.disclaimer]
    return "\n".join(lines)
