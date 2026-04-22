"""In-process JSON-backed mock database for attendees and event metadata."""

import json
import threading
from pathlib import Path
from typing import Any

_DATA_DIR = Path(__file__).resolve().parent / "data"
_ATTENDEES = _DATA_DIR / "attendees.json"
_EVENT = _DATA_DIR / "event.json"
_LOCK = threading.Lock()

VALID_STATUSES = {"pending", "confirmed", "declined", "maybe", "no_answer"}


def get_event() -> dict[str, Any]:
    return json.loads(_EVENT.read_text())


def list_attendees() -> list[dict[str, Any]]:
    return json.loads(_ATTENDEES.read_text())


def get_attendee(attendee_id: str) -> dict[str, Any] | None:
    return next((a for a in list_attendees() if a["id"] == attendee_id), None)


def update_attendee(attendee_id: str, **changes: Any) -> dict[str, Any]:
    if "status" in changes and changes["status"] not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {changes['status']}")

    with _LOCK:
        attendees = json.loads(_ATTENDEES.read_text())
        for a in attendees:
            if a["id"] == attendee_id:
                a.update(changes)
                _ATTENDEES.write_text(json.dumps(attendees, indent=2))
                return a
    raise KeyError(f"Attendee {attendee_id} not found")


def increment_attempts(attendee_id: str) -> int:
    attendee = get_attendee(attendee_id)
    if not attendee:
        raise KeyError(f"Attendee {attendee_id} not found")
    new_count = attendee.get("attempts", 0) + 1
    update_attendee(attendee_id, attempts=new_count)
    return new_count
