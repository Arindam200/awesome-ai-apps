"""Watch the agent handle one situation live.

    uv run run_demo.py            # list the scenarios
    uv run run_demo.py S1         # API renamed its pricing fields
    uv run run_demo.py S8         # two tools broken in one task
"""
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")

from rich.console import Console  # noqa: E402

from healing.run import run_scenario  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402


def main():
    by_id = {s["id"]: s for s in SCENARIOS}
    if len(sys.argv) < 2 or sys.argv[1].upper() not in by_id:
        console = Console()
        for s in SCENARIOS:
            console.print(f"  [bold]{s['id']}[/bold]  {s['name']}")
        console.print("\nusage: uv run run_demo.py <id>")
        return
    s = by_id[sys.argv[1].upper()]
    run_dir = Path("runs") / f"demo_{s['id']}_{datetime.now():%Y%m%d_%H%M%S}"
    summary = run_scenario(s, run_dir)
    verdict = "PASS" if summary["passed"] else "FAIL"
    Console().print(f"\n[bold]{verdict}[/bold]  {summary['note']}  |  events: {run_dir / 'events.jsonl'}")


if __name__ == "__main__":
    main()
