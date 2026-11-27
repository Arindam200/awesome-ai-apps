"""Run every scenario N times on the same harness, model and prompt, and score each run.

    uv run run_benchmark.py                 # 1 run per scenario
    uv run run_benchmark.py --trials 3      # the numbers in the README
    uv run run_benchmark.py --only S1 S8    # a subset

A run passes only if the task outcome is right AND the agent took the right action:
it repaired exactly the tools that were broken, and touched nothing else.
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")

from rich.console import Console  # noqa: E402
from rich.table import Table  # noqa: E402

from config import MODEL, PRICE  # noqa: E402
from healing.run import run_scenario  # noqa: E402
from scenarios import SCENARIOS  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=1)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--quiet", action="store_true", help="no live event stream")
    ap.add_argument("--plain", action="store_true", help="baseline: default Deep Agent, no healing layer")
    a = ap.parse_args()

    chosen = [s for s in SCENARIOS if not a.only or s["id"] in {x.upper() for x in a.only}]
    out_dir = Path("runs") / f"{'plain' if a.plain else 'bench'}_{datetime.now():%Y%m%d_%H%M%S}"
    console = Console(highlight=False)
    results = []
    for s in chosen:
        for trial in range(1, a.trials + 1):
            r = run_scenario(s, out_dir / f"{s['id']}_t{trial}", live=not a.quiet,
                             mode="plain" if a.plain else "healing")
            r["trial"] = trial
            results.append(r)
            mark = "[green]PASS[/green]" if r["passed"] else "[red]FAIL[/red]"
            console.print(f"{mark} {s['id']} t{trial}  {r['seconds']:.1f}s  ${r['cost_usd']:.4f}  {r['note']}")

    table = Table(title=f"{'PLAIN Deep Agent (no healing)' if a.plain else 'Self-healing agent'}: "
                        f"{MODEL}, {a.trials} run(s) per scenario")
    for col in ("Scenario", "Passed", "Right action", "First-try fix", "Avg time", "Avg cost"):
        table.add_column(col)
    for s in chosen:
        rs = [r for r in results if r["scenario"] == s["id"]]
        n = len(rs)
        ft = [r["first_try"] for r in rs if r["first_try"] is not None]
        table.add_row(f"{s['id']} {s['name']}", f"{sum(r['passed'] for r in rs)}/{n}",
                      f"{sum(r['right_action'] for r in rs)}/{n}",
                      f"{sum(ft)}/{len(ft)}" if ft else "n/a",
                      f"{sum(r['seconds'] for r in rs) / n:.1f}s", f"${sum(r['cost_usd'] for r in rs) / n:.4f}")
    console.print(table)

    totals = {k: sum(r["usage"][k] for r in results) for k in ("llm_calls", "input", "cached", "output")}
    summary = {"mode": "plain" if a.plain else "healing", "model": MODEL, "price_per_1m": PRICE, "trials": a.trials, "date": datetime.now().isoformat(),
               "passed": sum(r["passed"] for r in results), "runs": len(results),
               "total_cost_usd": round(sum(r["cost_usd"] for r in results), 6), "tokens": totals,
               "results": results}
    (out_dir / "results.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    console.print(f"{summary['passed']}/{summary['runs']} passed | ${summary['total_cost_usd']:.4f} total | "
                  f"{totals['input']:,} input ({totals['cached']:,} cached), {totals['output']:,} output | "
                  f"{out_dir / 'results.json'}")


if __name__ == "__main__":
    main()
