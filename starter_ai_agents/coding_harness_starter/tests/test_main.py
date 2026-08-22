from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import main as cli
from coding_harness.models import (
    FileOperation,
    ImplementationPlan,
    PatchProposal,
    RunSummary,
    TestRunRecord,
)
from coding_harness.testing import TEST_ARGUMENTS, TestResult
from coding_harness.workspace import Workspace


def update_proposal() -> PatchProposal:
    return PatchProposal(
        plan=ImplementationPlan(
            task_understanding="update the sample",
            files_to_modify=["sample.py"],
            steps=["replace the value"],
            tests=["fixed unittest discovery"],
            risks_and_assumptions=[],
        ),
        operations=[
            FileOperation(
                operation="update",
                path="sample.py",
                expected_old_text="value = 1",
                content="value = 2",
                reason="exercise the CLI loop",
            )
        ],
    )


class OneProposalProvider:
    def propose(
        self,
        task: str,
        workspace: Workspace,
        previous: TestResult | None,
        preparation_feedback: str | None = None,
    ) -> PatchProposal:
        return update_proposal()


class MainTests(unittest.TestCase):
    def test_parser_exposes_only_workspace_and_help_has_a_runnable_example(
        self,
    ) -> None:
        parser = cli.build_parser()
        option_destinations = {
            action.dest for action in parser._actions if action.option_strings
        }

        self.assertIn("workspace", option_destinations)
        self.assertNotIn("task", option_destinations)
        self.assertNotIn("test_command", option_destinations)
        self.assertIn("python main.py", parser.format_help())

    def test_cli_requires_an_interactive_task_then_applies_approved_patch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "sample.py").write_text("value = 1\n", encoding="utf-8")
            answers = iter(["", "change it", "y"])
            output: list[str] = []

            exit_code = cli.main(
                ["--workspace", str(root)],
                input_fn=lambda _: next(answers),
                output_fn=output.append,
                proposal_provider=OneProposalProvider(),
                test_executor=lambda _: TestResult(TEST_ARGUMENTS, 0, "ok", ""),
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(
                (root / "sample.py").read_text(encoding="utf-8"), "value = 2\n"
            )
            self.assertIn(
                "A non-empty coding task is required. Press Ctrl+C or Ctrl+D to cancel.",
                output,
            )
            self.assertTrue(
                any(line.endswith("Final status: success") for line in output)
            )
            self.assertIn("Final tests: passed", output)

    def test_missing_model_configuration_returns_a_safe_actionable_error(self) -> None:
        output: list[str] = []

        def task_must_not_be_requested(_: str) -> str:
            self.fail(
                "model configuration must be validated before prompting for a task"
            )

        with patch.object(
            cli.ModelConfig,
            "from_environment",
            side_effect=ValueError("Missing model configuration: NEBIUS_API_KEY."),
        ):
            exit_code = cli.main(
                [], input_fn=task_must_not_be_requested, output_fn=output.append
            )

        self.assertEqual(exit_code, 2)
        self.assertEqual(
            output[-1],
            "Model configuration error: Missing model configuration: NEBIUS_API_KEY.",
        )

    def test_failure_summary_reports_each_result_and_a_bounded_error_tail(self) -> None:
        summary = RunSummary(
            task="change it",
            status="test_failed",
            attempts=3,
            test_runs=[
                TestRunRecord(
                    argv=list(TEST_ARGUMENTS),
                    exit_code=1,
                    stdout="",
                    stderr="x" * 2_000 + "\nAssertionError: still failing\n",
                )
            ],
            message="Tests still fail after 3 approved edit attempt(s); applied changes were kept.",
        )
        output: list[str] = []

        cli._print_summary(summary, output.append)

        self.assertIn("Attempts: 3", output)
        self.assertTrue(any("failed; exit_code=1" in line for line in output))
        self.assertIn("Final tests: failed", output)
        diagnostic = next(
            line for line in output if line.startswith("Final test error summary:")
        )
        self.assertLessEqual(
            len(diagnostic.removeprefix("Final test error summary:\n")), 1_500
        )
        self.assertIn("AssertionError: still failing", diagnostic)
        self.assertLessEqual(len(cli._test_error_summary(summary.test_runs[0], 5)), 5)
        self.assertEqual(cli._test_error_summary(summary.test_runs[0], 0), "")

    def test_task_prompt_interruption_is_a_clean_cancellation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output: list[str] = []

            def interrupt(_: str) -> str:
                raise EOFError

            exit_code = cli.main(
                ["--workspace", directory],
                input_fn=interrupt,
                output_fn=output.append,
                proposal_provider=OneProposalProvider(),
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            output[-1], "No coding task was provided; nothing was changed."
        )


if __name__ == "__main__":
    unittest.main()
