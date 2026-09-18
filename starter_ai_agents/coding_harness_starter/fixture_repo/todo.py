"""A deliberately small todo module used by the coding-harness example."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class Todo:
    """One todo item in the example workspace."""

    title: str
    completed: bool = False


def list_todos(items: Iterable[Todo]) -> list[Todo]:
    """Return all supplied todo items in their original order.

    Status filtering is intentionally not implemented in this starting fixture.
    The README's example coding task asks the harness to add it safely.
    """

    return list(items)
