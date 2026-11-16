"""The world the agent watches: a simulated checkout service for a small online store.

There is no LLM in here. It is a seeded simulation of one on-call morning: a bad
deploy, a database disk slowly filling up, team chatter, a customer ticket, a
fix-forward. You can inject more trouble from the UI. Metrics follow what actually
happens rather than a fixed script: a bad version pushes the error rate up, an
approved rollback brings it back down, and a payments-provider outage hurts
checkout whatever version is running. So what the agent does changes what it sees
next.
"""

from __future__ import annotations

import math
import random
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable

BASELINE_ERR = 0.3  # checkout-api 5xx %, 7-day baseline
BASELINE_P95 = 205  # ms

SERVICES = {
    "checkout-api": "customer checkout and card payments. Owned by this team",
    "orders-db": "Postgres primary behind checkout. Owned by this team",
    "search-api": "product search. Owned by another team",
    "payments-provider": "external card processor. Not ours: you only see its status page",
}


@dataclass
class Event:
    id: int
    at: datetime
    kind: str  # deploy | rollback | alert | chat | ticket | status | approval
    source: str
    text: str
    service: str | None = None
    severity: str = "info"  # info | warning | critical

    def line(self) -> str:
        sev = f"/{self.severity}" if self.kind == "alert" else ""
        svc = f" {self.service}" if self.service else ""
        return f"[{self.at:%H:%M}] {self.kind}{sev}{svc} ({self.source}): {self.text}"


@dataclass
class Deploy:
    version: str
    at: datetime
    author: str
    message: str
    bad: bool = False
    rollback: bool = False


@dataclass
class Approval:
    id: str
    service: str
    from_version: str
    to_version: str
    reason: str
    requested_at: datetime
    requested_by: str  # run id
    status: str = "pending"  # pending | approved | denied
    decided_at: datetime | None = None
    decided_by: str = ""

    def describe(self) -> str:
        head = f"{self.id}: roll back {self.service} {self.from_version} -> {self.to_version}"
        if self.status == "pending":
            return f"{head}, pending since {self.requested_at:%H:%M}"
        return f"{head}, {self.status} at {self.decided_at:%H:%M} by {self.decided_by}"


TICKETS = [
    "Order #51877: checkout spinner never finished, then said 'payment failed'. Tried twice.",
    "Order #50342: got charged but no confirmation email. Is my order placed?",
    "Order #49920: the discount code SPRING10 isn't applying at checkout.",
]
CHATTER = [
    ("#general", "priya", "Anyone know if the coffee machine on 3 got fixed? ☕"),
    ("#checkout-eng", "sam", "PR for the new address form is up, reviews welcome when you have a sec."),
    ("#random", "dev", "Friendly reminder that the parking garage closes early today."),
]


def _scripted_morning() -> dict[int, list[Callable[[World], None]]]:
    """What happens at each minute of the shift, as offsets from 09:00."""
    return {
        2: [
            lambda w: w.chat(
                "#general", "priya", "Reminder: design review moved to 11:00. Bring questions (and snacks)."
            )
        ],
        4: [lambda w: w.deploy("search-api", "v3.2.1", "ci-bot", "Tweak synonym ranking for 'oat milk'")],
        8: [
            lambda w: w.chat(
                "#checkout-eng",
                "maya",
                "Shipping the new payment retry policy after standup. Should cut false declines.",
            )
        ],
        12: [
            lambda w: w.deploy(
                "checkout-api",
                "v2.14.0",
                "maya",
                "Payment client: new retry policy (5 retries, exponential backoff)",
                bad=True,
            )
        ],
        16: [lambda w: w.status("All systems operational.")],
        17: [
            lambda w: w.ticket(
                "Order #48213: card was declined at checkout, but my bank shows a pending charge. Was I charged twice?"
            )
        ],
        21: [
            lambda w: w.chat(
                "#checkout-eng",
                "maya",
                "Is checkout slow for anyone else? Looking into it."
                if w.current("checkout-api").bad
                else "Saw the rollback of v2.14.0, sorry all. Digging into the retry change, fix coming.",
            )
        ],
        26: [
            lambda w: w.alert(
                "checkout-api", "info", "Pod checkout-api-7f9c restarted once (OOMKilled). Replacement is healthy."
            )
        ],
        30: [
            lambda w: w.chat(
                "#ops",
                "dev",
                "Found the orders-db disk growth: debug logging was left on after last "
                "night's migration. Turned it off and rotated the logs.",
            )
        ],
        31: [lambda w: w.fix_disk()],
        35: [lambda w: w.deploy("checkout-api", "v2.14.1", "maya", "Retry policy fix: cap retries at 2, 1.5s timeout")],
        38: [lambda w: w.chat("#general", "priya", "Lunch order closes at 11:30 🌯")],
    }


