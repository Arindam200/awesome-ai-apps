from misconception import find_misconceptions
from parser import parse_trace
from tracker import PersistenceTracker


def diagnose(trace: str) -> list[dict]:
    """Analyze a student's reasoning trace."""
    steps = parse_trace(trace)
    results = []

    for index, step in enumerate(steps, start=1):
        matches = find_misconceptions(step)

        for misconception in matches:
            results.append(
                {
                    "step": index,
                    "reasoning": step,
                    "misconception": misconception.name,
                    "description": misconception.description,
                }
            )

    return results


def main() -> None:
    sample_trace = """
I have a list of numbers.
The loop variable is changed, so that changes the original list.
The loop then continues with the next item.
""".strip()

    tracker = PersistenceTracker()
    results = diagnose(sample_trace)

    print("TraceMind — Adaptive Learning Diagnostic Agent")
    print("=" * 50)

    if not results:
        print("No known misconceptions detected.")
        return

    for result in results:
        history = tracker.record(result["misconception"])

        print(f"\nStep {result['step']}: {result['reasoning']}")
        print(f"Misconception: {result['misconception']}")
        print(f"Explanation: {result['description']}")
        print(f"Learning history: {history}")


if __name__ == "__main__":
    main()
