"""Glue: the clock, the world, the cron server and the agent.

Every tick moves the simulated clock forward one minute. The world produces
whatever happens in that minute, then the cron server fires every schedule
that's due and each one wakes the agent. The clock stays put while the agent
works, so a slow model call never makes it miss an event.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Callable

from agent import DEFAULT_MODEL, OnCallContext, RunRecord, build_agent, run_agent
from cron import CronServer, Schedule
from desk import Desk, Memory
from world import World

HERE = Path(__file__).parent
SCHEDULES_DIR = HERE / "schedules"
MEMORY_PATH = HERE / "state" / "memory.md"
IDLE_PAUSE_SECONDS = 30  # the UI loop pauses itself when no browser tab is watching


def trigger_message(sch: Schedule, now: datetime) -> str:
    """The user message of a scheduled run: which schedule fired, and its prompt."""
    if sch.kind == "static":
        return f"[Schedule `{sch.id}` ({sch.cron}) fired at {now:%H:%M}.]\n\n{sch.prompt}"
    assert sch.created_at is not None
    ago = int((now - sch.created_at).total_seconds() // 60)
    if sch.kind == "follow-up":
        head = (
            f"[Your follow-up `{sch.id}` fired at {now:%H:%M}. You set it at {sch.created_at:%H:%M} "
            f"({ago} min ago). Anything above this message is stale: fetch fresh data.]"
        )
    else:
        head = (
            f"[Your recurring schedule `{sch.id}` ({sch.cron}) fired at {now:%H:%M}. You created it at "
            f"{sch.created_at:%H:%M} in {sch.created_by}.]"
        )
    return f"{head}\n\nYour note to yourself: {sch.prompt}"


class OnCallRuntime:
    def __init__(
        self,
        *,
        start: datetime | None = None,
        auto_approve_after: int | None = None,
        memory_path: Path = MEMORY_PATH,
        model: str | None = None,
        agent=None,
    ):
        start = start or datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        self.listeners: list[Callable[[str, object], None]] = []
        self.world = World(start)
        self.cron = CronServer(start)
        self.cron.load_static(SCHEDULES_DIR)
        self.desk = Desk(
            slack_webhook=os.getenv("SLACK_WEBHOOK_URL") or None, on_notify=lambda n: self.emit("notify", n)
        )
        self.memory = Memory(memory_path)
        self.model_id = model or os.getenv("NEBIUS_MODEL", DEFAULT_MODEL)
        self.agent = agent if agent is not None else build_agent(self.model_id)
        self.auto_approve_after = auto_approve_after
        self.runs: list[RunRecord] = []
        self.current: RunRecord | None = None
        self._run_seq = 0
        self._ticked = False
        # background loop, used by the Streamlit app
        self.speed = 1.5  # real seconds per simulated minute
        self.running = False
        self.last_seen = time.time()
        self.error: str | None = None
        self._thread: threading.Thread | None = None

    def emit(self, kind: str, obj: object) -> None:
        for fn in self.listeners:
            fn(kind, obj)

    # ---- one tick ----------------------------------------------------------------
    def step(self) -> None:
        """One simulated minute. The very first call handles the start time itself (09:00)."""
        if self._ticked:
            for ev in self.world.advance():
                self.emit("event", ev)
        self._ticked = True
        if self.auto_approve_after is not None:
            for a in self.world.auto_decide(self.auto_approve_after):
                self.emit("decision", a)
        for sch in self.cron.due(self.world.now):
            self.fire(sch)

    def fire(self, sch: Schedule) -> RunRecord:
        now = self.world.now
        self._run_seq += 1
        rec = RunRecord(id=f"run-{self._run_seq}", at=now, schedule_id=sch.id, kind=sch.kind, prompt=sch.prompt)
        message = trigger_message(sch, now)
        self.cron.mark_fired(sch, now)
        is_triage = bool(sch.metadata.get("triage"))
        upto = len(self.world.events)

        if is_triage and not self.world.unread():
            rec.status = "skipped"
            rec.summary = "No new events since the last triage. Stayed asleep, no model call."
            self.runs.append(rec)
            self.emit("run_end", rec)
            return rec

        rec.thread_id = sch.thread_id or f"thread-{rec.id}"
        self.runs.append(rec)
        self.current = rec
        self.emit("run_start", rec)
        ctx = OnCallContext(world=self.world, cron=self.cron, desk=self.desk, memory=self.memory, run=rec)
        try:
            run_agent(self.agent, ctx, message, on_step=self.emit)
        finally:
            self.current = None
        if is_triage and rec.status == "done":
            self.world.mark_read(upto)
        self.emit("run_end", rec)
        return rec

    # ---- shift log --------------------------------------------------------------------
    def shift_log(self) -> dict:
        """Everything that happened this shift, as plain data."""
        return {
            "model": self.model_id,
            "now": self.world.now,
            "events": [asdict(e) for e in self.world.events],
            "runs": [asdict(r) for r in self.runs],
            "notifications": [asdict(n) for n in self.desk.notifications],
            "incidents": [asdict(i) for i in self.desk.incidents],
            "approvals": [asdict(a) for a in self.world.approvals],
            "schedules": [asdict(s) for s in self.cron.schedules.values()],
            "metrics": list(self.world.metrics),
            "memory": list(self.memory.notes),
        }

    def shift_log_json(self) -> str:
        return json.dumps(
            self.shift_log(),
            default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o),
            ensure_ascii=False,
            indent=1,
        )

    # ---- human actions from the UI -------------------------------------------------
    def decide(self, approval_id: str, approved: bool) -> None:
        a = self.world.decide(approval_id, approved, by="you")
        self.emit("decision", a)

    def inject(self, what: str) -> None:
        before = len(self.world.events)
        self.world.inject(what)
        for ev in self.world.events[before:]:
            self.emit("event", ev)

    # ---- background loop for the UI ----------------------------------------------------
    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.error = None
        self.last_seen = time.time()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pause(self) -> None:
        self.running = False

    def heartbeat(self) -> None:
        self.last_seen = time.time()

    def _loop(self) -> None:
        while self.running:
            if time.time() - self.last_seen > IDLE_PAUSE_SECONDS:
                self.running = False  # nobody is watching: stop spending tokens
                break
            t0 = time.time()
            try:
                self.step()
            except Exception as e:
                self.error = f"{type(e).__name__}: {e}"
                self.running = False
                break
            time.sleep(max(0.0, self.speed - (time.time() - t0)))
