"""The human side of the desk: notifications, incidents and long-term memory."""

from __future__ import annotations

import json
import re
import threading
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

LEVEL_ICON = {"page": "🚨", "warn": "⚠️", "fyi": "📝"}


@dataclass
class Notification:
    at: datetime
    level: str  # page | warn | fyi
    title: str
    message: str
    run_id: str


@dataclass
class Incident:
    id: str
    service: str
    title: str
    severity: str
    opened_at: datetime
    opened_by: str
    notes: list[tuple[datetime, str]] = field(default_factory=list)
    status: str = "open"
    resolved_at: datetime | None = None

    def describe(self) -> str:
        at, note = self.notes[-1]
        head = f"{self.id} [{self.severity}, {self.service}] {self.title}, opened {self.opened_at:%H:%M}"
        if self.status == "resolved":
            return f"{head}, resolved {self.resolved_at:%H:%M}: {note}"
        return f"{head}. Latest note ({at:%H:%M}): {note}"


class Desk:
    def __init__(self, slack_webhook: str | None = None, on_notify: Callable[[Notification], None] | None = None):
        self.notifications: list[Notification] = []
        self.incidents: list[Incident] = []
        self.slack_webhook = slack_webhook
        self.on_notify = on_notify

    def notify(self, at: datetime, level: str, title: str, message: str, run_id: str) -> Notification:
        n = Notification(at, level, title.strip(), message.strip(), run_id)
        self.notifications.append(n)
        if self.on_notify:
            self.on_notify(n)
        if self.slack_webhook:
            threading.Thread(target=self._post_to_slack, args=(n,), daemon=True).start()
        return n

    def _post_to_slack(self, n: Notification) -> None:
        body = json.dumps({"text": f"{LEVEL_ICON.get(n.level, '')} *{n.title}*\n{n.message}"}).encode()
        req = urllib.request.Request(self.slack_webhook or "", data=body, headers={"Content-Type": "application/json"})
        try:
            urllib.request.urlopen(req, timeout=5).read()
        except Exception:
            pass  # delivery is best effort; the in-app inbox always has the message

    def open_incident(
        self, at: datetime, service: str, title: str, severity: str, summary: str, run_id: str
    ) -> Incident:
        for inc in self.open_incidents():
            if inc.service == service:
                raise ValueError(f"{inc.id} is already open for {service}. Update it with update_incident instead.")
        inc = Incident(
            f"INC-{len(self.incidents) + 1}", service, title.strip(), severity, at, run_id, [(at, summary.strip())]
        )
        self.incidents.append(inc)
        return inc

    def get(self, incident_id: str) -> Incident:
        for inc in self.incidents:
            if inc.id.lower() == incident_id.strip().lower():
                return inc
        raise ValueError(f"no incident {incident_id!r}. Open: {[i.id for i in self.open_incidents()] or 'none'}")

    def update_incident(self, at: datetime, incident_id: str, note: str) -> Incident:
        inc = self.get(incident_id)
        inc.notes.append((at, note.strip()))
        return inc

    def resolve_incident(self, at: datetime, incident_id: str, summary: str) -> Incident:
        inc = self.get(incident_id)
        if inc.status == "resolved":
            raise ValueError(f"{inc.id} is already resolved.")
        inc.notes.append((at, summary.strip()))
        inc.status, inc.resolved_at = "resolved", at
        return inc

    def open_incidents(self) -> list[Incident]:
        return [i for i in self.incidents if i.status == "open"]


class Memory:
    """Long-term memory: a short markdown list loaded into every run, kept across restarts."""

    MAX_NOTES = 30

    def __init__(self, path: Path):
        self.path = path
        self.notes: list[str] = []
        if path.exists():
            self.notes = [ln[2:].strip() for ln in path.read_text().splitlines() if ln.startswith("- ")]

    def add(self, at: datetime, note: str) -> bool:
        note = re.sub(r"^(\(\d{4}-\d{2}-\d{2}\)\s*)+", "", " ".join(note.split()))
        if any(note.lower() in n.lower() for n in self.notes):
            return False
        self.notes.append(f"({at:%Y-%m-%d}) {note}")
        self.notes = self.notes[-self.MAX_NOTES :]
        self._save()
        return True

    def clear(self) -> None:
        self.notes = []
        self._save()

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("# Long-term memory\n\n" + "".join(f"- {n}\n" for n in self.notes))
