from __future__ import annotations

from pathlib import Path
import shutil
import tempfile
import textwrap
import unittest

from coding_harness.models import FileOperation, ImplementationPlan, PatchProposal
from coding_harness.runner import HarnessRunner
from coding_harness.workspace import Workspace


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class AcceptAll:
    def approve(self, operations: object) -> bool:
        return True


class FixtureProposalProvider:
    def propose(
        self,
        task: str,
        workspace: Workspace,
        previous: object,
        preparation_feedback: str | None = None,
    ) -> PatchProposal:
        old_function = textwrap.dedent(
            '''\
            def list_todos(items: Iterable[Todo]) -> list[Todo]:
                """Return all supplied todo items in their original order.

                Status filtering is intentionally not implemented in this starting fixture.
                The README's example coding task asks the harness to add it safely.
                """

                return list(items)
            '''
        )
        new_function = textwrap.dedent(
            '''\
            def list_todos(items: Iterable[Todo], status: str = "all") -> list[Todo]:
                """Return todos selected by all, completed, or pending status."""

                if status not in {"all", "completed", "pending"}:
                    raise ValueError(f"unsupported todo status: {status}")
                todos = list(items)
                if status == "all":
                    return todos
                completed = status == "completed"
                return [todo for todo in todos if todo.completed is completed]
            '''
        )
        filtering_tests = textwrap.dedent(
            """\
            import unittest

            from todo import Todo, list_todos


            class TodoFilteringTests(unittest.TestCase):
                def setUp(self) -> None:
                    self.todos = [Todo("done", True), Todo("waiting", False)]

                def test_supported_filters(self) -> None:
                    self.assertEqual(list_todos(self.todos, "all"), self.todos)
                    self.assertEqual(list_todos(self.todos, "completed"), [self.todos[0]])
                    self.assertEqual(list_todos(self.todos, "pending"), [self.todos[1]])

                def test_invalid_filter(self) -> None:
                    with self.assertRaisesRegex(ValueError, "unsupported todo status"):
                        list_todos(self.todos, "later")
            """
        )
        return PatchProposal(
            plan=ImplementationPlan(
                task_understanding=task,
                files_to_modify=["todo.py", "tests/test_filtering.py"],
                steps=["add status filtering", "cover each mode and invalid input"],
                tests=["run the fixed unittest discovery command"],
                risks_and_assumptions=["preserve the default all-items behavior"],
            ),
            operations=[
                FileOperation(
                    operation="update",
                    path="todo.py",
                    expected_old_text=old_function,
                    content=new_function,
                    reason="implement the requested filtering behavior",
                ),
                FileOperation(
                    operation="create",
                    path="tests/test_filtering.py",
                    content=filtering_tests,
                    reason="test valid and invalid filtering modes",
                ),
            ],
        )


class FixtureFlowTests(unittest.TestCase):
    def test_filtering_task_passes_the_real_fixed_test_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace_root = Path(directory) / "fixture_repo"
            shutil.copytree(PROJECT_ROOT / "fixture_repo", workspace_root)

            summary = HarnessRunner(
                Workspace(workspace_root),
                FixtureProposalProvider(),
                AcceptAll(),
                output_fn=lambda _: None,
            ).run("Add completed-status filtering and tests")

            self.assertEqual(summary.status, "success")
            self.assertEqual(summary.attempts, 1)
            self.assertEqual(summary.updated_files, ["todo.py"])
            self.assertEqual(summary.created_files, ["tests/test_filtering.py"])
            self.assertEqual(len(summary.test_runs), 1)
            self.assertEqual(summary.test_runs[0].exit_code, 0)


if __name__ == "__main__":
    unittest.main()
