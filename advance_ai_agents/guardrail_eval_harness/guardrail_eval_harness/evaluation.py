"""Evaluation engine: runs scenarios, applies DeepEval metrics, builds results."""

from __future__ import annotations

import asyncio

from deepeval.evaluate.configs import (
    AsyncConfig,
    CacheConfig,
    DisplayConfig,
    ErrorConfig,
)
from deepeval.evaluate.evaluate import evaluate
from deepeval.metrics import BaseMetric

from guardrail_eval_harness.agent import run_scenario
from guardrail_eval_harness.metrics import (
    METRIC_CLASSES,
    applicable_metrics,
    build_test_case,
)
from guardrail_eval_harness.schemas import (
    CaseResult,
    MetricOutcome,
    MetricResultRecord,
    ReportTotals,
    RunTrace,
    Scenario,
)


def _run_metrics(scenario: Scenario, trace: RunTrace) -> list[MetricResultRecord]:
    records: list[MetricResultRecord] = []
    expected = scenario.expected.model_dump()
    expected["expected_refusal"] = scenario.expected_refusal
    expected["expected_refusal_reason"] = scenario.expected_refusal_reason
    test_case = build_test_case(scenario.id, scenario.user_input, trace, expected)
    metric_names = applicable_metrics(scenario.category)
    metrics: list[BaseMetric] = [METRIC_CLASSES[name]() for name in metric_names]
    try:
        results = evaluate(
            test_cases=[test_case],
            metrics=metrics,
            async_config=AsyncConfig(run_async=False),
            cache_config=CacheConfig(write_cache=False, use_cache=False),
            display_config=DisplayConfig(
                show_indicator=False,
                print_results=False,
                verbose_mode=False,
                inspect_after_run=False,
            ),
            error_config=ErrorConfig(ignore_errors=False, skip_on_missing_params=False),
        )
    except (AssertionError, RuntimeError, ValueError) as exc:
        for name in metric_names:
            records.append(
                MetricResultRecord(
                    metric=name,
                    outcome=MetricOutcome.ERROR,
                    reason=f"evaluator exception: {type(exc).__name__}: {exc}"[:300],
                )
            )
        return records
    metrics_data = results.test_results[0].metrics_data or []
    by_name = {m.name: m for m in metrics_data}
    for name in metric_names:
        data = by_name.get(name)
        if data is None:
            records.append(
                MetricResultRecord(
                    metric=name,
                    outcome=MetricOutcome.ERROR,
                    reason="metric produced no result",
                )
            )
            continue
        if data.error:
            outcome = MetricOutcome.ERROR
        elif data.success is True:
            outcome = MetricOutcome.PASS
        else:
            outcome = MetricOutcome.FAIL
        records.append(
            MetricResultRecord(
                metric=name,
                outcome=outcome,
                score=data.score,
                reason=(data.reason or "")[:300],
            )
        )
    return records


def evaluate_scenarios(
    scenarios: list[Scenario], mode: str
) -> tuple[list[CaseResult], ReportTotals, str]:
    del mode  # mode is reported at the report level; execution is identical
    case_results: list[CaseResult] = []
    totals = ReportTotals()
    aggregate = "pass"
    for scenario in scenarios:
        trace = asyncio.run(run_scenario(scenario))
        records = _run_metrics(scenario, trace)
        case = CaseResult(
            scenario_id=scenario.id,
            suite=scenario.suite,
            category=scenario.category,
            outcomes=records,
            trace=trace,
            status="pass",
        )
        case.status = case.effective_status()
        case_results.append(case)
        for record in records:
            if record.outcome is MetricOutcome.NOT_APPLICABLE:
                totals.not_applicable += 1
            else:
                totals.applicable += 1
                if record.outcome is MetricOutcome.PASS:
                    totals.passed += 1
                elif record.outcome is MetricOutcome.FAIL:
                    totals.failed += 1
                else:
                    totals.errored += 1
        if case.status == "error":
            aggregate = "error"
        elif case.status == "fail" and aggregate != "error":
            aggregate = "fail"
    return case_results, totals, aggregate
