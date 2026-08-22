from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from coding_harness.approval import ApprovalGate
from coding_harness.models import FileOperation, ImplementationPlan, PatchProposal
from coding_harness.runner import HarnessRunner
from coding_harness.testing import TEST_ARGUMENTS, TestResult
from coding_harness.workspace import Workspace


def proposal(old: str, new: str) -> PatchProposal:
    return PatchProposal(
        plan=ImplementationPlan(
            task_understanding="change the sample",
            files_to_modify=["sample.py"],
            steps=["replace the value"],
            tests=["run unittest"],
            risks_and_assumptions=[],
        ),
        operations=[
            FileOperation(
                operation="update",
                path="sample.py",
                expected_old_text=old,
                content=new,
                reason="test proposal",
            )
        ],
    )


class ScriptedProvider:
    def __init__(self, proposals: list[object]) -> None:
        self.proposals = proposals
        self.calls: list[TestResult | None] = []
        self.feedback: list[str | None] = []

    def propose(
        self,
        task: str,
        workspace: Workspace,
        previous: TestResult | None,
        preparation_feedback: str | None = None,
    ) -> object:
        self.calls.append(previous)
        self.feedback.append(preparation_feedback)
        return self.proposals.pop(0)


class AcceptAll:
    def __init__(self) -> None:
        self.calls = 0

    def approve(self, operations: object) -> bool:
        self.calls += 1
        return True


