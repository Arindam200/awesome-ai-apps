"""Small, explicit human approval gate for proposed filesystem changes."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from .models import FileOperation


Input = Callable[[str], str]
Output = Callable[[str], object]


class ApprovalGate:
    """Requests fresh approval for one patch; it never performs an edit."""

    def __init__(self, input_fn: Input = input, output_fn: Output = print) -> None:
        self._input = input_fn
        self._output = output_fn

    def approve(self, operations: Iterable[FileOperation]) -> bool:
        try:
            approved = self._input("Apply this patch? [y/N]: ")
        except (EOFError, KeyboardInterrupt):
            approved = ""
        if approved != "y":
            self._output("Patch was not approved; no files were changed.")
            return False
        return True


def request_approval(
    operations: Iterable[FileOperation],
    input_fn: Input = input,
    output_fn: Output = print,
) -> bool:
    """Convenient functional wrapper used by the runner and unit tests."""

    return ApprovalGate(input_fn=input_fn, output_fn=output_fn).approve(operations)
