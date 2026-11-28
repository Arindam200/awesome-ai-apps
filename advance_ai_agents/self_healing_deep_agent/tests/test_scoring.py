"""The benchmark's report check compares every model's cost, not just the total."""
from scenarios import compare_costs, expected_costs
from provider_api.server import FAULTS


def test_correct_costs_pass():
    ok, note = compare_costs(expected_costs())
    assert ok, note


def test_right_total_but_wrong_split_fails():
    want = expected_costs()
    models = list(want)
    moved = dict(want)
    moved[models[0]] += moved[models[1]]                     # same total, wrong per-model costs
    moved[models[1]] = 0.0
    assert abs(sum(moved.values()) - sum(want.values())) < 1e-9
    ok, note = compare_costs(moved)
    assert not ok and "per-model" in note


def test_retired_model_may_appear_under_its_new_id():
    FAULTS.reset(retired_model_in_logs=True)
    want = expected_costs()
    renamed = {("Qwen/Qwen3-235B-A22B-Instruct-2507" if m == "Qwen/Qwen3-235B-A22B-Instruct" else m): c
               for m, c in want.items()}
    assert compare_costs(renamed)[0]


def test_missing_model_fails():
    want = expected_costs()
    want.pop(next(iter(want)))
    assert not compare_costs(want)[0]
