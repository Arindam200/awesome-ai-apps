"""The early-warning agent: Gemini reasons and explains, the tools supply every number.

The model calls the tools (automatic function calling in the google-genai SDK), then
writes a short assessment. The risk level always comes from `get_risk_assessment`: if
the model's text claims a different level, the tool's level wins and the report says so.
Without an API key, or if Gemini fails, the same tools run and a template explanation
is used instead (`source = "offline"`).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field

from .assess import assess
from .models import Patient
from .tools import ToolSession

DEFAULT_MODEL = "gemini-2.5-flash"
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
    source: str  # "gemini" | "offline"
    model: str | None = None
    trace: list[dict] = field(default_factory=list)
    note: str | None = None
    disclaimer: str = DISCLAIMER


def offline_explanation(a: dict) -> dict:
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


def parse_reply(text: str) -> dict | None:
    text = (text or "").strip()
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


def run_agent(
    patient: Patient,
    api_key: str | None = None,
    model: str | None = None,
    offline: bool = False,
    client=None,
) -> AgentResult:
    """Assess a patient. Pass `client` to inject a google-genai client (tests use a fake one)."""
    api_key = api_key if api_key is not None else os.getenv("GEMINI_API_KEY", "")
    model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    assessment = assess(patient)
    if offline or (not api_key and client is None):
        note = None if offline else "GEMINI_API_KEY is not set, so the explanation below is the offline template."
        return AgentResult(assessment, offline_explanation(assessment), "offline", note=note)

    session = ToolSession(patient)
    try:
        from google import genai
        from google.genai import types

        client = client or genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=f"Assess patient {patient.id} and explain the result for the ward clinician.",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=session.tools(),
                temperature=0.2,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=15),
            ),
        )
        explanation = parse_reply(response.text)
    except Exception as e:  # noqa: BLE001 — any Gemini failure (network, quota, bad model) falls back offline
        return AgentResult(assessment, offline_explanation(assessment), "offline", trace=session.trace,
                           note=f"Gemini was unavailable ({type(e).__name__}); showing the offline explanation.")

    if explanation is None:
        return AgentResult(assessment, offline_explanation(assessment), "offline", model=model, trace=session.trace,
                           note="Gemini's reply could not be parsed; showing the offline explanation.")
    note = None
    if explanation["level"] != assessment["level"]:
        note = f"The model said '{explanation['level'] or 'nothing'}'; the tool-computed level {assessment['level']} is used."
        explanation["level"] = assessment["level"]
    return AgentResult(assessment, explanation, "gemini", model=model, trace=session.trace, note=note)
