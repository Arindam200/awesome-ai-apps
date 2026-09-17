"""Optional live Nebius backend; lazily initialized, never used offline."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any

from guardrail_eval_harness.agent import MAX_TURNS, run_scenario
from guardrail_eval_harness.schemas import CaseResult, ReportTotals, RunTrace, Scenario

NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1"

DEFAULT_CASE_TIMEOUT_SECONDS = 60.0
DEFAULT_RESPONSE_SIZE_LIMIT = 20000


@dataclass
class LiveBackend:
    model_name: str
    base_url: str = NEBIUS_BASE_URL
    per_case_timeout_seconds: float = DEFAULT_CASE_TIMEOUT_SECONDS
    max_turns: int = MAX_TURNS

    def __post_init__(self) -> None:
        if not self.model_name:
            raise ValueError("--live-model is required for --mode live")
        self._api_key = os.getenv("NEBIUS_API_KEY")
        if not self._api_key:
            raise ValueError("NEBIUS_API_KEY must be set for --mode live")
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                base_url=os.getenv("EXAMPLE_BASE_URL", self.base_url),
                api_key=self._api_key,
            )
        return self._client

    def build_model(self) -> Any:
        from agents import OpenAIChatCompletionsModel

        return OpenAIChatCompletionsModel(
            model=self.model_name,
            openai_client=self._ensure_client(),
        )

    async def run_case(self, scenario: Scenario) -> RunTrace:
        model = self.build_model()
        return await run_scenario(
            scenario,
            model=model,
            timeout_seconds=self.per_case_timeout_seconds,
            max_turns=self.max_turns,
        )


def live_report(
    backend: LiveBackend, scenarios: list[Scenario]
) -> tuple[list[CaseResult], ReportTotals, str]:
    """Run live cases through the same evaluation engine as offline runs."""
    from guardrail_eval_harness.evaluation import _run_metrics

    case_results: list[CaseResult] = []
    totals = ReportTotals()
    aggregate = "pass"
    for scenario in scenarios:
        trace = asyncio.run(backend.run_case(scenario))
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
        from guardrail_eval_harness.schemas import MetricOutcome

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
