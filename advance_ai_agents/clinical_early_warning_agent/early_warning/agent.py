"""The early-warning agent: an open model on Nebius Token Factory reasons and explains,
the tools supply every number.

The model calls the tools through Token Factory's OpenAI-compatible chat completions API
(standard function calling), then writes a short assessment. The risk level always comes
from `get_risk_assessment`: if the model's text claims a different level, the tool's level
wins and the report says so. Without an API key, or if the model fails, the same tools run
and a template explanation is used instead (`source = "offline"`).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .assess import assess
from .models import Patient
from .tools import ToolSession

DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507"
DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
MAX_TOOL_ROUNDS = 15  # model turns that may call tools before it must answer
DISCLAIMER = "Educational example on synthetic data. Decision support, not diagnosis; clinical judgment rests with a clinician."

SYSTEM_PROMPT = """You are a clinical early-warning assistant reviewing one patient's vital signs for a ward clinician.

How to work:
1. Call get_patient_overview, get_news2 and get_qsofa.
2. Call check_personal_baseline and check_trend for the vitals that look relevant (at least spo2, hr and rr).
3. Call get_risk_assessment. Its level is authoritative.

How to answer:
- Take every number from the tools. Never estimate or invent a value.
- Do not diagnose or name a disease as certain. Describe what the readings show and why it matters.
- Point out anything fixed-threshold NEWS2 misses (a drift inside its normal ranges, or a value far from this
  patient's own normal), and anything that reassures.
- Reply with JSON only:
  {"level": "<the level from get_risk_assessment>",
   "clinician_summary": "<2-3 short sentences for a clinician>",
   "key_findings": ["<short finding with its number>", "..."],
   "patient_message": "<one plain sentence for the patient>",
   "suggested_review": "<the urgency from get_risk_assessment, in your words>"}"""


@dataclass
class AgentResult:
    assessment: dict
    explanation: dict
    source: str  # "nebius" | "offline"
    model: str | None = None
    trace: list[dict] = field(default_factory=list)
    note: str | None = None
    disclaimer: str = DISCLAIMER


def offline_explanation(a: dict) -> dict:
    """A template explanation built from the assessment alone, used when no model answers."""
    causes = [f for f in a["factors"] if f["factor"] != "escalation_floor"] or a["factors"]
    if causes:
        summary = f"{a['level']} (score {a['score']}/100). " + " ".join(f["detail"] for f in causes[:2])
    else:
        summary = f"{a['level']} (score {a['score']}/100). All vital signs are within this patient's own normal range."
    patient = {
        "Stable": "Your readings are within your usual range.",
        "Watch": "Some readings are a little different from your usual, so your care team will check more often.",
        "Warning": "Your readings have changed and a doctor should see you within the hour.",
        "Critical": "Your readings need attention now; please tell a nurse how you feel.",
    }[a["level"]]
    return {
        "level": a["level"],
        "clinician_summary": summary,
        "key_findings": [f["detail"] for f in causes[:4]],
        "patient_message": patient,
        "suggested_review": a["urgency"],
    }


def parse_reply(text: str | None) -> dict | None:
    """The JSON answer from the model's reply, or None if it has none. Any <think> block is ignored."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or not isinstance(data.get("clinician_summary"), str) or not data["clinician_summary"].strip():
        return None
    findings = data.get("key_findings")
    return {
        "level": str(data.get("level", "")),
        "clinician_summary": data["clinician_summary"].strip(),
        "key_findings": [str(x) for x in findings] if isinstance(findings, list) else [],
        "patient_message": str(data.get("patient_message", "")).strip(),
        "suggested_review": str(data.get("suggested_review", "")).strip(),
    }


def _tool_loop(client, model: str, patient: Patient, session: ToolSession) -> str | None:
    """Let the model call tools until it answers in text. None if it is still calling tools after
    MAX_TOOL_ROUNDS turns."""
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"Assess patient {patient.id} and explain the result for the ward clinician."},
    ]
    tools = session.specs()
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.chat.completions.create(model=model, messages=messages, tools=tools, temperature=0.2)
        message = response.choices[0].message
        if not message.tool_calls:
            return message.content
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [{"id": c.id, "type": "function",
                            "function": {"name": c.function.name, "arguments": c.function.arguments}}
                           for c in message.tool_calls],
        })
        for c in message.tool_calls:
            result = session.call(c.function.name, c.function.arguments)
            messages.append({"role": "tool", "tool_call_id": c.id, "content": json.dumps(result, default=str)})
    return None


def run_agent(
    patient: Patient,
    api_key: str | None = None,
    model: str | None = None,
    offline: bool = False,
    client=None,
) -> AgentResult:
    """Assess a patient. Pass `client` to inject an OpenAI-compatible client (tests use a fake one)."""
    api_key = api_key if api_key is not None else os.getenv("NEBIUS_API_KEY", "")
    model = model or os.getenv("NEBIUS_MODEL", DEFAULT_MODEL)
    assessment = assess(patient)
    if offline or (not api_key and client is None):
        note = None if offline else "NEBIUS_API_KEY is not set, so the explanation below is the offline template."
        return AgentResult(assessment, offline_explanation(assessment), "offline", note=note)

    session = ToolSession(patient)
    try:
        if client is None:
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=os.getenv("NEBIUS_BASE_URL", DEFAULT_BASE_URL))
        text = _tool_loop(client, model, patient, session)
    except Exception as e:  # noqa: BLE001 — any API failure (network, quota, bad model) falls back offline
        return AgentResult(assessment, offline_explanation(assessment), "offline", trace=session.trace,
                           note=f"Nebius Token Factory was unavailable ({type(e).__name__}); "
                                "showing the offline explanation.")

    if text is None:
        return AgentResult(assessment, offline_explanation(assessment), "offline", model=model, trace=session.trace,
                           note=f"The model did not answer within {MAX_TOOL_ROUNDS} tool rounds; "
                                "showing the offline explanation.")
    explanation = parse_reply(text)
    if explanation is None:
        return AgentResult(assessment, offline_explanation(assessment), "offline", model=model, trace=session.trace,
                           note="The model's reply could not be parsed; showing the offline explanation.")
    note = None
    if explanation["level"] != assessment["level"]:
        note = f"The model said '{explanation['level'] or 'nothing'}'; the tool-computed level {assessment['level']} is used."
        explanation["level"] = assessment["level"]
    return AgentResult(assessment, explanation, "nebius", model=model, trace=session.trace, note=note)
