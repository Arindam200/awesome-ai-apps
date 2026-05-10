"""
dashboard.py — Live dashboard for the Nebius AutoResearch agent.

Serves a web UI showing score progression, experiment history, current
solve.py, and live run logs. Supports starting/stopping the agent.

Usage:
    python dashboard.py
    # Open http://localhost:5000 in your browser
"""

import os
import sys
import subprocess
import threading
import signal
import json
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
RESULTS_TSV     = os.path.join(BASE_DIR, "results.tsv")
SOLVE_PY        = os.path.join(BASE_DIR, "solve.py")
RUN_LOG         = os.path.join(BASE_DIR, "run.log")
AGENT_SCRIPT    = os.path.join(BASE_DIR, "nebius_agent.py")

# Global agent process handle
_agent_proc: subprocess.Popen | None = None
_agent_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _read_file(path: str, fallback: str = "") -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except FileNotFoundError:
        return fallback


def _parse_results() -> list[dict]:
    content = _read_file(RESULTS_TSV)
    if not content.strip():
        return []
    rows = []
    for line in content.strip().splitlines()[1:]:  # skip header
        parts = line.split("\t", 4)
        if len(parts) == 5:
            rows.append({
                "commit":          parts[0],
                "score":           float(parts[1]),
                "processing_time": float(parts[2]),
                "status":          parts[3],
                "description":     parts[4],
            })
    return rows


def _best_score(rows: list[dict]) -> float:
    valid = [r["score"] for r in rows if r["score"] > 0]
    return max(valid) if valid else 0.0


def _baseline(rows: list[dict]) -> dict | None:
    for r in rows:
        if "baseline" in r["description"].lower():
            return r
    return rows[0] if rows else None


# ─────────────────────────────────────────────────────────────────────────────
# API routes
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/results")
def api_results():
    rows = _parse_results()
    baseline = _baseline(rows)
    best     = _best_score(rows)
    speedup  = round(best / baseline["score"], 2) if baseline and baseline["score"] > 0 and best > 0 else 1.0
    return jsonify({
        "rows":    rows,
        "best":    best,
        "baseline": baseline["score"] if baseline else 0.0,
        "speedup": speedup,
        "total":   len(rows),
        "kept":    sum(1 for r in rows if r["status"] == "keep"),
        "crashed": sum(1 for r in rows if r["status"] == "crash"),
        "discarded": sum(1 for r in rows if r["status"] == "discard"),
    })


@app.route("/api/code")
def api_code():
    return jsonify({"code": _read_file(SOLVE_PY, "# solve.py not found")})


@app.route("/api/log")
def api_log():
    content = _read_file(RUN_LOG, "")
    # Return last 60 lines
    lines = content.splitlines()[-60:]
    return jsonify({"log": "\n".join(lines)})


@app.route("/api/status")
def api_status():
    global _agent_proc
    with _agent_lock:
        running = _agent_proc is not None and _agent_proc.poll() is None
    return jsonify({"running": running})


@app.route("/api/start", methods=["POST"])
def api_start():
    global _agent_proc
    data = request.get_json(silent=True) or {}
    n_experiments = data.get("n_experiments", 10)
    use_batch     = data.get("batch", False)
    api_key       = data.get("api_key", os.environ.get("NEBIUS_API_KEY", ""))

    with _agent_lock:
        if _agent_proc is not None and _agent_proc.poll() is None:
            return jsonify({"ok": False, "error": "Agent is already running."})

        cmd = [sys.executable, AGENT_SCRIPT, "--n-experiments", str(n_experiments)]
        if use_batch:
            cmd.append("--batch")

        env = {**os.environ, "NEBIUS_API_KEY": api_key, "PYTHONIOENCODING": "utf-8"}
        try:
            _agent_proc = subprocess.Popen(
                cmd,
                cwd=BASE_DIR,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return jsonify({"ok": True, "pid": _agent_proc.pid})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global _agent_proc
    with _agent_lock:
        if _agent_proc is None or _agent_proc.poll() is not None:
            return jsonify({"ok": True, "message": "Agent was not running."})
        try:
            _agent_proc.terminate()
            _agent_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _agent_proc.kill()
        _agent_proc = None
    return jsonify({"ok": True, "message": "Agent stopped."})


# ─────────────────────────────────────────────────────────────────────────────
# Main page
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    print("=" * 50)
    print("  Nebius AutoResearch Dashboard")
    print("  Open http://localhost:5000")
    print("=" * 50)
    app.run(debug=False, port=5000, threaded=True)
