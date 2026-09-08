"""Command-line entry point for the minimal coding harness."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

from agent import build_agent
from models import FileChange, RunSummary
from tools import AgentDependencies
from workspace import Workspace, WorkspaceViolation

PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_WORKSPACE = PROJECT_ROOT / "fixture_repo"
DEFAULT_TASK = "Fix the bug in calculator.add so the repository tests pass."


def parse_args() -> argparse.Namespace:
    """Parse the coding task and optional workspace path."""
    parser = argparse.ArgumentParser(description="Run a human-gated coding agent.")
    parser.add_argument("task", nargs="?", default=DEFAULT_TASK)
    parser.add_argument(
        "--workspace",
        type=Path,
        default=DEFAULT_WORKSPACE,
        help="Repository directory the agent may inspect and edit.",
    )
    return parser.parse_args()


def approved_by_human(answer: str) -> bool:
    """Accept only an unambiguous affirmative approval."""
    return answer.strip().lower() in {"y", "yes"}


def emit_summary(summary: RunSummary) -> None:
    """Print the final result using the same JSON shape on every path."""
    print("\n=== RUN SUMMARY ===")
    print(json.dumps(summary.model_dump(), indent=2))


def preview_changes(workspace: Workspace, changes: list[FileChange]) -> bool:
    """Validate and render every diff before asking for approval."""
    try:
        workspace.validate_changes(changes)
        previews = [(change, workspace.preview_diff(change)) for change in changes]
    except WorkspaceViolation as exc:
        emit_summary(RunSummary(status="invalid_proposal", error=str(exc)))
        return False

    print("\n=== PATCH PREVIEW ===")
    for change, diff in previews:
        print(f"\n# {change.path}: {change.reason}")
        print(diff or "(no changes)")
    return True


def main() -> int:
    """Run inspect, propose, approve, apply, test, and summarize."""
    load_dotenv(PROJECT_ROOT / ".env")
    args = parse_args()
    workspace = Workspace(args.workspace)
    agent = build_agent()

    result = asyncio.run(agent.run(args.task, deps=AgentDependencies(workspace)))
    proposal = result.output

    print("\n=== STRUCTURED PROPOSAL ===")
    print(proposal.model_dump_json(indent=2))
    if not preview_changes(workspace, proposal.changes):
        return 1

    answer = input("\nApply these changes and run the allowlisted tests? [y/N] ")
    if not approved_by_human(answer):
        emit_summary(RunSummary(status="rejected"))
        return 0

    try:
        changed_files = workspace.apply_changes(proposal.changes, approved=True)
    except WorkspaceViolation as exc:
        emit_summary(RunSummary(status="apply_failed", error=str(exc)))
        return 1
    test_result = workspace.run_tests()
    summary = RunSummary(
        status="passed" if test_result.passed else "tests_failed",
        changed_files=changed_files,
        tests=test_result,
    )
    emit_summary(summary)
    return 0 if test_result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
