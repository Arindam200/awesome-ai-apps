"""Mock appointment booking backend, in-process."""

import json
import uuid
from pathlib import Path
from typing import Any

from loguru import logger

_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "slots.json"


def _load() -> dict[str, Any]:
    return json.loads(_DATA_FILE.read_text())


def _save(state: dict[str, Any]) -> None:
    _DATA_FILE.write_text(json.dumps(state, indent=2))


def check_availability(date: str | None = None, doctor: str | None = None) -> list[dict[str, Any]]:
    state = _load()
    slots = state["available_slots"]
    if date:
        slots = [s for s in slots if s["date"] == date]
    if doctor:
        slots = [s for s in slots if doctor.lower() in s["doctor"].lower()]
    return slots


def book_appointment(slot_id: str, patient_name: str, phone: str) -> dict[str, Any]:
    state = _load()
    slot = next((s for s in state["available_slots"] if s["id"] == slot_id), None)
    if not slot:
        return {"success": False, "error": f"Slot {slot_id} not available."}

    confirmation = str(uuid.uuid4())[:8].upper()
    state["available_slots"] = [s for s in state["available_slots"] if s["id"] != slot_id]
    state["booked"].append(
        {**slot, "patient": patient_name, "phone": phone, "confirmation": confirmation}
    )
    _save(state)
    logger.info(f"Booked {slot_id} for {patient_name} -> {confirmation}")
    return {
        "success": True,
        "confirmation": confirmation,
        "date": slot["date"],
        "time": slot["time"],
        "doctor": slot["doctor"],
    }
