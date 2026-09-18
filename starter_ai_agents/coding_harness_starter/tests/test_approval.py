from __future__ import annotations

import unittest

from coding_harness.approval import request_approval
from coding_harness.models import FileOperation


def operation(kind: str = "create") -> FileOperation:
    if kind == "create":
        return FileOperation(
            operation=kind, path="new.py", content="x = 1\n", reason="test"
        )
    if kind == "update":
        return FileOperation(
            operation=kind,
            path="old.py",
            expected_old_text="x",
            content="y",
            reason="test",
        )
    return FileOperation(
        operation=kind, path="old.py", expected_old_text="x", reason="test"
    )


class ApprovalTests(unittest.TestCase):
    def test_default_rejection_requires_exact_lowercase_y(self) -> None:
        answers = iter([""])
        self.assertFalse(
            request_approval(
                [operation()],
                input_fn=lambda _: next(answers),
                output_fn=lambda _: None,
            )
        )

    def test_regular_change_applies_after_y(self) -> None:
        answers = iter(["y"])
        self.assertTrue(
            request_approval(
                [operation("update")],
                input_fn=lambda _: next(answers),
                output_fn=lambda _: None,
            )
        )

    def test_interrupted_input_is_a_safe_rejection(self) -> None:
        for interruption in (EOFError(), KeyboardInterrupt()):

            def interrupt(_: str, error: BaseException = interruption) -> str:
                raise error

            self.assertFalse(
                request_approval(
                    [operation()], input_fn=interrupt, output_fn=lambda _: None
                )
            )


if __name__ == "__main__":
    unittest.main()