class World:
    def __init__(self, start: datetime, seed: int = 7):
        self.start = start
        self.now = start
        self.lock = threading.RLock()
        self._rng = random.Random(seed)
        self._script = _scripted_morning()
        self.events: list[Event] = []
        self.read_upto = 0  # events[:read_upto] were handled by a finished triage run
        self.approvals: list[Approval] = []
        self._later: list[tuple[datetime, Callable[[], None]]] = []
        self.deploys: dict[str, list[Deploy]] = {
            "checkout-api": [
                Deploy("v2.13.1", start - timedelta(days=6, hours=3), "sam", "Gift card balance check at checkout"),
                Deploy("v2.13.2", start - timedelta(days=2, hours=5), "maya", "Fix rounding on multi-currency totals"),
            ],
            "search-api": [Deploy("v3.2.0", start - timedelta(days=3), "ci-bot", "Index refresh job tuning")],
        }
        self.metrics: list[dict] = []
        self._err = BASELINE_ERR
        self._disk = 68.4
        self._debug_logging = True  # the slow disk leak a teammate fixes at 09:30
        self._provider_down_until: datetime | None = None
        self._open_alerts: set[str] = set()
        self._err_high = 0
        self._err_ok = 0
        self._sample()

    @property
    def minute(self) -> int:
        return int((self.now - self.start).total_seconds() // 60)

    # ---- clock ------------------------------------------------------------
    def advance(self) -> list[Event]:
        """Move the clock one minute forward and return the events it produced."""
        with self.lock:
            before = len(self.events)
            self.now += timedelta(minutes=1)
            for item in [x for x in self._later if x[0] <= self.now]:
                self._later.remove(item)
                item[1]()
            for action in self._script.get(self.minute, []):
                action(self)
            if self._provider_down_until and self.now >= self._provider_down_until:
                self._provider_down_until = None
                self.status("Resolved: card authorizations are back to normal. All systems operational.")
            self._sample()
            self._monitor()
            return self.events[before:]

    # ---- event helpers ----------------------------------------------------
    def emit(self, kind: str, source: str, text: str, service: str | None = None, severity: str = "info") -> Event:
        with self.lock:
            ev = Event(len(self.events) + 1, self.now, kind, source, text, service, severity)
            self.events.append(ev)
            return ev

    def chat(self, channel: str, author: str, text: str) -> None:
        self.emit("chat", channel, f"{author}: {text}")

    def ticket(self, text: str) -> None:
        self.emit("ticket", "support inbox", text)

    def status(self, text: str) -> None:
        self.emit("status", "payments provider status page", text, service="payments-provider")

    def alert(self, service: str, severity: str, text: str) -> None:
        self.emit("alert", "monitoring", text, service=service, severity=severity)

    def deploy(self, service: str, version: str, author: str, message: str, bad: bool = False) -> None:
        self.deploys.setdefault(service, []).append(Deploy(version, self.now, author, message, bad=bad))
        self.emit("deploy", "deploy bot", f"{version} by {author}: {message}", service=service)

    def fix_disk(self) -> None:
        self._debug_logging = False
        self._disk = 58.0

    def current(self, service: str) -> Deploy:
        return self.deploys[service][-1]

    # ---- metrics + monitoring rules ----------------------------------------
    def _sample(self) -> None:
        target = BASELINE_ERR
        if self.current("checkout-api").bad:
            target = 5.4
        if self._provider_down_until:
            target = max(target, 3.8)
        rate = 0.45 if target > self._err else 0.5
        self._err += (target - self._err) * rate
        err = max(0.05, self._err + self._rng.gauss(0, 0.07))
        p95 = BASELINE_P95 + (err - BASELINE_ERR) * 370 + self._rng.gauss(0, 12)
        rps = 140 + 12 * math.sin(self.minute / 7) + self._rng.gauss(0, 3)
        self._disk += (0.48 if self._debug_logging else 0.03) + self._rng.gauss(0, 0.03)
        self.metrics.append(
            {
                "at": self.now,
                "rps": round(rps),
                "error_rate": round(err, 2),
                "p95_ms": round(p95),
                "disk_pct": round(self._disk, 1),
            }
        )

    def _disk_rate(self) -> float:
        window = self.metrics[-11:]
        if len(window) < 2:
            return 0.0
        return (window[-1]["disk_pct"] - window[0]["disk_pct"]) / (len(window) - 1)

    def _monitor(self) -> None:
        m = self.metrics[-1]
        err = m["error_rate"]
        self._err_high = self._err_high + 1 if err > 2.0 else 0
        self._err_ok = self._err_ok + 1 if err < 1.0 else 0
        if self._err_high == 2 and "checkout-5xx" not in self._open_alerts:
            self._open_alerts.add("checkout-5xx")
            self.alert(
                "checkout-api",
                "critical",
                f"5xx rate above 2% for 2 minutes (now {err:.1f}%, baseline {BASELINE_ERR}%).",
            )
        if self._err_ok == 2 and "checkout-5xx" in self._open_alerts:
            self._open_alerts.discard("checkout-5xx")
            self.alert("checkout-api", "info", f"Recovered: 5xx rate back under 1% (now {err:.1f}%).")

        disk, rate = m["disk_pct"], self._disk_rate()
        for threshold, severity in ((70, "warning"), (80, "warning"), (90, "critical")):
            key = f"disk-{threshold}"
            if disk >= threshold and key not in self._open_alerts:
                self._open_alerts.add(key)
                eta = f" Full in about {int((100 - disk) / rate)} min at this rate." if rate > 0.05 else ""
                self.alert(
                    "orders-db",
                    severity,
                    f"Disk usage {disk:.0f}% on orders-db-primary (threshold {threshold}%), "
                    f"growing {rate:+.2f}%/min.{eta}",
                )
            elif disk < threshold - 3:
                self._open_alerts.discard(key)

    # ---- what the agent's tools read ----------------------------------------
    def unread(self) -> list[Event]:
        return self.events[self.read_upto :]

    def mark_read(self, upto: int) -> None:
        self.read_upto = max(self.read_upto, upto)

    def when(self, dt: datetime) -> str:
        return f"{dt:%H:%M}" if dt.date() == self.now.date() else f"{dt:%a %H:%M}"

    def metrics_report(self, service: str, minutes: int) -> str:
        minutes = max(1, min(int(minutes), 60))
        rows = self.metrics[-minutes:]
        if len(rows) > 30:  # keep the table short: every other minute
            rows = rows[::2]
        last = self.metrics[-1]
        if service == "checkout-api":
            cur = self.current(service)
            table = ["time   rps  5xx%  p95ms"] + [
                f"{r['at']:%H:%M}  {r['rps']:>3}  {r['error_rate']:>4.1f}  {r['p95_ms']:>5}" for r in rows
            ]
            head = (
                f"checkout-api now: 5xx {last['error_rate']:.1f}% (baseline {BASELINE_ERR}%), p95 "
                f"{last['p95_ms']}ms (baseline {BASELINE_P95}ms). Running {cur.version}, deployed "
                f"{self.when(cur.at)} by {cur.author}."
            )
            return head + "\n" + "\n".join(table)
        if service == "orders-db":
            rate = self._disk_rate()
            eta = f", full in ~{int((100 - last['disk_pct']) / rate)} min" if rate > 0.05 else ", stable"
            table = ["time   disk%"] + [f"{r['at']:%H:%M}  {r['disk_pct']:.1f}" for r in rows]
            return (
                f"orders-db-primary disk {last['disk_pct']:.1f}%, trend {rate:+.2f}%/min over the last "
                f"10 min{eta}.\n" + "\n".join(table)
            )
        if service == "search-api":
            version = self.current(service).version
            return f"search-api: 5xx 0.1%, p95 95ms, steady for the last {minutes} min. Running {version}."
        if service == "payments-provider":
            return "No metrics for an external provider. Its status page posts show up as `status` events."
        return f"Unknown service {service!r}. Known: {', '.join(SERVICES)}."

    def deploy_history(self, service: str) -> str:
        if service not in self.deploys:
            return f"No deploy history for {service!r}. Services with deploys: {', '.join(self.deploys)}."
        lines = []
        history = self.deploys[service]
        for i, d in enumerate(reversed(history[-6:])):
            tag = " (current)" if i == 0 else ""
            what = "rollback to" if d.rollback else "deploy"
            lines.append(f"{self.when(d.at)} {what} {d.version} by {d.author}: {d.message}{tag}")
        return "\n".join(lines)

    # ---- human-gated actions -------------------------------------------------
    def request_rollback(self, service: str, to_version: str, reason: str, run_id: str) -> Approval:
        with self.lock:
            if service not in self.deploys:
                raise ValueError(
                    f"{service!r} has no deploy history. Services with deploys: {', '.join(self.deploys)}."
                )
            cur = self.current(service)
            if to_version == cur.version:
                raise ValueError(f"{service} is already running {to_version}.")
            if not any(d.version == to_version for d in self.deploys[service]):
                raise ValueError(f"{to_version} was never deployed to {service}. See get_deploy_history.")
            for a in self.approvals:
                if a.status == "pending" and a.service == service:
                    raise ValueError(f"{a.id} for {service} is already waiting for the human. Don't ask twice.")
            approval = Approval(
                f"APR-{len(self.approvals) + 1}", service, cur.version, to_version, reason, self.now, run_id
            )
            self.approvals.append(approval)
            return approval

    def decide(self, approval_id: str, approved: bool, by: str) -> Approval:
        with self.lock:
            a = next(x for x in self.approvals if x.id == approval_id)
            if a.status != "pending":
                return a
            a.status = "approved" if approved else "denied"
            a.decided_at, a.decided_by = self.now, by
            verb = "approved" if approved else "denied"
            self.emit(
                "approval",
                "on-call phone",
                f"{by} {verb} {a.id}: roll back {a.service} {a.from_version} -> {a.to_version}.",
                service=a.service,
            )
            if approved:
                self._later.append((self.now + timedelta(minutes=1), lambda: self._rollback(a)))
            return a

    def auto_decide(self, after_minutes: int) -> list[Approval]:
        """Stand-in for the human: approve requests that waited `after_minutes`."""
        due = [
            a
            for a in self.approvals
            if a.status == "pending" and self.now - a.requested_at >= timedelta(minutes=after_minutes)
        ]
        return [self.decide(a.id, True, by="on-call (simulated)") for a in due]

    def _rollback(self, a: Approval) -> None:
        target = next(d for d in reversed(self.deploys[a.service]) if d.version == a.to_version)
        self.deploys[a.service].append(
            Deploy(
                a.to_version,
                self.now,
                "deploy bot",
                f"Rollback from {a.from_version} ({a.id})",
                bad=target.bad,
                rollback=True,
            )
        )
        self.emit(
            "rollback", "deploy bot", f"Rolled back {a.from_version} -> {a.to_version} ({a.id}).", service=a.service
        )

    # ---- trouble you can inject from the UI ------------------------------------
    def inject(self, what: str) -> None:
        with self.lock:
            if what == "bad_deploy":
                major, minor, _ = (int(x) for x in re.findall(r"\d+", self.current("checkout-api").version)[:3])
                self.deploy("checkout-api", f"v{major}.{minor + 1}.0", "jordan", "Bump payments SDK to 9.0", bad=True)
            elif what == "provider_outage":
                self._provider_down_until = self.now + timedelta(minutes=12)
                self.status("Investigating: elevated timeouts on card authorizations in all regions.")
            elif what == "ticket":
                self.ticket(self._rng.choice(TICKETS))
            elif what == "chat":
                self.chat(*self._rng.choice(CHATTER))
            else:
                raise ValueError(f"unknown injection {what!r}")
