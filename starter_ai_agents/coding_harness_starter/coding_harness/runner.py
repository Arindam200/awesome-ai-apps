"""Deterministic plan → approval → apply → test → review orchestration."""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from pydantic import ValidationError

from .agent import ProposalProvider
from .approval import ApprovalGate
from .models import PatchProposal, RunSummary, TestRunRecord
from .patching import (
    PatchApplyError,
    PatchValidationError,
    apply_prepared_patch,
    prepare_patch,
    render_unified_diff,
)
from .testing import TEST_COMMAND_DISPLAY, TestResult, run_tests
from .workspace import Workspace


Output = Callable[[str], object]
TestExecutor = Callable[[Workspace], TestResult]
MAX_PREPARATION_ATTEMPTS = 2


class HarnessRunner:
    """Runs at most three independently approved edit attempts.

    The runner intentionally accepts all collaborators as constructor arguments.
    Tests can therefore use an in-memory proposal provider and test executor;
    invoking this module never requires a model API key or a network connection.
    """

    def __init__(
        self,
        workspace: Workspace,
        proposal_provider: ProposalProvider | object,
        approval_gate: ApprovalGate | object,
        *,
        test_executor: TestExecutor = run_tests,
        output_fn: Output = print,
        max_attempts: int = 3,
    ) -> None:
        if not 1 <= max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        self.workspace = workspace
        self.proposal_provider = proposal_provider
        self.approval_gate = approval_gate
        self.test_executor = test_executor
        self.output = output_fn
        self.max_attempts = max_attempts

    def run(self, task: str) -> RunSummary:
        """Run the synchronous CLI loop, adapting async real agents if needed."""
        return asyncio.run(self.run_async(task))

    async def run_async(self, task: str) -> RunSummary:
        task = task.strip()
        if not task:
            raise ValueError("coding task cannot be empty")

        created: list[str] = []
        updated: list[str] = []
        test_runs: list[TestRunRecord] = []
        last_test: TestResult | None = None
        for attempt in range(1, self.max_attempts + 1):
            proposal, prepared, preparation_error = await self._prepare_proposal(
                task, last_test
            )
            if proposal is None or prepared is None:
                return self._summary(
                    task,
                    "test_failed" if test_runs else "no_patch",
                    attempt - 1,
                    created,
                    updated,
                    test_runs,
                    preparation_error or "No patch proposal was prepared.",
                )

            self._show_proposal(attempt, proposal, prepared)
            if not self.approval_gate.approve(proposal.operations):
                return self._summary(
                    task,
                    "cancelled",
                    attempt,
                    created,
                    updated,
                    test_runs,
                    "User declined the patch; no files from this attempt were applied.",
                )

            try:
                applied_paths = apply_prepared_patch(prepared)
            except PatchApplyError as error:
                self._record_applied_paths(
                    prepared, error.applied_paths, created, updated
                )
                message = f"Patch application failed: {error}"
                self.output(message)
                return self._summary(
                    task,
                    "apply_failed",
                    attempt,
                    created,
                    updated,
                    test_runs,
                    message,
                )
            except (PatchValidationError, OSError) as error:
                message = (
                    f"Patch was not applied because workspace state changed: {error}"
                )
                self.output(message)
                return self._summary(
                    task,
                    "apply_failed",
                    attempt,
                    created,
                    updated,
                    test_runs,
                    message,
                )

            self._record_applied_paths(prepared, applied_paths, created, updated)
            try:
                last_test = self.test_executor(self.workspace)
            except Exception as error:
                message = f"Fixed tests could not be started: {error}"
                self.output(message)
                return self._summary(
                    task,
                    "test_failed",
                    attempt,
                    created,
                    updated,
                    test_runs,
                    message,
                )
            test_runs.append(_as_record(last_test))
            self._show_test_result(attempt, last_test)
            if last_test.passed:
                return self._summary(
                    task,
                    "success",
                    attempt,
                    created,
                    updated,
                    test_runs,
                    "All fixed unittest tests passed.",
                )

        message = f"Tests still fail after {self.max_attempts} approved edit attempt(s); applied changes were kept."
        self.output(message)
        return self._summary(
            task,
            "test_failed",
            self.max_attempts,
            created,
            updated,
            test_runs,
            message,
        )

    async def _prepare_proposal(
        self,
        task: str,
        last_test: TestResult | None,
    ) -> tuple[PatchProposal | None, Any | None, str | None]:
        """Allow one zero-write correction for invalid model proposals."""

        feedback: str | None = None
        for preparation_attempt in range(MAX_PREPARATION_ATTEMPTS):
            try:
                proposal = await self._propose(task, last_test, feedback)
                return proposal, prepare_patch(self.workspace, proposal), None
            except (KeyboardInterrupt, SystemExit):
                raise
            except (PatchValidationError, ValidationError, ValueError) as error:
                message = f"Could not prepare a patch: {type(error).__name__}: {error}."
                if preparation_attempt + 1 == MAX_PREPARATION_ATTEMPTS:
                    return None, None, f"{message} No files were applied."
                self.output(f"{message} Requesting one corrected proposal.")
                feedback = _bounded_preparation_feedback(error)
            except Exception as error:
                message = f"Could not prepare a patch: {type(error).__name__}: {error}."
                return None, None, f"{message} No files were applied."

        raise AssertionError("preparation loop must return or raise")

    async def _propose(
        self,
        task: str,
        last_test: TestResult | None,
        preparation_feedback: str | None,
    ) -> PatchProposal:
        method = getattr(self.proposal_provider, "propose")
        proposal = method(task, self.workspace, last_test, preparation_feedback)
        if inspect.isawaitable(proposal):
            proposal = await proposal
        if not isinstance(proposal, PatchProposal):
            if hasattr(PatchProposal, "model_validate"):
                proposal = PatchProposal.model_validate(proposal)
            else:
                proposal = PatchProposal.parse_obj(proposal)
        return proposal

    def _show_proposal(
        self, attempt: int, proposal: PatchProposal, prepared: Any
    ) -> None:
        plan = proposal.plan
        self.output(
            f"\nAttempt {attempt}/{self.max_attempts}: {plan.task_understanding}"
        )
        self.output("Plan: " + "; ".join(plan.steps))
        if plan.files_to_modify:
            self.output("Planned files: " + ", ".join(plan.files_to_modify))
        self.output("Planned tests: " + _file_list(plan.tests))
        self.output("Risks/assumptions: " + _file_list(plan.risks_and_assumptions))
        self.output("Create: " + _file_list(prepared.created_files))
        self.output("Update: " + _file_list(prepared.updated_files))
        self.output(f"Fixed tests after approval: {TEST_COMMAND_DISPLAY}")
        self.output("Full diff:\n" + render_unified_diff(prepared))

    def _show_test_result(self, attempt: int, result: TestResult) -> None:
        state = "passed" if result.passed else "failed"
        self.output(
            f"Test run {attempt}: {state} (exit_code={result.exit_code}, timed_out={result.timed_out})"
        )
        if not result.passed and result.error_summary():
            self.output("Test error summary:\n" + result.error_summary())

    @staticmethod
    def _record_applied_paths(
        prepared: Any,
        applied_paths: list[str],
        created: list[str],
        updated: list[str],
    ) -> None:
        applied = set(applied_paths)
        for item in prepared.operations:
            if item.relative_path not in applied:
                continue
            destination = created if item.operation.operation == "create" else updated
            if item.relative_path not in destination:
                destination.append(item.relative_path)

    @staticmethod
    def _summary(
        task: str,
        status: str,
        attempts: int,
        created: list[str],
        updated: list[str],
        test_runs: list[TestRunRecord],
        message: str,
    ) -> RunSummary:
        return RunSummary(
            task=task,
            status=status,
            attempts=attempts,
            created_files=created,
            updated_files=updated,
            test_runs=test_runs,
            message=message,
        )


def _as_record(result: TestResult) -> TestRunRecord:
    return TestRunRecord(
        argv=list(result.command),
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _file_list(files: list[str]) -> str:
    return ", ".join(files) if files else "(none)"


def _bounded_preparation_feedback(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"[:1_200]