class RunnerTests(unittest.TestCase):
    def test_preparation_errors_are_bounded_in_output_feedback_and_summary(
        self,
    ) -> None:
        long_detail = "x" * 5_000

        class RetryThenSucceed:
            def __init__(self) -> None:
                self.calls = 0
                self.feedback: list[str | None] = []

            def propose(
                self,
                task: str,
                workspace: Workspace,
                previous: TestResult | None,
                preparation_feedback: str | None = None,
            ) -> PatchProposal:
                self.calls += 1
                self.feedback.append(preparation_feedback)
                if self.calls == 1:
                    raise ValueError(long_detail)
                return proposal("value = 1", "value = 2")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("value = 1\n", encoding="utf-8")
            provider = RetryThenSucceed()
            output: list[str] = []

            summary = HarnessRunner(
                Workspace(root),
                provider,
                AcceptAll(),
                test_executor=lambda _: TestResult(TEST_ARGUMENTS, 0, "ok", ""),
                output_fn=output.append,
            ).run("bound retry errors")

            self.assertEqual(summary.status, "success")
            self.assertLessEqual(len(output[0]), 1_300)
            self.assertLessEqual(len(provider.feedback[1] or ""), 1_200)
            self.assertNotIn(long_detail, output[0])

        class TerminalFailure:
            def propose(self, *_: object, **__: object) -> PatchProposal:
                raise RuntimeError(long_detail)

        with tempfile.TemporaryDirectory() as directory:
            summary = HarnessRunner(
                Workspace(directory),
                TerminalFailure(),
                AcceptAll(),
                output_fn=lambda _: None,
            ).run("bound terminal errors")

        self.assertEqual(summary.status, "no_patch")
        self.assertLessEqual(len(summary.message), 1_300)
        self.assertNotIn(long_detail, summary.message)

    def test_invalid_proposal_gets_one_zero_write_correction(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "sample.py"
            target.write_text("value = 1\n", encoding="utf-8")
            provider = ScriptedProvider(
                [
                    {
                        "plan": {
                            "task_understanding": "change the sample",
                            "files_to_modify": ["sample.py"],
                            "steps": ["replace the value"],
                            "tests": "run unittest",
                            "risks_and_assumptions": [],
                        },
                        "operations": [],
                    },
                    proposal("value = 1", "value = 2"),
                ]
            )
            approval = AcceptAll()

            summary = HarnessRunner(
                Workspace(root),
                provider,
                approval,
                test_executor=lambda _: TestResult(TEST_ARGUMENTS, 0, "ok", ""),
                output_fn=lambda _: None,
            ).run("correct the proposal")

            self.assertEqual(summary.status, "success")
            self.assertEqual(approval.calls, 1)
            self.assertEqual(len(provider.calls), 2)
            self.assertIsNone(provider.feedback[0])
            self.assertIn("ValidationError", provider.feedback[1] or "")
            self.assertEqual(target.read_text(encoding="utf-8"), "value = 2\n")

    def test_success_applies_then_runs_fixed_test_executor(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("value = 1\n", encoding="utf-8")
            provider = ScriptedProvider([proposal("value = 1", "value = 2")])
            approval = AcceptAll()
            seen_workspaces: list[Workspace] = []

            def passing_test(workspace: Workspace) -> TestResult:
                seen_workspaces.append(workspace)
                return TestResult(TEST_ARGUMENTS, 0, "ok", "")

            output: list[str] = []
            summary = HarnessRunner(
                Workspace(root),
                provider,
                approval,
                test_executor=passing_test,
                output_fn=output.append,
            ).run("change it")

            self.assertEqual(summary.status, "success")
            self.assertEqual(summary.attempts, 1)
            self.assertEqual(summary.updated_files, ["sample.py"])
            self.assertEqual(
                (root / "sample.py").read_text(encoding="utf-8"), "value = 2\n"
            )
            self.assertEqual(approval.calls, 1)
            self.assertEqual(
                [workspace.root for workspace in seen_workspaces], [root.resolve()]
            )
            self.assertTrue(
                any(line.startswith("Planned tests: run unittest") for line in output)
            )
            self.assertTrue(
                any(line.startswith("Risks/assumptions:") for line in output)
            )

    def test_stops_after_three_approved_failing_attempts_and_keeps_edits(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("value = 1\n", encoding="utf-8")
            provider = ScriptedProvider(
                [
                    proposal("value = 1", "value = 2"),
                    proposal("value = 2", "value = 3"),
                    proposal("value = 3", "value = 4"),
                ]
            )
            approval = AcceptAll()

            def failing_test(_: Workspace) -> TestResult:
                return TestResult(TEST_ARGUMENTS, 1, "", "failing test")

            summary = HarnessRunner(
                Workspace(root),
                provider,
                approval,
                test_executor=failing_test,
                output_fn=lambda _: None,
            ).run("keep trying")

            self.assertEqual(summary.status, "test_failed")
            self.assertEqual(summary.attempts, 3)
            self.assertEqual(len(summary.test_runs), 3)
            self.assertEqual(approval.calls, 3)
            self.assertEqual(len(provider.calls), 3)
            self.assertIsNone(provider.calls[0])
            self.assertIsNotNone(provider.calls[1])
            self.assertEqual(
                (root / "sample.py").read_text(encoding="utf-8"), "value = 4\n"
            )

    def test_rejection_skips_test_execution_and_preserves_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("value = 1\n", encoding="utf-8")
            provider = ScriptedProvider([proposal("value = 1", "value = 2")])

            class Reject:
                def approve(self, operations: object) -> bool:
                    return False

            def should_not_run(_: Workspace) -> TestResult:
                self.fail("tests must not run after user rejection")

            summary = HarnessRunner(
                Workspace(root),
                provider,
                Reject(),
                test_executor=should_not_run,
                output_fn=lambda _: None,
            ).run("decline it")

            self.assertEqual(summary.status, "cancelled")
            self.assertEqual(summary.test_runs, [])
            self.assertEqual(
                (root / "sample.py").read_text(encoding="utf-8"), "value = 1\n"
            )

    def test_real_approval_gate_rejects_every_operation_without_writing(self) -> None:
        for operation_kind in ("create", "update"):
            with self.subTest(operation=operation_kind):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    target = root / (
                        "new.py" if operation_kind == "create" else "sample.py"
                    )
                    if operation_kind != "create":
                        target.write_text("value = 1\n", encoding="utf-8")

                    operation_args: dict[str, object] = {
                        "operation": operation_kind,
                        "path": target.name,
                        "reason": "exercise the real approval gate",
                    }
                    if operation_kind == "create":
                        operation_args["content"] = "value = 2\n"
                    elif operation_kind == "update":
                        operation_args.update(
                            expected_old_text="value = 1",
                            content="value = 2",
                        )
                    else:
                        operation_args["expected_old_text"] = "value = 1\n"

                    patch_proposal = PatchProposal(
                        plan=ImplementationPlan(
                            task_understanding=f"reject {operation_kind}",
                            files_to_modify=[target.name],
                            steps=["propose one operation"],
                            tests=["fixed unittest"],
                            risks_and_assumptions=[],
                        ),
                        operations=[FileOperation(**operation_args)],
                    )
                    provider = ScriptedProvider([patch_proposal])
                    answers = iter([""])

                    def should_not_run(_: Workspace) -> TestResult:
                        self.fail("tests must not run after user rejection")

                    summary = HarnessRunner(
                        Workspace(root),
                        provider,
                        ApprovalGate(
                            input_fn=lambda _: next(answers), output_fn=lambda _: None
                        ),
                        test_executor=should_not_run,
                        output_fn=lambda _: None,
                    ).run("reject the patch")

                    self.assertEqual(summary.status, "cancelled")
                    if operation_kind == "create":
                        self.assertFalse(target.exists())
                    else:
                        self.assertEqual(
                            target.read_text(encoding="utf-8"), "value = 1\n"
                        )


if __name__ == "__main__":
    unittest.main()
