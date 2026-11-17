"""A small in-process cron server, shaped like Managed Deep Agents schedules.

LangChain's proactive agents boil down to "agent runs as cron tasks". This module
is that cron server. It holds two kinds of schedules, as Managed Deep Agents does:

- static schedules, declared one per file in `schedules/` with `define_schedule()`
- runtime schedules, created by the agent itself through tools: a cron expression
  for recurring work, or an `at` time for a one-off follow-up

The caller passes the current time in, so the server runs the same way on the
simulated clock of the demo as it would on the wall clock.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from croniter import croniter

MAX_AGENT_SCHEDULES = 20  # same default limit as Managed Deep Agents


@dataclass(frozen=True)
class ScheduleSpec:
    cron: str
    prompt: str
    metadata: dict = field(default_factory=dict)


def define_schedule(*, cron: str, prompt: str, metadata: dict | None = None) -> ScheduleSpec:
    """Declare a static schedule. Same shape as `managed_deepagents.define_schedule`."""
    _check_cron(cron)
    return ScheduleSpec(cron=cron, prompt=prompt, metadata=metadata or {})


def _check_cron(cron: str) -> None:
    if len(cron.split()) != 5 or not croniter.is_valid(cron):
        raise ValueError(f"cron must be a standard 5-field expression, got {cron!r}")


@dataclass
class Schedule:
    id: str
    prompt: str
    owner: str  # "static" (schedules/ folder) or "agent" (created at runtime)
    cron: str | None = None  # recurring
    at: datetime | None = None  # one-time
    thread_id: str | None = None  # None: every run starts a fresh thread
    created_at: datetime | None = None
    created_by: str | None = None  # id of the run that created it
    metadata: dict = field(default_factory=dict)
    next_run: datetime | None = None
    last_run: datetime | None = None
    runs: int = 0
    active: bool = True
    ended: str = ""  # why it stopped: "fired", "cancelled by run-7", ...

    @property
    def kind(self) -> str:
        if self.owner == "static":
            return "static"
        return "recurring" if self.cron else "follow-up"

    @property
    def when(self) -> str:
        return self.cron if self.cron else f"once at {self.at:%H:%M}"

    def describe(self) -> str:
        nxt = f", next {self.next_run:%H:%M}" if self.active and self.next_run else ""
        state = "" if self.active else f" [{self.ended}]"
        return f"{self.id} ({self.kind}, {self.when}{nxt}){state}: {self.prompt}"


class CronServer:
    def __init__(self, now: datetime):
        self.schedules: dict[str, Schedule] = {}
        self._seq = 0
        self._start = now

    # ---- static schedules -------------------------------------------------
    def load_static(self, folder: Path) -> None:
        """Import every schedules/*.py file. The file name is the schedule name."""
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            spec_obj = importlib.util.spec_from_file_location(f"schedules.{path.stem}", path)
            if spec_obj is None or spec_obj.loader is None:
                raise ImportError(f"can't load {path}")
            module = importlib.util.module_from_spec(spec_obj)
            spec_obj.loader.exec_module(module)
            spec = getattr(module, "schedule", None)
            if not isinstance(spec, ScheduleSpec):
                raise ValueError(f"{path} must define a top-level `schedule = define_schedule(...)`")
            self.schedules[path.stem] = Schedule(
                id=path.stem,
                prompt=spec.prompt,
                owner="static",
                cron=spec.cron,
                metadata=dict(spec.metadata),
                created_at=self._start,
                # First run at or after the start time.
                next_run=croniter(spec.cron, self._start - timedelta(seconds=1)).get_next(datetime),
            )

    # ---- runtime schedules (what the agent's tools call) ------------------
    def create(
        self,
        *,
        now: datetime,
        prompt: str,
        cron: str | None = None,
        at: datetime | None = None,
        thread_id: str | None = None,
        created_by: str | None = None,
    ) -> Schedule:
        if (cron is None) == (at is None):
            raise ValueError("give exactly one of cron and at")
        if len(self.active(owner="agent")) >= MAX_AGENT_SCHEDULES:
            raise ValueError("Schedule limit reached. Cancel a schedule first.")
        if cron is not None:
            _check_cron(cron)
            next_run = croniter(cron, now).get_next(datetime)
        else:
            assert at is not None
            at = at.replace(second=0, microsecond=0)
            if at < now + timedelta(minutes=1):
                raise ValueError("`at` must be at least one minute in the future")
            if at > now + timedelta(days=365):
                raise ValueError("`at` must be at most 365 days in the future")
            next_run = at
        self._seq += 1
        sid = f"{'every' if cron else 'once'}-{self._seq}"
        sch = Schedule(
            id=sid,
            prompt=prompt,
            owner="agent",
            cron=cron,
            at=at,
            thread_id=thread_id,
            created_at=now,
            created_by=created_by,
            next_run=next_run,
        )
        self.schedules[sid] = sch
        return sch

    def cancel(self, schedule_id: str, *, by: str) -> Schedule:
        sch = self.schedules.get(schedule_id)
        if sch is None:
            raise ValueError(f"no schedule {schedule_id!r}")
        if sch.owner == "static":
            raise ValueError(f"{schedule_id!r} is declared in schedules/ and can only be changed in code")
        if not sch.active:
            raise ValueError(f"{schedule_id!r} already ended ({sch.ended})")
        sch.active = False
        sch.ended = f"cancelled by {by}"
        return sch

    # ---- the clock side ---------------------------------------------------
    def due(self, now: datetime) -> list[Schedule]:
        """Schedules whose next run is at or before `now`.

        Follow-ups go first: they belong to ongoing work, and triage that runs
        after them sees the incident state they left behind.
        """
        due = [s for s in self.schedules.values() if s.active and s.next_run and s.next_run <= now]
        order = {"follow-up": 0, "recurring": 1, "static": 2}
        return sorted(due, key=lambda s: (order[s.kind], s.next_run, s.id))

    def mark_fired(self, sch: Schedule, now: datetime) -> None:
        sch.last_run = now
        sch.runs += 1
        if sch.cron:
            sch.next_run = croniter(sch.cron, now).get_next(datetime)
        else:
            sch.active = False
            sch.ended = "fired"
            sch.next_run = None

    def active(self, owner: str | None = None) -> list[Schedule]:
        return [s for s in self.schedules.values() if s.active and (owner is None or s.owner == owner)]

    def upcoming(self, limit: int = 5) -> list[Schedule]:
        return sorted(self.active(), key=lambda s: s.next_run or datetime.max)[:limit]
