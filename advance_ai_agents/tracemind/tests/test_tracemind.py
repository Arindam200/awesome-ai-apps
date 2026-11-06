from pathlib import Path

from misconception import find_misconceptions
from parser import parse_trace
from tracker import PersistenceTracker


def test_parse_trace():
    """Parse a reasoning trace into individual steps."""
    trace = """
    First reasoning step.
    Second reasoning step.
    """

    assert parse_trace(trace) == [
        "First reasoning step.",
        "Second reasoning step.",
    ]


def test_find_misconception():
    """Detect a known loop-variable misconception."""
    step = "Changing the loop variable changes the original list."

    matches = find_misconceptions(step)

    assert len(matches) == 1
    assert matches[0].name == "Loop variable changes the original collection"


def test_persistence_tracker(tmp_path: Path):
    """Persist and increment misconception history."""
    history_file = tmp_path / "learning_history.json"
    tracker = PersistenceTracker(str(history_file))

    first_history = tracker.record(
        "Loop variable changes the original collection"
    )
    second_history = tracker.record(
        "Loop variable changes the original collection"
    )

    assert first_history["Loop variable changes the original collection"] == 1
    assert second_history["Loop variable changes the original collection"] == 2


def test_find_misconception_with_empty_input():
    """Return no misconceptions for empty input."""
    assert find_misconceptions("") == []


def test_find_misconception_with_no_match():
    """Return no misconceptions when no known pattern is present."""
    assert find_misconceptions("This is a normal reasoning step.") == []
