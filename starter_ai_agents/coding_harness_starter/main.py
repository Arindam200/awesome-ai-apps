"""Interactive entry point for the approval-gated coding harness example."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from coding_harness.agent import CodingAgent, ModelConfig
from coding_harness.approval import ApprovalGate
from coding_harness.runner import HarnessRunner
from coding_harness.testing import TestResult, run_tests
from coding_harness.workspace import Workspace, WorkspaceError


DEFAULT_WORKSPACE = Path(__file__).resolve().parent / "fixture_repo"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a small, human-approved plan/edit/test/review coding loop.",
        epilog="Example: python main.py --workspace path/to/a/small/python-project",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="existing workspace to inspect and (only after approval) edit; defaults to fixture_repo",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    input_fn: Callable[[str], str] | None = None,
    output_fn: Callable[[str], object] = print,
    proposal_provider: object | None = None,
    test_executor: Callable[[Workspace], TestResult] = run_tests,
) -> int:
    """Run the CLI; injection arguments keep tests offline and non-interactive."""
    _load_dotenv_if_available()
    args = build_parser().parse_args(argv)
    read_input = input if input_fn is None else input_fn
    try:
        workspace = Workspace(args.workspace)
    except WorkspaceError as error:
        output_fn(f"Invalid workspace: {error}")
        return 2

    if proposal_provider is None:
        try:
            proposal_provider = CodingAgent(ModelConfig.from_environment())
        except ValueError as error:
            output_fn(f"Model configuration error: {error}")
            return 2

    task = _prompt_for_task(read_input, output_fn)
    if task is None:
        output_fn("No coding task was provided; nothing was changed.")
        return 0

    runner = HarnessRunner(
        workspace,
        proposal_provider,
        ApprovalGate(input_fn=read_input, output_fn=output_fn),
        test_executor=test_executor,
        output_fn=output_fn,
    )
    summary = runner.run(task)
    _print_summary(summary, output_fn)
    return 0 if summary.status in {"success", "cancelled"} else 1


def _prompt_for_task(
    input_fn: Callable[[str], str], output_fn: Callable[[str], object]
) -> str | None:
    while True:
        try:
            task = input_fn("Describe the coding task (required): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if task:
            return task
        output_fn(
            "A non-empty coding task is required. Press Ctrl+C or Ctrl+D to cancel."
        )


def _print_summary(summary: object, output_fn: Callable[[str], object]) -> None:
    output_fn(f"\nFinal status: {summary.status}")
    output_fn(f"Attempts: {summary.attempts}")
    output_fn("Created: " + _files(summary.created_files))
    output_fn("Updated: " + _files(summary.updated_files))
    for index, test_run in enumerate(summary.test_runs, start=1):
        outcome = "timeout" if test_run.timed_out else f"exit_code={test_run.exit_code}"
        output_fn(
            f"Test run {index}: {' '.join(test_run.argv)} "
            f"({_test_result_label(test_run)}; {outcome})"
        )
    output_fn("Final tests: " + _final_test_status(summary.test_runs))
    if summary.token_usage is not None:
        usage = summary.token_usage
        output_fn(
            "Token usage: "
            f"prompt={usage.prompt_tokens}, "
            f"completion={usage.completion_tokens}, "
            f"total={usage.total_tokens}"
        )
    if summary.status == "test_failed" and summary.test_runs:
        diagnostic = _test_error_summary(summary.test_runs[-1])
        if diagnostic:
            output_fn("Final test error summary:\n" + diagnostic)
    output_fn(summary.message)


def _files(paths: list[str]) -> str:
    return ", ".join(paths) if paths else "(none)"


def _test_result_label(test_run: object) -> str:
    if test_run.timed_out:
        return "timed out"
    return "passed" if test_run.exit_code == 0 else "failed"


def _final_test_status(test_runs: list[object]) -> str:
    if not test_runs:
        return "not run"
    return _test_result_label(test_runs[-1])


def _test_error_summary(test_run: object, limit: int = 1_500) -> str:
    """Show a short final diagnostic without repeating complete captured logs."""

    if limit < 1:
        return ""
    output = "\n".join(
        part for part in (test_run.stdout, test_run.stderr) if part
    ).strip()
    if len(output) <= limit:
        return output
    marker = "... [output truncated]\n"
    if limit <= len(marker):
        return output[-limit:]
    return marker + output[-(limit - len(marker)) :]


def _load_dotenv_if_available() -> None:
    """Load a local .env for normal CLI use without making unit tests depend on it."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


if __name__ == "__main__":
    raise SystemExit(main())
