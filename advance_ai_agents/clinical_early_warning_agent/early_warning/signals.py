"""Personal baseline and trend: the two signals fixed-threshold scores miss.

Baseline: median and MAD (scaled to a standard deviation) of the patient's own readings
over the last 7 days, leaving out the most recent hours so a slow decline can't teach
itself to look normal. Robust statistics ignore the odd artefact without extra rules.

Trend: a least-squares slope over the last 3 hours. Readings minutes apart are
autocorrelated, which makes the ordinary standard error far too small; it is widened by
the lag-1 autocorrelation of the residuals before testing whether the slope is real.
"""

from __future__ import annotations

import math
import statistics
from datetime import timedelta
from itertools import pairwise

from .models import Reading

BASELINE_DAYS = 7
BASELINE_LAG_HOURS = 6
MIN_BASELINE_READINGS = 24
SMOOTH_READINGS = 3  # "current" = mean of the last 3 readings, to damp single-reading noise
Z_THRESHOLD = 2.5

# Floors on the spread so a very steady patient can't turn noise into a huge z-score.
MIN_STD = {"hr": 3.0, "spo2": 1.0, "sbp": 5.0, "rr": 1.5, "temp": 0.25}
# Which direction away from normal is concerning.
BAD_DIRECTION = {"hr": "both", "spo2": "down", "sbp": "both", "rr": "both", "temp": "both"}

TREND_HOURS = 3.0
TREND_MIN_POINTS = 8
TREND_MIN_T = 3.0
# (concerning direction, slope per hour that counts as a drift)
TREND_THRESHOLD = {"spo2": ("down", 0.5), "hr": ("both", 4.0), "rr": ("up", 1.5), "sbp": ("both", 6.0), "temp": ("up", 0.3)}


def baseline(readings: list[Reading], vital: str) -> dict | None:
    now = readings[-1].ts
    start, end = now - timedelta(days=BASELINE_DAYS), now - timedelta(hours=BASELINE_LAG_HOURS)
    values = [r.get(vital) for r in readings if start <= r.ts <= end]
    if len(values) < MIN_BASELINE_READINGS:
        return None
    med = statistics.median(values)
    mad = statistics.median(abs(v - med) for v in values)
    return {"mean": med, "std": max(mad * 1.4826, MIN_STD[vital]), "n": len(values)}


def current(readings: list[Reading], vital: str) -> float:
    last = readings[-SMOOTH_READINGS:]
    return sum(r.get(vital) for r in last) / len(last)


def deviation(readings: list[Reading], vital: str) -> dict:
    b = baseline(readings, vital)
    value = current(readings, vital)
    if b is None:
        return {"vital": vital, "value": round(value, 2), "baseline": None, "z": None, "flagged": False,
                "note": "Not enough history for a personal baseline (needs 2+ hours older than 6 h)."}
    z = (value - b["mean"]) / b["std"]
    direction = BAD_DIRECTION[vital]
    concerning = direction == "both" or (direction == "down" and z < 0) or (direction == "up" and z > 0)
    return {
        "vital": vital,
        "value": round(value, 2),
        "baseline": round(b["mean"], 2),
        "baseline_std": round(b["std"], 2),
        "z": round(z, 2),
        "flagged": bool(concerning and abs(z) >= Z_THRESHOLD),
    }


def _fit(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Slope and its autocorrelation-corrected standard error."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0 or n <= 2:
        return 0.0, math.inf
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    intercept = my - slope * mx
    res = [y - (intercept + slope * x) for x, y in zip(xs, ys, strict=True)]
    ss = sum(e * e for e in res)
    se = math.sqrt(ss / (n - 2) / sxx)
    if ss > 0:
        r = min(max(sum(a * b for a, b in pairwise(res)) / ss, 0.0), 0.9)
        se *= math.sqrt((1 + r) / (1 - r))
    return slope, se


def trend(readings: list[Reading], vital: str, hours: float = TREND_HOURS) -> dict:
    now = readings[-1].ts
    window = [r for r in readings if r.ts >= now - timedelta(hours=hours)]
    xs = [(r.ts - now).total_seconds() / 3600 for r in window]
    ys = [r.get(vital) for r in window]
    slope, se = _fit(xs, ys) if len(window) >= 3 else (0.0, math.inf)
    t = 0.0 if se in (0, math.inf) else slope / se
    direction, threshold = TREND_THRESHOLD[vital]
    steep = (direction == "up" and slope >= threshold) or (direction == "down" and slope <= -threshold) or (
        direction == "both" and abs(slope) >= threshold
    )
    return {
        "vital": vital,
        "slope_per_hour": round(slope, 3),
        "t_stat": round(t, 2),
        "points": len(window),
        "window_hours": hours,
        "threshold_per_hour": threshold,
        "flagged": bool(len(window) >= TREND_MIN_POINTS and steep and abs(t) >= TREND_MIN_T),
    }
