"""Run the multi-agent orchestrator from the terminal.

uv run main.py "Compare Postgres, SQLite and DuckDB for a solo developer's analytics app"
uv run main.py --max-tasks 4 --revisions 0 --no-tools --out report.md "Your goal"
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from models import FAST_WORKER_MODEL, WORKER_MODEL, catalog, label
from orchestrator import cost_summary, make_settings, run

DEFAULT_GOAL = (
    "Compare Postgres, SQLite, DuckDB and MongoDB for a solo developer building a SaaS analytics "
    "dashboard. Recommend one and explain when to switch."
)

console = Console()


def main() -> None:
    ap = argparse.ArgumentParser(description="Kimi K3.1 Pro orchestrates cheap worker agents on Nebius.")
    ap.add_argument("goal", nargs="?", default=DEFAULT_GOAL)
    ap.add_argument("--worker", default=WORKER_MODEL, help="standard-tier worker and every revision")
    ap.add_argument("--fast-worker", default=FAST_WORKER_MODEL, help="fast-tier worker, first attempt")
    ap.add_argument("--max-tasks", type=int, default=5)
    ap.add_argument("--revisions", type=int, default=1, help="review rounds that may send work back")
    ap.add_argument("--no-tools", action="store_true", help="workers answer without web lookups")
    ap.add_argument("--out", type=Path, help="save the final deliverable as Markdown")
    args = ap.parse_args()

    settings = make_settings(
        worker=args.worker,
        fast_worker=args.fast_worker,
        max_tasks=args.max_tasks,
        max_revisions=args.revisions,
        tools=not args.no_tools,
    )
    pricing = "live Token Factory prices" if catalog() else "fallback prices (catalog unreachable)"
    console.print(
        Panel(
            f"[bold]Goal[/] {args.goal}\n\n"
            f"Orchestrator  [magenta]{label(settings['orchestrator'])}[/]\n"
            f"Workers       [cyan]{label(settings['worker'])}[/] (standard)  "
            f"[green]{label(settings['fast_worker'])}[/] (fast)\n"
            f"Tools {'on' if settings['tools'] else 'off'} · up to {settings['max_tasks']} subtasks · "
            f"{settings['max_revisions']} review round(s) · {pricing}",
            title="Multi-Agent Orchestrator",
            border_style="magenta",
        )
    )

    started, state = time.time(), {}
    with console.status("Kimi is planning...") as status:
        for ev in run(args.goal, settings):
            kind = ev["event"]
            if kind == "plan":
                show_plan(ev["plan"], settings)
                status.update(f"{len(ev['plan']['tasks'])} workers running in parallel...")
            elif kind == "worker_start" and ev["attempt"] > 1:
                console.print(f"  [yellow]↻[/] {ev['task_id']} sent back, retrying on {label(ev['model'])}")
            elif kind == "tool_call":
                arg = next(iter(ev["args"].values()), "")
                console.print(f"  [dim]{ev['task_id']}: {ev['tool']}({str(arg)[:70]!r})[/]")
            elif kind == "worker_done":
                r = ev["result"]
                mark = "[green]✓[/]" if r["status"] == "done" else "[red]✗[/]"
                console.print(
                    f"  {mark} {r['task_id']} · {label(r['model'])} · {r['seconds']}s · "
                    f"{r['tool_calls']} tool calls · ${r['cost']:.4f}"
                )
            elif kind == "reviewing":
                status.update(f"Kimi is reviewing the work (round {ev['round']})...")
            elif kind == "review":
                show_review(ev["review"], ev["revisions"])
                if ev["revisions"]:
                    status.update(f"{len(ev['revisions'])} worker(s) revising...")
            elif kind == "synthesizing":
                status.update("Kimi is writing the final deliverable...")
            elif kind == "done":
                state = ev["state"]

    final = state.get("final", "")
    console.rule("[bold magenta]Final deliverable")
    console.print(Markdown(final or "_No output._"))
    show_costs(state.get("ledger", []), settings["orchestrator"], time.time() - started, state.get("results", {}))
    if args.out:
        args.out.write_text(final)
        console.print(f"\nSaved to {args.out}")


def show_plan(plan: dict, settings: dict) -> None:
    t = Table(title=plan["approach"], title_justify="left", show_lines=False)
    t.add_column("Task", style="bold")
    t.add_column("Tier")
    t.add_column("Worker")
    t.add_column("Brief", overflow="fold", max_width=70)
    for task in plan["tasks"]:
        model = settings["fast_worker"] if task["tier"] == "fast" else settings["worker"]
        t.add_row(task["id"], task["tier"], label(model), task["brief"][:220])
    console.print(t)


def show_review(review: dict, revisions: list) -> None:
    sent_back = {r["task_id"] for r in revisions}
    console.print(f"\n[bold magenta]Review {review['round']}[/] {review['summary']}")
    for v in review["verdicts"]:
        if v["task_id"] in sent_back:
            console.print(f"  [yellow]revise[/] {v['task_id']}: {v['feedback']}")
        else:
            console.print(f"  [green]accept[/] {v['task_id']}")


def show_costs(ledger: list, orchestrator: str, seconds: float, results: dict) -> None:
    c = cost_summary(ledger, orchestrator)
    t = Table(title="Cost ledger", title_justify="left")
    for col in ("Model", "Calls", "Input tokens", "Output tokens", "Cost"):
        t.add_column(col, justify="right" if col != "Model" else "left")
    for model, m in sorted(c["by_model"].items(), key=lambda kv: -kv[1]["cost"]):
        t.add_row(
            label(model), str(m["calls"]), f"{m['input_tokens']:,}", f"{m['output_tokens']:,}", f"${m['cost']:.4f}"
        )
    console.print(t)
    worker_time = sum(r["seconds"] for r in results.values())
    console.print(
        f"Total [bold]${c['total']:.4f}[/] for {c['tokens']:,} tokens in {seconds:.0f}s. "
        f"Workers handled {c['worker_token_share']:.0f}% of the tokens for ${c['worker_cost']:.4f}.\n"
        f"The same tokens all on {label(orchestrator)}: ${c['all_orchestrator_total']:.4f} "
        f"([bold green]{c['savings_pct']:.0f}% saved[/]). "
        f"Final-attempt worker time added up to {worker_time:.0f}s; running them in parallel hid most of it."
    )


if __name__ == "__main__":
    main()
