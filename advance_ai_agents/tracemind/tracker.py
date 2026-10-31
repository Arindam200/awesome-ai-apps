import json
from pathlib import Path


class PersistenceTracker:
    """Store and retrieve recurring misconception history."""

    def __init__(self, history_file: str = "learning_history.json"):
        self.history_file = Path(history_file)

    def load_history(self) -> dict[str, int]:
        """Load misconception counts from disk."""
        if not self.history_file.exists():
            return {}

        try:
            history = json.loads(self.history_file.read_text())

            if not isinstance(history, dict) or not all(
                isinstance(name, str)
                and type(count) is int
                and count >= 0
                for name, count in history.items()
            ):
                return {}

            return history
        except (json.JSONDecodeError, OSError):
            return {}

    def record(self, misconception_name: str) -> dict[str, int]:
        """Record one occurrence of a misconception."""
        history = self.load_history()
        history[misconception_name] = history.get(misconception_name, 0) + 1

        self.history_file.write_text(
            json.dumps(history, indent=2)
        )

        return history
