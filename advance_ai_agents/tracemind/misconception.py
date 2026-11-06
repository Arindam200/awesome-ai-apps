from dataclasses import dataclass


@dataclass
class Misconception:
    name: str
    description: str
    keywords: list[str]


KNOWN_MISCONCEPTIONS = [
    Misconception(
        name="Loop variable changes the original collection",
        description=(
            "The student assumes assigning to a loop variable directly "
            "changes the corresponding item in the original collection."
        ),
        keywords=[
            "changes the list",
            "changes the original list",
            "modifies the list",
            "changes the collection",
            "modifies the collection",
        ],
    ),
    Misconception(
        name="Loop runs only once",
        description=(
            "The student assumes a loop processes only the first item "
            "instead of repeating for each item."
        ),
        keywords=[
            "runs only once",
            "only runs once",
            "first item only",
            "only the first item",
        ],
    ),
]


def find_misconceptions(step: str) -> list[Misconception]:
    """Find known misconception patterns in one reasoning step."""
    step_lower = step.lower()
    matches = []

    for misconception in KNOWN_MISCONCEPTIONS:
        if any(keyword in step_lower for keyword in misconception.keywords):
            matches.append(misconception)

    return matches
