from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from early_warning.assess import assess
from early_warning.models import Reading
from early_warning.samples import SAMPLES, generate
from early_warning.signals import baseline, deviation, trend

T = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)


def series(hours: float, value_at, step_min: int = 5) -> list[Reading]:
    n = int(hours * 60 / step_min) + 1
    out = []
    for i in range(n):
        ts = T - timedelta(minutes=step_min * (n - 1 - i))
        h_before_end = (T - ts).total_seconds() / 3600
        out.append(Reading(ts=ts, hr=72, spo2=value_at(h_before_end), sbp=120, rr=16, temp=36.8))
    return out


def test_baseline_is_robust_and_ignores_the_last_six_hours():
    readings = series(48, lambda h: 90.0 if h < 5 else 97.0)  # the last 5 h dropped
    b = baseline(readings, "spo2")
    assert b["mean"] == 97.0
    assert b["std"] == 1.0  # floor for a perfectly steady signal


def test_no_baseline_without_enough_history():
    assert baseline(series(3, lambda h: 97.0), "spo2") is None
    assert deviation(series(3, lambda h: 97.0), "spo2")["flagged"] is False


def test_only_the_concerning_direction_is_flagged():
    high = series(48, lambda h: 100.0 if h < 0.3 else 96.0)
    low = series(48, lambda h: 91.0 if h < 0.3 else 96.0)
    assert not deviation(high, "spo2")["flagged"]  # higher SpO2 is not a problem
    assert deviation(low, "spo2")["flagged"]


def test_slow_fall_is_a_trend():
    t = trend(series(24, lambda h: 97.0 - max(0.0, 3 - h) * 0.8), "spo2")
    assert t["flagged"]
    assert t["slope_per_hour"] == pytest.approx(-0.8, abs=0.1)


def test_too_few_points_is_not_a_trend():
    assert not trend(series(0.4, lambda h: 97.0 - (0.4 - h) * 5), "spo2")["flagged"]


@pytest.mark.parametrize("name", ["stable", "copd"])
def test_resting_samples_rarely_flag_and_never_escalate(name):
    """Noise can trip a single check now and then; it must stay rare and never change the level."""
    p = generate(name)
    checks = flags = 0
    for i in range(len(p.readings) - 288, len(p.readings), 6):
        window = p.readings[: i + 1]
        for vital in ("hr", "spo2", "sbp", "rr", "temp"):
            checks += 2
            flags += trend(window, vital)["flagged"] + deviation(window, vital)["flagged"]
        assert assess(replace(p, readings=window))["level"] == "Stable", (name, i)
    assert flags / checks < 0.01, f"{flags} flags in {checks} checks"


def test_samples_are_deterministic():
    assert generate("runner").readings[-1] == generate("runner").readings[-1]
    assert set(SAMPLES) == {"stable", "slow_hypoxia", "early_sepsis", "runner", "copd"}
