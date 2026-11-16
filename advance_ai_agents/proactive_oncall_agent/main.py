"""Run one on-call shift in the terminal and watch the agent work without being asked.

python main.py                   # 09:00-09:48 shift, rollbacks auto-approved after 2 min
python main.py --approve ask     # you approve or deny rollbacks yourself
python main.py --approve never   # nobody answers the phone: watch it escalate
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime

from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

load_dotenv()

from agent import RunRecord, Step  # noqa: E402
from desk import LEVEL_ICON, Notification  # noqa: E402
from runtime import OnCallRuntime  # noqa: E402
from world import Approval, Event  # noqa: E402

console = Console(highlight=False)

EVENT_ICON = {"deploy": "🚀", "rollback": "⏪", "chat": "💬", "ticket": "🎫", "status": "🌐", "approval": "📱"}
ALERT_ICON = {"critical": "🔥", "warning": "⚠️ ", "info": "ℹ️ "}
LEVEL_STYLE = {"page": "bold red", "warn": "yellow", "fyi": "cyan"}


def fmt_args(args: dict) -> str:
    parts = []
    for k, v in args.items():
        s = repr(v)
        parts.append(f"{k}={s if len(s) <= 60 else s[:57] + '...'}")
    return ", ".join(parts)


def on_event(kind: str, obj: object) -> None:
    if kind == "event" and isinstance(obj, Event):
        icon = ALERT_ICON.get(obj.severity, "") if obj.kind == "alert" else EVENT_ICON.get(obj.kind, "•")
        svc = f"[bold]{obj.service}[/] " if obj.service else ""
        console.print(f"[dim]{obj.at:%H:%M}[/] {icon} [dim]{obj.kind:<8}[/] {svc}{obj.text}", soft_wrap=True)
    elif kind == "run_start" and isinstance(obj, RunRecord):
        why = {
            "static": f"schedule [bold]{obj.schedule_id}[/]",
            "follow-up": f"its own follow-up [bold]{obj.schedule_id}[/]",
            "recurring": f"its own recurring watch [bold]{obj.schedule_id}[/]",
        }[obj.kind]
        console.rule(f"[bold magenta]⏰ {obj.at:%H:%M} agent woken by {why}[/]", style="magenta")
    elif kind == "tool" and isinstance(obj, Step):
        console.print(f"   [magenta]→ {obj.tool}[/]([dim]{fmt_args(obj.args)}[/])", soft_wrap=True)
    elif kind == "result" and isinstance(obj, Step):
        first = obj.result.strip().splitlines()[0] if obj.result.strip() else ""
        console.print(f"     [dim]↳ {obj.tool}: {first[:130]}[/]", soft_wrap=True)
    elif kind == "notify" and isinstance(obj, Notification):
        console.print(
            Panel(
                obj.message,
                title=f"{LEVEL_ICON[obj.level]} {obj.level.upper()}: {obj.title}",
                title_align="left",
                border_style=LEVEL_STYLE[obj.level],
                width=100,
            )
        )
    elif kind == "decision" and isinstance(obj, Approval):
        mark = "✅" if obj.status == "approved" else "❌"
        console.print(f"[dim]{obj.decided_at:%H:%M}[/] {mark} {obj.decided_by} {obj.status} {obj.id}")
    elif kind == "run_end" and isinstance(obj, RunRecord):
        if obj.status == "skipped":
            console.print(f"[dim]{obj.at:%H:%M} 💤 {obj.schedule_id}: nothing new, agent stayed asleep[/]")
        else:
            style = "red" if obj.status == "error" else "green"
            console.print(f"   [{style}]✎ {obj.summary}[/]", soft_wrap=True)
            console.print(f"   [dim]{obj.seconds:.1f}s · {len(obj.steps)} tool calls · {obj.tokens:,} tokens[/]")


def summary(rt: OnCallRuntime) -> None:
    runs = [r for r in rt.runs if r.status != "skipped"]
    skipped = len(rt.runs) - len(runs)
    by_kind: dict[str, int] = {}
    for r in runs:
        by_kind[r.kind] = by_kind.get(r.kind, 0) + 1
    levels = {lvl: sum(n.level == lvl for n in rt.desk.notifications) for lvl in ("page", "warn", "fyi")}

    t = Table(title="Shift summary", show_header=False, title_style="bold")
    t.add_row("Events in the stream", str(len(rt.world.events)))
    t.add_row(
        "Times the agent woke up",
        f"{len(runs)} ({', '.join(f'{v} {k}' for k, v in by_kind.items())}), "
        f"plus {skipped} skipped triages with no model call",
    )
    t.add_row("Messages to the human", ", ".join(f"{v} {k}" for k, v in levels.items()))
    t.add_row("Self-scheduled wake-ups", str(sum(1 for s in rt.cron.schedules.values() if s.owner == "agent")))
    t.add_row("Tokens", f"{sum(r.tokens for r in runs):,}")
    for inc in rt.desk.incidents:
        t.add_row(inc.id, inc.describe())
    for a in rt.world.approvals:
        t.add_row(a.id, a.describe())
    console.print(t)
    if rt.memory.notes:
        console.print(
            Panel(
                "\n".join(f"• {n}" for n in rt.memory.notes), title="🧠 Long-term memory", title_align="left", width=100
            )
        )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--until", default="09:48", help="stop at this simulated time (HH:MM). Default 09:48")
    p.add_argument(
        "--approve",
        choices=["auto", "ask", "never"],
        default="auto",
        help="who answers rollback requests. Default: a simulated human after --approve-after min",
    )
    p.add_argument("--approve-after", type=int, default=2, help="minutes before the simulated human approves")
    p.add_argument("--speed", type=float, default=0.15, help="real seconds per quiet simulated minute")
    p.add_argument("--fresh-memory", action="store_true", help="forget long-term memory from earlier shifts")
    p.add_argument("--model", default=None, help="Nebius model id. Default: moonshotai/Kimi-K3.1-Pro")
    args = p.parse_args()

    if args.approve == "ask" and not sys.stdin.isatty():
        p.error("--approve ask needs an interactive terminal")

    rt = OnCallRuntime(auto_approve_after=args.approve_after if args.approve == "auto" else None, model=args.model)
    if args.fresh_memory:
        rt.memory.clear()
    rt.listeners.append(on_event)
    hh, mm = (int(x) for x in args.until.split(":"))
    end = rt.world.start.replace(hour=hh, minute=mm)

    console.print(
        Panel(
            "Nobody will type anything. A cron server wakes the agent every 5 minutes to triage the event stream, "
            "and the agent schedules its own follow-ups. Rollbacks need a human's approval.\n"
            f"[dim]Model: {rt.model_id} on Nebius Token Factory · simulated shift "
            f"{rt.world.start:%H:%M}-{end:%H:%M} · long-term memory: {len(rt.memory.notes)} notes[/]",
            title="⏰ Proactive on-call agent",
            title_align="left",
            border_style="magenta",
            width=100,
        )
    )

    asked: set[str] = set()
    try:
        while rt.world.now < end:
            t0 = time.time()
            rt.step()
            if args.approve == "ask":
                for a in rt.world.approvals:
                    if a.status == "pending" and a.id not in asked:
                        asked.add(a.id)
                        ok = Confirm.ask(
                            f"📱 {a.id}: roll back {a.service} {a.from_version} -> {a.to_version}? Reason: {a.reason}",
                            default=True,
                        )
                        rt.decide(a.id, ok)
            time.sleep(max(0.0, args.speed - (time.time() - t0)))
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/]")
    summary(rt)


if __name__ == "__main__":
    started = datetime.now()
    main()
    console.print(f"[dim]Wall time {datetime.now() - started}.[/]")
