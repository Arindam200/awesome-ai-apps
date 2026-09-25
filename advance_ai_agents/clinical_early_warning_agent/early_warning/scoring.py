"""NEWS2 and qSOFA, implemented exactly from the published charts.

NEWS2: Royal College of Physicians, National Early Warning Score 2 (2017).
qSOFA: Singer et al., Sepsis-3 (JAMA 2016).
Values are rounded the way they are charted (whole numbers; temperature to one decimal)
before scoring.
"""

from __future__ import annotations

import math

from .models import Reading


def _whole(v: float) -> int:
    return math.floor(v + 0.5)


def score_rr(rr: float) -> int:
    r = _whole(rr)
    if r <= 8:
        return 3
    if r <= 11:
        return 1
    if r <= 20:
        return 0
    if r <= 24:
        return 2
    return 3


def score_spo2(spo2: float, on_oxygen: bool, scale: int = 1) -> int:
    s = _whole(spo2)
    if scale == 2:  # prescribed 88-92% target (hypercapnic respiratory failure)
        if s <= 83:
            return 3
        if s <= 85:
            return 2
        if s <= 87:
            return 1
        if s <= 92 or not on_oxygen:
            return 0
        if s <= 94:
            return 1
        if s <= 96:
            return 2
        return 3
    if s <= 91:
        return 3
    if s <= 93:
        return 2
    if s <= 95:
        return 1
    return 0


def score_temp(temp: float) -> int:
    t = math.floor(temp * 10 + 0.5) / 10
    if t <= 35.0:
        return 3
    if t <= 36.0:
        return 1
    if t <= 38.0:
        return 0
    if t <= 39.0:
        return 1
    return 2


def score_sbp(sbp: float) -> int:
    s = _whole(sbp)
    if s <= 90:
        return 3
    if s <= 100:
        return 2
    if s <= 110:
        return 1
    if s <= 219:
        return 0
    return 3


def score_hr(hr: float) -> int:
    h = _whole(hr)
    if h <= 40:
        return 3
    if h <= 50:
        return 1
    if h <= 90:
        return 0
    if h <= 110:
        return 1
    if h <= 130:
        return 2
    return 3


RESPONSE = {
    "Low": "Routine monitoring (registered nurse to assess).",
    "Low-Medium": "Urgent ward-based review: a single parameter scores 3.",
    "Medium": "Urgent review by a clinician; at least hourly observations.",
    "High": "Emergency assessment by a critical-care team.",
}


def news2(reading: Reading, spo2_scale: int = 1) -> dict:
    parameters = {
        "rr": score_rr(reading.rr),
        "spo2": score_spo2(reading.spo2, reading.on_oxygen, spo2_scale),
        "air_or_oxygen": 2 if reading.on_oxygen else 0,
        "temp": score_temp(reading.temp),
        "sbp": score_sbp(reading.sbp),
        "hr": score_hr(reading.hr),
        "consciousness": 0 if reading.consciousness.upper() == "A" else 3,
    }
    total = sum(parameters.values())
    any_three = any(v == 3 for v in parameters.values())
    if total >= 7:
        band = "High"
    elif total >= 5:
        band = "Medium"
    elif any_three:
        band = "Low-Medium"
    else:
        band = "Low"
    return {"total": total, "band": band, "any_single_three": any_three, "parameters": parameters, "response": RESPONSE[band]}


def qsofa(reading: Reading) -> dict:
    criteria = {
        "rr_at_least_22": reading.rr >= 22,
        "sbp_at_most_100": reading.sbp <= 100,
        "altered_mentation": reading.consciousness.upper() != "A",
    }
    score = sum(criteria.values())
    return {"score": score, "criteria": criteria, "sepsis_flag": score >= 2}
