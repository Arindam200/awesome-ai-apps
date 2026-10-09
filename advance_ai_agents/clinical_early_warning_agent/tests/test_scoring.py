from datetime import datetime, timezone

import pytest

from early_warning.models import Reading
from early_warning.scoring import (
    news2,
    qsofa,
    score_hr,
    score_rr,
    score_sbp,
    score_spo2,
    score_temp,
)

T = datetime(2026, 1, 15, 8, 0, tzinfo=timezone.utc)


def reading(**kw):
    base = {"hr": 72, "spo2": 97, "sbp": 120, "rr": 16, "temp": 36.8}
    return Reading(ts=T, **{**base, **kw})


@pytest.mark.parametrize("rr,pts", [(8, 3), (9, 1), (11, 1), (12, 0), (20, 0), (21, 2), (24, 2), (25, 3)])
def test_respiratory_rate(rr, pts):
    assert score_rr(rr) == pts


@pytest.mark.parametrize("spo2,pts", [(91, 3), (92, 2), (93, 2), (94, 1), (95, 1), (96, 0)])
def test_spo2_scale1(spo2, pts):
    assert score_spo2(spo2, on_oxygen=False) == pts


@pytest.mark.parametrize("spo2,o2,pts", [(83, False, 3), (85, False, 2), (87, False, 1), (88, False, 0), (95, False, 0),
                                          (93, True, 1), (95, True, 2), (97, True, 3)])
def test_spo2_scale2(spo2, o2, pts):
    assert score_spo2(spo2, on_oxygen=o2, scale=2) == pts


@pytest.mark.parametrize("temp,pts", [(35.0, 3), (35.1, 1), (36.0, 1), (36.1, 0), (38.0, 0), (38.1, 1), (39.0, 1), (39.1, 2)])
def test_temperature(temp, pts):
    assert score_temp(temp) == pts


@pytest.mark.parametrize("sbp,pts", [(90, 3), (91, 2), (100, 2), (101, 1), (110, 1), (111, 0), (219, 0), (220, 3)])
def test_systolic_bp(sbp, pts):
    assert score_sbp(sbp) == pts


@pytest.mark.parametrize("hr,pts", [(40, 3), (41, 1), (50, 1), (51, 0), (90, 0), (91, 1), (110, 1), (111, 2), (130, 2), (131, 3)])
def test_heart_rate(hr, pts):
    assert score_hr(hr) == pts


def test_bands():
    assert news2(reading())["band"] == "Low"
    assert news2(reading(rr=26))["band"] == "Low-Medium"
    assert news2(reading(rr=22, spo2=93, hr=95))["band"] == "Medium"  # 2 + 2 + 1
    assert news2(reading(rr=22, spo2=93, hr=115, temp=38.5))["band"] == "High"  # 7
    assert news2(reading(on_oxygen=True))["parameters"]["air_or_oxygen"] == 2
    assert news2(reading(consciousness="C"))["parameters"]["consciousness"] == 3


def test_qsofa():
    assert not qsofa(reading())["sepsis_flag"]
    assert qsofa(reading(rr=24, sbp=98))["sepsis_flag"]
    assert qsofa(reading(consciousness="V", sbp=95))["score"] == 2
