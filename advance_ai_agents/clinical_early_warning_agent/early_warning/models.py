"""Plain data types shared by the clinical tools and the agent."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

VITALS = ("hr", "spo2", "sbp", "rr", "temp")

VITAL_INFO = {
    "hr": {"label": "Heart rate", "unit": "bpm", "decimals": 0},
    "spo2": {"label": "SpO2", "unit": "%", "decimals": 0},
    "sbp": {"label": "Systolic BP", "unit": "mmHg", "decimals": 0},
    "rr": {"label": "Respiratory rate", "unit": "/min", "decimals": 0},
    "temp": {"label": "Temperature", "unit": "°C", "decimals": 1},
}


def fmt(vital: str, value: float, decimals: int | None = None) -> str:
    """A value with its unit, e.g. "93 bpm", "94%", "38.4 °C"."""
    info = VITAL_INFO[vital]
    d = info["decimals"] if decimals is None else decimals
    text = f"{value:.{d}f}"
    return f"{text}{info['unit']}" if info["unit"] == "%" else f"{text} {info['unit']}"


@dataclass(frozen=True)
class Reading:
    ts: datetime
    hr: float
    spo2: float
    sbp: float
    rr: float
    temp: float
    on_oxygen: bool = False
    consciousness: str = "A"  # A = alert; C = new confusion; V / P / U

    def get(self, vital: str) -> float:
        return getattr(self, vital)


@dataclass
class Patient:
    id: str
    label: str
    readings: list[Reading]  # oldest first; the last one is "now"
    conditions: list[str] = field(default_factory=list)
    spo2_scale: int = 1  # NEWS2 SpO2 scale 2 for a prescribed 88-92% target (e.g. COPD)

    @property
    def latest(self) -> Reading:
        return self.readings[-1]


def _parse_time(text: str) -> datetime:
    """ISO 8601; a timestamp without an offset is taken as UTC."""
    ts = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def patient_from_dict(data: dict) -> Patient:
    """Build a Patient from JSON like {"patient": {...}, "readings": [{"ts": "...", "hr": 72, ...}]}."""
    if not isinstance(data, dict):
        raise ValueError("Patient JSON must be an object with 'patient' and 'readings'")
    meta = data.get("patient", {})
    readings = [
        Reading(
            ts=_parse_time(r["ts"]),
            hr=float(r["hr"]),
            spo2=float(r["spo2"]),
            sbp=float(r["sbp"]),
            rr=float(r["rr"]),
            temp=float(r["temp"]),
            on_oxygen=bool(r.get("on_oxygen", False)),
            consciousness=str(r.get("consciousness", "A")),
        )
        for r in data["readings"]
    ]
    if not readings:
        raise ValueError("A patient needs at least one reading")
    readings.sort(key=lambda r: r.ts)
    return Patient(
        id=str(meta.get("id", "patient")),
        label=str(meta.get("label", meta.get("id", "Patient"))),
        readings=readings,
        conditions=list(meta.get("conditions", [])),
        spo2_scale=int(meta.get("spo2_scale", 1)),
    )


def load_patient(path: str | Path) -> Patient:
    return patient_from_dict(json.loads(Path(path).read_text()))


def patient_to_dict(p: Patient) -> dict:
    return {
        "patient": {"id": p.id, "label": p.label, "conditions": p.conditions, "spo2_scale": p.spo2_scale},
        "readings": [
            {"ts": r.ts.isoformat(), "hr": r.hr, "spo2": r.spo2, "sbp": r.sbp, "rr": r.rr, "temp": r.temp,
             "on_oxygen": r.on_oxygen, "consciousness": r.consciousness}
            for r in p.readings
        ],
    }
