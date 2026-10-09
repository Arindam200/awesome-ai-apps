import json
from dataclasses import replace

import pytest

from early_warning import assess, generate
from early_warning.models import load_patient, patient_to_dict

RANK = {"Stable": 0, "Watch": 1, "Warning": 2, "Critical": 3}


def test_resting_patients_are_stable():
    assert assess(generate("stable"))["level"] == "Stable"


def test_copd_on_scale2_is_not_a_permanent_alarm():
    p = generate("copd")
    assert assess(p)["level"] == "Stable"
    assert assess(replace(p, spo2_scale=1))["news2"]["parameters"]["spo2"] >= 2  # scale 1 would keep scoring it


@pytest.mark.parametrize("name,at_least", [("slow_hypoxia", "Watch"), ("runner", "Watch"), ("early_sepsis", "Warning")])
def test_deterioration_is_caught_while_news2_is_still_low(name, at_least):
    a = assess(generate(name))
    assert RANK[a["level"]] >= RANK[at_least]
    assert a["news2"]["band"] in ("Low", "Low-Medium")  # NEWS2 alone would not yet ask for urgent review


def test_runner_rise_is_normal_to_news2_but_not_to_the_patient():
    a = assess(generate("runner"))
    assert a["news2"]["total"] == 0
    assert "hr" in a["flagged_baselines"]
    assert any("NEWS2 still scores it as normal" in f["detail"] for f in a["factors"])


def test_factors_add_up_to_the_score():
    a = assess(generate("early_sepsis"))
    assert sum(f["points"] for f in a["factors"]) == pytest.approx(a["score"], abs=1)
    assert a["factors"] == sorted(a["factors"], key=lambda f: -f["points"])


def test_news2_high_forces_critical():
    p = generate("stable")
    last = replace(p.latest, rr=26, spo2=90, hr=115)  # 3 + 3 + 2
    a = assess(replace(p, readings=p.readings[:-1] + [last]))
    assert a["news2"]["total"] >= 7 and a["level"] == "Critical"
    assert any(f["factor"] == "escalation_floor" for f in a["factors"])


def test_json_round_trip(tmp_path):
    p = generate("slow_hypoxia")
    path = tmp_path / "patient.json"
    path.write_text(json.dumps(patient_to_dict(p)))
    q = load_patient(path)
    assert q.readings == p.readings and q.spo2_scale == p.spo2_scale
    assert assess(q)["score"] == assess(p)["score"]
