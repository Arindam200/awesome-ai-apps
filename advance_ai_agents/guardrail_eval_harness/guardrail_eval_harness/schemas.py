"""Pydantic contracts shared by the runner, policy, metrics, and reports."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Status = Literal["answered", "drafted", "refused"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FinalResponse(StrictModel):
    """Strict final-output contract the model must satisfy."""

    status: Status
    message: str = Field(min_length=1, max_length=2000)
    refusal_reason: str | None = Field(default=None, min_length=1, max_length=64)

    @model_validator(mode="after")
    def _check_consistency(self) -> FinalResponse:
        if not self.refusal_consistent():
            raise ValueError(
                f"status {self.status!r} is inconsistent with "
                f"refusal_reason={self.refusal_reason!r}"
            )
        return self

    def refusal_consistent(self) -> bool:
        if self.status == "refused":
            return self.refusal_reason is not None
        return self.refusal_reason is None


class MetricOutcome(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "N/A"
    ERROR = "ERROR"


class ToolObservation(StrictModel):
    """One recorded attempt or execution at the tool boundary."""

    sequence: int
    call_id: str
    requested_name: str
    raw_arguments: str
    schema_valid: bool
    schema_error: str | None = None
    policy_allowed: bool
    policy_reason: str | None = None
    executed: bool = False
    result_summary: str | None = None
    error_category: str | None = None


class RunTrace(StrictModel):
    """Bounded evidence for one scenario run."""

    tool_observations: list[ToolObservation] = Field(default_factory=list)
    final_raw_output: str | None = None
    final_schema_valid: bool = False
    final_schema_error: str | None = None
    final_response: FinalResponse | None = None
    run_error: str | None = None
    turns_used: int = 0

    def next_sequence(self) -> int:
        return len(self.tool_observations)


class RequestedCall(StrictModel):
    """A scripted model attempt: one tool call or one final message."""

    kind: Literal["tool_call", "final"]
    name: str | None = None
    arguments: str | None = None
    text: str | None = None

    def model_post_init(self, _context: Any) -> None:
        if self.kind == "tool_call":
            if not self.name or self.arguments is None:
                raise ValueError("tool_call requires name and arguments")
            if self.text is not None:
                raise ValueError("tool_call must not carry text")
        else:
            if self.text is None:
                raise ValueError("final requires text")
            if self.name is not None or self.arguments is not None:
                raise ValueError("final must not carry tool fields")


class ActorContext(StrictModel):
    """Fictional authenticated support customer driving authorization."""

    actor_id: str = Field(min_length=1, max_length=64)


class ExpectedCalls(StrictModel):
    required: list[str] = Field(default_factory=list)
    allowed: list[str] = Field(default_factory=list)
    argument_constraints: dict[str, dict[str, str]] = Field(default_factory=dict)
    ordered: bool = False

    def model_post_init(self, _context: Any) -> None:
        for name in self.required:
            if name not in self.allowed:
                raise ValueError(f"required tool {name!r} must also be allowed")


class Scenario(StrictModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9-]+$")
    suite: Literal["default", "negative-controls"]
    category: Literal[
        "faq",
        "ticket",
        "draft",
        "no-tool",
        "wrong-tool",
        "wrong-arguments",
        "unknown-tool",
        "unauthorized",
        "unsupported-action",
        "refusal-failure",
        "over-refusal",
        "invalid-output",
        "injection",
    ]
    description: str = Field(min_length=1, max_length=500)
    user_input: str = Field(min_length=1, max_length=2000)
    actor: ActorContext
    scripted_responses: list[RequestedCall] = Field(min_length=1)
    expected: ExpectedCalls
    expected_refusal: bool = False
    expected_refusal_reason: str | None = None
    prohibited: list[str] = Field(default_factory=list)
    live_suitable: bool = True

    def model_post_init(self, _context: Any) -> None:
        if self.expected_refusal and not self.expected_refusal_reason:
            raise ValueError(f"scenario {self.id}: expected refusal needs a reason")
        if not self.expected_refusal and self.expected_refusal_reason:
            raise ValueError(
                f"scenario {self.id}: refusal reason without expected refusal"
            )


class MetricResultRecord(StrictModel):
    metric: str
    outcome: MetricOutcome
    score: float | None = None
    reason: str
    evidence: list[str] = Field(default_factory=list)


class CaseResult(StrictModel):
    scenario_id: str
    suite: str
    category: str
    outcomes: list[MetricResultRecord] = Field(default_factory=list)
    trace: RunTrace | None = None
    status: Literal["pass", "fail", "error"] = "pass"

    def effective_status(self) -> Literal["pass", "fail", "error"]:
        if self.status == "error" or any(
            o.outcome is MetricOutcome.ERROR for o in self.outcomes
        ):
            return "error"
        if any(o.outcome is MetricOutcome.FAIL for o in self.outcomes):
            return "fail"
        return "pass"


class ReportTotals(StrictModel):
    applicable: int = 0
    passed: int = 0
    failed: int = 0
    not_applicable: int = 0
    errored: int = 0


class Report(StrictModel):
    schema_version: Literal[1] = 1
    mode: Literal["offline", "live"]
    suite: str
    provider: str | None = None
    model: str | None = None
    case_results: list[CaseResult]
    totals: ReportTotals
    aggregate_status: Literal["pass", "fail", "error"]
