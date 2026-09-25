"""Combine NEWS2, qSOFA, personal baseline and trend into one explainable risk level.

score = NEWS2 points + qSOFA + baseline deviations + trends (each group capped),
then raised to an escalation floor so the result is never less alarming than NEWS2.
Every point is a named factor, and the factors add up to the score.
"""

from __future__ import annotations

from .models import VITAL_INFO, VITALS, Patient, fmt
from .scoring import news2, qsofa
from .signals import deviation, trend

LEVELS = (("Stable", 0), ("Watch", 25), ("Warning", 50), ("Critical", 75))
URGENCY = {
    "Stable": "Routine",
    "Watch": "Routine, observe more often",
    "Warning": "Clinician review within 1 hour",
    "Critical": "Immediate",
}

NEWS2_POINTS, NEWS2_CAP, SINGLE_THREE_POINTS, QSOFA_POINTS = 4.0, 40.0, 6.0, 15.0
DEVIATION_WEIGHT = {"spo2": 16.0, "rr": 12.0, "hr": 12.0, "sbp": 12.0, "temp": 10.0}
TREND_WEIGHT = {"spo2": 14.0, "rr": 10.0, "hr": 10.0, "sbp": 10.0, "temp": 8.0}
DEVIATION_CAP, TREND_CAP = 35.0, 30.0


def level_for(score: float) -> str:
    return [name for name, minimum in LEVELS if score >= minimum][-1]


def _cap(factors: list[dict], cap: float) -> list[dict]:
    total = sum(f["points"] for f in factors)
    if total > cap:
        for f in factors:
            f["points"] *= cap / total
    return factors


def assess(patient: Patient) -> dict:
    r = patient.latest
    n2 = news2(r, patient.spo2_scale)
    q = qsofa(r)
    deviations = {v: deviation(patient.readings, v) for v in VITALS}
    trends = {v: trend(patient.readings, v) for v in VITALS}
    factors: list[dict] = []

    if n2["total"]:
        scored = ", ".join(f"{k} +{s}" for k, s in n2["parameters"].items() if s)
        factors.append({"factor": "news2", "points": min(n2["total"] * NEWS2_POINTS, NEWS2_CAP),
                        "detail": f"NEWS2 is {n2['total']} ({n2['band']}) from {scored}."})
    if n2["any_single_three"]:
        factors.append({"factor": "news2_single_three", "points": SINGLE_THREE_POINTS,
                        "detail": "A single NEWS2 parameter scores 3, which needs urgent ward review."})
    if q["sepsis_flag"]:
        factors.append({"factor": "qsofa", "points": QSOFA_POINTS, "detail": f"qSOFA is {q['score']}/3: screen for sepsis."})

    dev = []
    for v, d in deviations.items():
        if d["flagged"]:
            info = VITAL_INFO[v]
            side = "above" if d["z"] > 0 else "below"
            normal_note = " NEWS2 still scores it as normal." if n2["parameters"].get(v, 0) == 0 else ""
            dev.append({"factor": f"{v}_baseline", "points": DEVIATION_WEIGHT[v] * max(0.5, min(abs(d["z"]) / 5, 1)),
                        "detail": f"{info['label']} {fmt(v, d['value'])} is {side} this patient's own normal of "
                                  f"{fmt(v, d['baseline'])} (z {d['z']:+.1f}).{normal_note}"})
    factors += _cap(dev, DEVIATION_CAP)

    trd = []
    for v, t in trends.items():
        if t["flagged"]:
            info = VITAL_INFO[v]
            verb = "rising" if t["slope_per_hour"] > 0 else "falling"
            normal_note = " NEWS2 still scores it as normal." if n2["parameters"].get(v, 0) == 0 else ""
            strength = min(abs(t["slope_per_hour"]) / (2 * t["threshold_per_hour"]), 1)
            trd.append({"factor": f"{v}_trend", "points": TREND_WEIGHT[v] * strength,
                        "detail": f"{info['label']} has been {verb} {fmt(v, abs(t['slope_per_hour']), 1)}/hour over "
                                  f"the last {t['window_hours']:g} h.{normal_note}"})
    factors += _cap(trd, TREND_CAP)

    raw = min(sum(f["points"] for f in factors), 100.0)
    floors = []
    if n2["total"] >= 7:
        floors.append((75, "NEWS2 7 or more needs emergency assessment"))
    elif n2["total"] >= 5:
        floors.append((50, "NEWS2 5-6 needs urgent clinical review"))
    elif n2["any_single_three"]:
        floors.append((25, "a single NEWS2 parameter at 3 needs urgent ward review"))
    if q["sepsis_flag"]:
        floors.append((50, "qSOFA 2 or more needs a sepsis screen"))
    if floors:
        floor, reason = max(floors)
        if floor > raw:
            factors.append({"factor": "escalation_floor", "points": floor - raw,
                            "detail": f"Raised to at least {floor}: {reason}."})
            raw = float(floor)

    for f in factors:
        f["points"] = round(f["points"], 1)
    factors.sort(key=lambda f: -f["points"])
    score = round(raw)
    level = level_for(score)
    return {
        "patient_id": patient.id,
        "score": score,
        "level": level,
        "urgency": URGENCY[level],
        "factors": factors,
        "news2": n2,
        "qsofa": q,
        "flagged_baselines": [v for v, d in deviations.items() if d["flagged"]],
        "flagged_trends": [v for v, t in trends.items() if t["flagged"]],
        "as_of": patient.latest.ts.isoformat(),
    }
