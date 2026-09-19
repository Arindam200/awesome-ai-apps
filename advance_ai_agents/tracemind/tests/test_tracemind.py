from pathlib import Path

from misconception import find_misconceptions
from parser import parse_trace
from tracker import PersistenceTracker


def test_parse_trace():
    trace = """
    First reasoning step.
    Second reasoning step.
    """

    assert parse_trace(trace) == [
        "First reasoning step.",
        "Second reasoning step.",
    ]


def test_find_misconception():
    step = "Changing the loop variable changes the original list."

    matches = find_misconceptions(step)

    assert len(matches) == 1
    assert matches[0].name == "Loop variable changes the original collection"


def test_persistence_tracker(tmp_path: Path):
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
