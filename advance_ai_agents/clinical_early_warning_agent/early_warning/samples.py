"""Synthetic sample patients: 7 days of 5-minute vital signs, generated deterministically.

Each vital is the patient's own normal, plus a day/night rhythm, a slow physiological
wander and small reading-to-reading jitter. A scenario then shifts some vitals steadily
over the final hours. No real patient data is used anywhere.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone

from .models import Patient, Reading

STEP = timedelta(minutes=5)
END = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)
CIRCADIAN = {"hr": (4.0, 15), "sbp": (5.0, 14), "temp": (0.25, 18), "rr": (0.5, 15)}
ROUND = {"hr": 0, "spo2": 0, "sbp": 0, "rr": 0, "temp": 1}
DEFAULT_NORMALS = {"hr": (74, 4), "spo2": (97, 0.8), "sbp": (122, 6), "rr": (16, 1.0), "temp": (36.8, 0.2)}

SAMPLES = {
    "stable": {
        "label": "Stable adult, routine post-op day 3",
        "conditions": ["Post-operative"],
        "normals": {},
        "drift": {},
    },
    "slow_hypoxia": {
        "label": "Asthma: SpO2 sliding inside the 'normal' range",
        "conditions": ["Asthma"],
        "normals": {"hr": (80, 4)},
        "drift": {"spo2": -1.0, "rr": 1.2, "hr": 3.5},
        "hours": 4.0,
    },
    "early_sepsis": {
        "label": "Post-appendectomy: early sepsis picture",
        "conditions": ["Post-op day 2 (appendectomy)"],
        "normals": {"hr": (76, 4), "temp": (37.0, 0.2)},
        "drift": {"hr": 7.0, "temp": 0.4, "rr": 1.5, "sbp": -5.0},
    },
    "runner": {
        "label": "Competitive runner, resting HR 52: a rise NEWS2 calls normal",
        "conditions": ["Dengue (recovering)"],
        "normals": {"hr": (52, 3), "rr": (13, 1.0), "sbp": (114, 5)},
        "drift": {"hr": 9.0, "rr": 1.5},
        "hours": 3.5,
    },
    "copd": {
        "label": "COPD on a prescribed 88-92% SpO2 target, stable",
        "conditions": ["COPD"],
        "normals": {"spo2": (90, 1.0), "rr": (19, 1.2), "hr": (86, 4)},
        "drift": {},
        "spo2_scale": 2,
    },
}


def _circadian(vital: str, ts: datetime) -> float:
    if vital not in CIRCADIAN:
        return 0.0
    amp, peak = CIRCADIAN[vital]
    hour = ts.hour + ts.minute / 60
    return amp * math.cos(2 * math.pi * (hour - peak) / 24)


def generate(name: str, days: int = 7, drift_hours: float | None = None, seed: int = 7) -> Patient:
    """A sample patient whose scenario drift (if any) runs over the last `drift_hours` (default: the sample's own)."""
    spec = SAMPLES[name]
    drift_hours = spec.get("hours", 3.0) if drift_hours is None else drift_hours
    normals = {**DEFAULT_NORMALS, **spec["normals"]}
    rng = random.Random(f"{seed}-{name}")
    slow = {v: 0.0 for v in normals}
    n = days * 288
    readings = []
    for i in range(n):
        ts = END - (n - 1 - i) * STEP
        hours_into_drift = max(0.0, drift_hours - (n - 1 - i) * STEP.total_seconds() / 3600)
        values = {}
        for v, (mean, std) in normals.items():
            slow[v] = 0.97 * slow[v] + rng.gauss(0, 0.35 * std * math.sqrt(1 - 0.97**2))
            jitter = max(-2.5, min(2.5, rng.gauss(0, 1))) * std * 0.94
            value = mean + _circadian(v, ts) + slow[v] + jitter + spec["drift"].get(v, 0.0) * hours_into_drift
            values[v] = round(min(value, 100.0) if v == "spo2" else value, ROUND[v])
        readings.append(Reading(ts=ts, **values))
    return Patient(id=name, label=spec["label"], readings=readings, conditions=spec["conditions"],
                   spo2_scale=spec.get("spo2_scale", 1))
