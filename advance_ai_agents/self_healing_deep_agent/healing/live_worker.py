"""Run one scenario and print its events as JSON lines, for the web page.

    python -m healing.live_worker S1 healing
    python -m healing.live_worker S1 plain

app.py starts this in its own process for every run, so the plain and the self-healing
agent never share state (Deep Agents settings, loaded tool modules)."""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
sys.stdout.reconfigure(encoding="utf-8")

PREFIX = "EVENT "   # anything else printed by libraries is ignored by app.py


def main(scenario_id: str, mode: str):
    from healing.run import run_scenario
    from scenarios import SCENARIOS

    scenario = next(s for s in SCENARIOS if s["id"] == scenario_id)
    run_dir = Path("runs") / f"live_{scenario_id}_{mode}_{datetime.now():%Y%m%d_%H%M%S}"
    send = lambda e: print(PREFIX + json.dumps(e, ensure_ascii=False, default=str), flush=True)  # noqa: E731
    summary = run_scenario(scenario, run_dir, live=False, mode=mode, on_event=send)
    send({"t": summary["seconds"], "type": "summary", "passed": summary["passed"], "note": summary["note"],
          "mode": mode, "events_file": str(run_dir / "events.jsonl")})


if __name__ == "__main__":
    main(sys.argv[1].upper(), sys.argv[2] if len(sys.argv) > 2 else "healing")
