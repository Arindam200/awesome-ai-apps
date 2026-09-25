"""The tools the agent can call. Each returns plain JSON-able data computed by the
deterministic code in this package, so every number the agent reports can be traced.

The patient's readings (a week at 5-minute intervals) are far too long to pass as tool
arguments, so the tools work on the patient loaded into a `ToolSession`.
"""

from __future__ import annotations

import functools
from collections.abc import Callable

from .assess import assess
from .models import VITAL_INFO, VITALS, Patient
from .scoring import news2, qsofa
from .signals import deviation, trend


class ToolSession:
    def __init__(self, patient: Patient) -> None:
        self.patient = patient
        self.trace: list[dict] = []

    def _record(self, fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            result = fn(*args, **kwargs)
            self.trace.append({"tool": fn.__name__, "args": kwargs or list(args), "result": result})
            return result

        return wrapper

    def tools(self) -> list[Callable]:
        p = self.patient

        def get_patient_overview() -> dict:
            """Who the patient is (synthetic), their conditions, the NEWS2 SpO2 scale in use, how much history
            is available, and the latest set of vital signs."""
            r = p.latest
            return {
                "patient_id": p.id,
                "description": p.label,
                "conditions": p.conditions,
                "spo2_scale": p.spo2_scale,
                "readings": len(p.readings),
                "history_hours": round((p.latest.ts - p.readings[0].ts).total_seconds() / 3600, 1),
                "latest": {"time": r.ts.isoformat(), "hr": r.hr, "spo2": r.spo2, "sbp": r.sbp, "rr": r.rr,
                           "temp": r.temp, "on_oxygen": r.on_oxygen, "consciousness": r.consciousness},
            }

        def get_news2() -> dict:
            """The NEWS2 early warning score for the latest reading, with the points for each parameter and the
            recommended clinical response."""
            return news2(p.latest, p.spo2_scale)

        def get_qsofa() -> dict:
            """The qSOFA sepsis screen for the latest reading (respiratory rate >= 22, systolic BP <= 100,
            altered mentation). Two or more criteria flag sepsis risk."""
            return qsofa(p.latest)

        def check_personal_baseline(vital: str) -> dict:
            """Compare one vital sign with this patient's own normal (median of the last 7 days, excluding the
            most recent 6 hours). vital must be one of: hr, spo2, sbp, rr, temp. Returns the current value,
            the personal baseline, a z-score, and whether it is flagged (|z| >= 2.5 in the concerning direction)."""
            if vital not in VITALS:
                return {"error": f"Unknown vital '{vital}'. Use one of {list(VITALS)}."}
            return {**deviation(p.readings, vital), "unit": VITAL_INFO[vital]["unit"]}

        def check_trend(vital: str, hours: float = 3.0) -> dict:
            """Fit a slope to one vital sign over the last `hours` (default 3, between 1 and 12). vital must be one
            of: hr, spo2, sbp, rr, temp. Returns the change per hour and whether it is a sustained drift in the
            concerning direction (steep enough and statistically significant)."""
            if vital not in VITALS:
                return {"error": f"Unknown vital '{vital}'. Use one of {list(VITALS)}."}
            return {**trend(p.readings, vital, max(1.0, min(float(hours), 12.0))), "unit": VITAL_INFO[vital]["unit"]}

        def get_risk_assessment() -> dict:
            """The combined, explainable risk assessment: a 0-100 score, the level (Stable, Watch, Warning,
            Critical), the suggested urgency, and every contributing factor with its points. This is the
            authoritative level; the explanation must agree with it."""
            return assess(p)

        return [self._record(f) for f in (get_patient_overview, get_news2, get_qsofa, check_personal_baseline,
                                           check_trend, get_risk_assessment)]
