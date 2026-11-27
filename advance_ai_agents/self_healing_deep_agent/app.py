"""Optional live view: watch the agent in your browser.

    uv run app.py                                   # open the page, pick a situation, press Run
    uv run app.py --replay runs/<run>/events.jsonl  # replay a recorded run at its real speed

Each run happens in its own Python process (healing/live_worker.py). Its events stream to
the page as they happen, so what you see is the real run, not an animation."""
import argparse
import json
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from config import MODEL, PRICE
from scenarios import SCENARIOS, TASK

ROOT = Path(__file__).resolve().parent
PAGE = ROOT / "ui" / "index.html"
PREFIX = "EVENT "


class Run:
    """The current run: its events, and whether it is still going."""

    def __init__(self):
        self.lock = threading.Lock()
        self.id = 0
        self.events: list[dict] = []
        self.running = False

    def start(self, feed):
        with self.lock:
            if self.running:
                return None
            self.id += 1
            self.events, self.running = [], True
            run_id = self.id
        threading.Thread(target=self._consume, args=(run_id, feed), daemon=True).start()
        return run_id

    def _consume(self, run_id, feed):
        try:
            for event in feed:
                with self.lock:
                    if run_id == self.id:
                        self.events.append(event)
        finally:
            with self.lock:
                self.running = False


RUN = Run()


def live_feed(scenario: str, mode: str):
    proc = subprocess.Popen([sys.executable, "-m", "healing.live_worker", scenario, mode], cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"})
    errors = []
    for line in proc.stdout:
        if line.startswith(PREFIX):
            yield json.loads(line[len(PREFIX):])
        elif line.strip():
            errors.append(line.rstrip())
    if proc.wait() != 0:
        yield {"t": 0, "type": "crash", "message": "\n".join(errors[-12:])}


def replay_feed(path: Path):
    events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    start = time.perf_counter()
    for e in events:
        time.sleep(max(0.0, e["t"] - (time.perf_counter() - start)))
        yield e
    yield {"t": events[-1]["t"], "type": "summary", "replay": True, "passed": events[-1].get("passed"),
           "events_file": str(path)}


class Handler(BaseHTTPRequestHandler):
    replay_path: Path | None = None

    def log_message(self, *args):
        pass

    def _json(self, body, status=200):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            data = PAGE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == "/api/scenarios":
            self._json({"scenarios": [{k: s[k] for k in ("id", "name", "repairs", "expect")} for s in SCENARIOS],
                        "replay": str(self.replay_path) if self.replay_path else None,
                        "model": MODEL, "price": PRICE, "task": TASK})
        elif self.path.startswith("/api/stream"):
            self._stream()
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path != "/api/run":
            return self._json({"error": "not found"}, 404)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if self.replay_path:
            run_id = RUN.start(replay_feed(self.replay_path))
        else:
            scenario, mode = body.get("scenario", "S1").upper(), body.get("mode", "healing")
            if scenario not in {s["id"] for s in SCENARIOS} or mode not in ("healing", "plain"):
                return self._json({"error": "unknown scenario or mode"}, 400)
            run_id = RUN.start(live_feed(scenario, mode))
        if run_id is None:
            return self._json({"error": "a run is already in progress"}, 409)
        self._json({"run": run_id})

    def _stream(self):
        """Server-sent events: every event of the current run, then new ones as they arrive."""
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        run_id, sent = RUN.id, 0
        try:
            while True:
                with RUN.lock:
                    if RUN.id != run_id:
                        break
                    batch, running = RUN.events[sent:], RUN.running
                for e in batch:
                    self.wfile.write(f"data: {json.dumps(e, ensure_ascii=False)}\n\n".encode())
                sent += len(batch)
                self.wfile.flush()
                if not running and not batch:
                    self.wfile.write(b"event: end\ndata: {}\n\n")
                    break
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError):
            pass


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--replay", type=Path, help="an events.jsonl file to replay instead of a live run")
    ap.add_argument("--no-browser", action="store_true")
    a = ap.parse_args()
    if a.replay and not a.replay.exists():
        sys.exit(f"No such file: {a.replay}")
    Handler.replay_path = a.replay
    server = ThreadingHTTPServer(("127.0.0.1", a.port), Handler)
    url = f"http://127.0.0.1:{a.port}"
    print(f"Live view on {url}  (Ctrl+C to stop)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
