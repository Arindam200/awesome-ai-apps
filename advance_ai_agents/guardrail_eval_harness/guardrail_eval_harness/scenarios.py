"""Load and validate scenario fixtures before any execution."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

from guardrail_eval_harness.schemas import Scenario

SUITES = ("default", "negative-controls")


def load_scenarios(suite: str, case_ids: list[str] | None = None) -> list[Scenario]:
    if suite not in SUITES:
        raise ValueError(f"unknown suite {suite!r}; expected one of {SUITES}")
    raw = _read_scenarios()
    seen: set[str] = set()
    scenarios: list[Scenario] = []
    for item in raw:
        scenario = Scenario.model_validate(item)
        if scenario.id in seen:
            raise ValueError(f"duplicate scenario id {scenario.id!r}")
        seen.add(scenario.id)
        if scenario.suite == suite:
            scenarios.append(scenario)
    if case_ids:
        unknown = [cid for cid in case_ids if cid not in seen]
        if unknown:
            raise ValueError(f"unknown case ids: {unknown}")
        wanted = set(case_ids)
        scenarios = [s for s in scenarios if s.id in wanted]
        if not scenarios:
            raise ValueError(
                f"empty selection for suite {suite!r} and cases {case_ids}"
            )
    else:
        if not scenarios:
            raise ValueError(f"suite {suite!r} contains no scenarios")
    return scenarios


def _read_scenarios() -> list[dict[str, Any]]:
    resource = resources.files("guardrail_eval_harness").joinpath("scenarios.json")
    data = json.loads(resource.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise TypeError("scenarios.json must contain a JSON list")
    return data
