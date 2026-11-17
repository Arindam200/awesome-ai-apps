"""Offline checks for the cron server, the simulated world and the runtime loop.

No API key or model needed: the agent is replaced with a stub.

    uv run python -m pytest test_offline.py -q     (or)     uv run python test_offline.py
"""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from cron import CronServer, define_schedule
from desk import Desk
from runtime import SCHEDULES_DIR, OnCallRuntime
from world import World

START = datetime(2026, 11, 16, 9, 0)


class StubAgent:
    """Stands in for the LangChain agent: records each wake-up, calls no tools."""

    def __init__(self):
        self.messages: list[str] = []

    def stream(self, inputs, config=None, context=None, stream_mode=None):
        self.messages.append(inputs["messages"][0].content)
        return iter(())


def raises(fn, *args, **kwargs) -> bool:
    try:
        fn(*args, **kwargs)
    except ValueError:
        return True
    return False


def run_until(world: World, hhmm: str) -> None:
    hh, mm = map(int, hhmm.split(":"))
    while world.now < START.replace(hour=hh, minute=mm):
        world.advance()


def test_static_schedules_load_and_fire_on_time():
    cron = CronServer(START)
    cron.load_static(SCHEDULES_DIR)
    assert set(cron.schedules) == {"triage", "shift_handoff"}
    fired = {}
    now = START
    while now <= START.replace(minute=50):
        for s in cron.due(now):
            fired.setdefault(s.id, []).append(f"{now:%H:%M}")
            cron.mark_fired(s, now)
        now += timedelta(minutes=1)
    assert fired["triage"][:3] == ["09:00", "09:05", "09:10"]
    assert fired["shift_handoff"] == ["09:47"]


def test_agent_follow_ups_fire_once_and_keep_their_thread():
    cron = CronServer(START)
    s = cron.create(now=START, at=START + timedelta(minutes=3), prompt="check", thread_id="t-1")
    assert cron.due(START + timedelta(minutes=2)) == []
    assert cron.due(START + timedelta(minutes=3)) == [s]
    cron.mark_fired(s, START + timedelta(minutes=3))
    assert not s.active and s.thread_id == "t-1"
    r = cron.create(now=START, cron="*/10 * * * *", prompt="watch disk")
    assert r.next_run == START + timedelta(minutes=10)
    cron.cancel(r.id, by="run-9")
    assert cron.active(owner="agent") == []


def test_schedule_validation():
    cron = CronServer(START)
    cron.load_static(SCHEDULES_DIR)
    assert raises(cron.create, now=START, prompt="x", cron="* * * *")  # 4 fields
    assert raises(cron.create, now=START, prompt="x", at=START)  # not in the future
    assert raises(cron.create, now=START, prompt="x")  # neither cron nor at
    assert raises(cron.cancel, "triage", by="run-1")  # static schedules live in code
    assert raises(define_schedule, cron="every 5 minutes", prompt="x")


def test_bad_deploy_breaks_checkout_and_rollback_fixes_it():
    w = World(START)
    run_until(w, "09:15")
    assert w.current("checkout-api").version == "v2.14.0"
    assert w.metrics[-1]["error_rate"] > 3.5
    crit = [e for e in w.events if e.kind == "alert" and e.severity == "critical"]
    assert crit and crit[0].at <= START.replace(minute=14)

    assert raises(w.request_rollback, "checkout-api", "v9.9.9", "typo", "run-4")
    a = w.request_rollback("checkout-api", "v2.13.2", "errors after deploy", "run-4")
    assert raises(w.request_rollback, "checkout-api", "v2.13.2", "again", "run-5")  # already pending
    w.decide(a.id, True, by="you")
    run_until(w, "09:22")
    assert w.current("checkout-api").version == "v2.13.2"
    assert w.metrics[-1]["error_rate"] < 1.0
    assert any(e.kind == "alert" and e.text.startswith("Recovered") for e in w.events)


def test_disk_story_and_provider_outage():
    w = World(START)
    run_until(w, "09:26")
    disk_alerts = [e for e in w.events if e.service == "orders-db" and e.kind == "alert"]
    minutes = [e.at.minute for e in disk_alerts]  # crosses 70%, then 80%
    assert len(minutes) == 2 and minutes[0] <= 5 and 20 <= minutes[1] <= 25, minutes
    run_until(w, "09:32")
    assert w.metrics[-1]["disk_pct"] < 60

    w2 = World(START)
    w2.inject("provider_outage")
    run_until(w2, "09:06")
    assert w2.metrics[-1]["error_rate"] > 2.5  # hurts checkout whatever version runs


def test_one_open_incident_per_service():
    desk = Desk()
    inc = desk.open_incident(START, "orders-db", "disk filling", "sev3", "71%", "run-2")
    assert raises(desk.open_incident, START, "orders-db", "disk filling again", "sev3", "77%", "run-5")
    desk.open_incident(START, "checkout-api", "5xx spike", "sev1", "5%", "run-4")  # other services are fine
    desk.resolve_incident(START, inc.id, "logs rotated")
    desk.open_incident(START, "orders-db", "disk again", "sev3", "85%", "run-9")  # allowed once resolved


def test_runtime_skips_quiet_triage_and_marks_events_read():
    stub = StubAgent()
    with tempfile.TemporaryDirectory() as tmp:
        rt = OnCallRuntime(start=START, agent=stub, memory_path=Path(tmp) / "memory.md")
        rt.fire(rt.cron.schedules["triage"])  # 09:00, nothing has happened yet
        assert rt.runs[-1].status == "skipped" and stub.messages == []
        while rt.world.now < START.replace(minute=5):
            rt.step()
        assert rt.runs[-1].status == "done" and rt.world.unread() == []
        assert "Schedule `triage`" in stub.messages[-1]


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
