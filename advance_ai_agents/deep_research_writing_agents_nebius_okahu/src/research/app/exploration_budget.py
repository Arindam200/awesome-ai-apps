"""Exploration call budget tracking.

Persists a small state file under `.memory/` that counts each
`deep_research` / `analyze_youtube_video` call. Used to enforce a hard cap
on exploration before `compile_research` runs, so the agent can't drift
past its budget even if it ignores the prompt.
"""

import logging
import time
from pathlib import Path

from research.config.constants import (
    EXPLORATION_STATE_FILE,
    MAX_EXPLORATION_CALLS,
)
from research.utils.file_utils import load_json, save_json

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when the exploration call budget would be exceeded."""

    def __init__(self, used_calls: int, max_calls: int) -> None:
        self.used_calls = used_calls
        self.max_calls = max_calls
        super().__init__(
            f"Exploration budget exhausted: already used {used_calls} of "
            f"{max_calls} calls. Call `compile_research` now to finalize "
            f"research.md from the results collected so far."
        )


def _state_path(memory_path: Path) -> Path:
    return memory_path / EXPLORATION_STATE_FILE


def record_exploration_call(
    memory_path: Path,
    tool: str,
    query: str,
    *,
    max_calls: int = MAX_EXPLORATION_CALLS,
) -> tuple[int, int]:
    """Record an exploration tool call and enforce the call budget.

    Returns:
        Tuple of (call_index, calls_remaining). `call_index` is 1-based
        and represents this call's position in the session.

    Raises:
        BudgetExceededError: If the budget is already exhausted.
    """

    state_path = _state_path(memory_path)
    state = load_json(state_path, default={"calls": []})
    calls: list[dict] = state.get("calls", [])

    if len(calls) >= max_calls:
        logger.warning(
            f"Blocked exploration call (tool={tool}): budget of "
            f"{max_calls} calls already used."
        )
        raise BudgetExceededError(used_calls=len(calls), max_calls=max_calls)

    calls.append({"tool": tool, "query": query, "at": time.time()})
    state["calls"] = calls
    save_json(state_path, state)

    call_index = len(calls)
    calls_remaining = max_calls - call_index
    return call_index, calls_remaining


def reset_exploration_budget(memory_path: Path) -> None:
    """Clear the persisted call state.

    Called from `compile_research` so that any follow-up research after a
    finalized brief starts with a fresh budget.
    """

    state_path = _state_path(memory_path)
    if state_path.exists():
        state_path.unlink()
        logger.info("Exploration budget reset.")
