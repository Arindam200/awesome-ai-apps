"""Run one scenario end to end and score it. Used by run_demo.py and run_benchmark.py."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from langchain_core.messages import AIMessage

from config import FAILURES_DIR, MODEL, ROOT, TOOLS_DIR
from healing.healer import Healer
from healing.recorder import ModelEvents, Recorder
from provider_api.server import FAULTS, start_server
from scenarios import REPORT, TASK, check_report

_API: dict = {}


def api_url() -> str:
    if not _API:
        server, url = start_server()
        _API.update(server=server, url=url)
        os.environ["PROVIDER_API_URL"] = url
    return _API["url"]


def reset_workspace(scenario: dict):
    """Fresh tools (working versions, then the scenario's broken ones), no old outputs."""
    for f in (ROOT / "scenarios" / "working").glob("*.py"):
        shutil.copy(f, TOOLS_DIR / f.name)    # copy, not copy2: fresh mtime, so no stale .pyc
    for name in scenario["broken"]:
        shutil.copy(ROOT / "scenarios" / "broken" / f"{name}.py", TOOLS_DIR / f"{name}.py")
    for d in (FAILURES_DIR, ROOT / "data", ROOT / "reports", TOOLS_DIR / "__pycache__"):
        shutil.rmtree(d, ignore_errors=True)
    for bak in TOOLS_DIR.glob("*.bak"):
        bak.unlink()
    FAULTS.reset(**scenario["faults"])


def run_scenario(scenario: dict, run_dir: Path, live: bool = True, mode: str = "healing", on_event=None) -> dict:
    """mode="healing": our agent. mode="plain": a default Deep Agent with no healing layer."""
    url = api_url()
    reset_workspace(scenario)
    os.chdir(ROOT)
    run_dir.mkdir(parents=True, exist_ok=True)
    before = {f.name: f.read_text(encoding="utf-8") for f in TOOLS_DIR.glob("*.py")}

    rec = Recorder(run_dir / "events.jsonl", live=live, on_event=on_event)
    healer = Healer(rec, url)
    if mode == "plain":
        from healing.plain import build_plain_agent   # never import healing.agent in this mode
        agent = build_plain_agent(rec)
    else:
        from healing.agent import build_agent
        agent = build_agent(healer)
    rec.t0 = __import__("time").perf_counter()   # clock starts with the task, not the build
    rec.emit("run_start", scenario=f"{scenario['id']}  {scenario['name']}", task=TASK, model=MODEL,
             broken=scenario["broken"], faults=scenario["faults"], mode=mode)

    error = None
    answer = ""
    try:
        state = agent.invoke({"messages": [{"role": "user", "content": TASK}]},
                             config={"callbacks": [ModelEvents(rec)], "recursion_limit": 60})
        answer = next((m.content for m in reversed(state["messages"])
                       if isinstance(m, AIMessage) and m.content), "")
    except Exception as exc:  # a crash of the harness itself is a failed run, not a skipped one
        error = f"{type(exc).__name__}: {exc}"
    rec.emit("final", answer=answer or f"(no answer: {error})")

    # ---- score: did it do the right thing, and only that?
    changed = sorted(n.removesuffix(".py") for n, src in before.items()
                     if (TOOLS_DIR / n).read_text(encoding="utf-8") != src)
    repaired_ok = sorted(e["tool"] for e in rec.events if e["type"] == "verified")
    attempts = [e for e in rec.events if e["type"] == "repair"]
    report_ok, report_note = check_report(ROOT)
    if scenario["expect"] == "report":
        task_ok = report_ok
    else:   # must stop: no report, and the answer must point at the key
        task_ok = not (ROOT / REPORT).exists() and "key" in answer.lower()
        report_note = "stopped without a report" if task_ok else report_note
    right_action = sorted(scenario["repairs"]) == repaired_ok == changed
    first_try = len(attempts) == len(scenario["repairs"]) == len(repaired_ok)

    u = rec.usage()
    summary = {
        "scenario": scenario["id"], "name": scenario["name"], "mode": mode, "passed": bool(task_ok and right_action and not error),
        "task_ok": task_ok, "right_action": right_action, "first_try": first_try if scenario["repairs"] else None,
        "note": report_note, "repairs_expected": scenario["repairs"], "repaired": repaired_ok,
        "files_changed": changed, "repair_attempts": len(attempts),
        "kinds_seen": sorted({e["kind"] for e in rec.events if e["type"] == "tool_error"}),
        "retries": sum(1 for e in rec.events if e["type"] == "retry"),
        "seconds": rec.elapsed(), "model_seconds": round(sum(e["seconds"] for e in rec.events
                                                            if e["type"] == "llm_end"), 2),
        "local_check_seconds": round(healer.local_check_seconds, 2),
        "usage": u, "cost_usd": rec.cost(), "error": error, "answer": answer,
        "diffs": [e["diff"] for e in rec.events if e["type"] == "patch"],
    }
    rec.emit("run_end", usage=u, cost_usd=rec.cost(), seconds=rec.elapsed(), passed=summary["passed"])
    rec.close()
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    reset_workspace({"broken": [], "faults": {}})
    return summary
