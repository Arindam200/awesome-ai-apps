"""Exercise real HTTP and SDK parsing against a local synthetic endpoint."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest
from openai import BadRequestError, OpenAI

from tracker import CostTracker, load_rows


def test_loopback_endpoint_records_success_unknown_usage_and_error(tmp_path):
    """Keep request metadata accurate through a real local HTTP exchange."""
    calls = []

    class Endpoint(BaseHTTPRequestHandler):
        """Return deterministic completion fixtures without external inference."""

        def log_message(self, *_):
            """Keep the test HTTP server silent."""

        def do_POST(self):
            """Serve compatible completions or a deliberate provider failure."""
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, body))
            failed = body["model"] == "failure"
            payload = {
                "id": "loopback-fixture",
                "object": "chat.completion",
                "created": 0,
                "model": body["model"],
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Synthetic reply"},
                    }
                ],
            }
            if body["model"] == "fixture-model":
                payload["usage"] = {
                    "prompt_tokens": 1000,
                    "completion_tokens": 200,
                    "total_tokens": 1200,
                }
            if failed:
                payload = {"error": {"message": "private-provider-error", "type": "bad_request"}}
            encoded = json.dumps(payload).encode()
            self.send_response(400 if failed else 200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    with ThreadingHTTPServer(("127.0.0.1", 0), Endpoint) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with OpenAI(
                api_key="local-fixture-key",
                base_url=f"http://127.0.0.1:{server.server_port}/v1",
                max_retries=0,
                timeout=5,
            ) as client:
                tracker = CostTracker(
                    client,
                    tmp_path / "usage.db",
                    "demo",
                    Path(__file__).resolve().parents[1] / "pricing.example.json",
                )
                for model in ["fixture-model", "unknown-usage"]:
                    response = tracker.create(
                        model=model, tag="local-check", messages=[{"role": "user", "content": "x"}]
                    )
                    assert response.choices[0].message.content == "Synthetic reply"
                with pytest.raises(BadRequestError):
                    tracker.create(model="failure", messages=[])
        finally:
            server.shutdown()
            worker.join(timeout=5)

    assert len(calls) == 3
    assert all(path == "/v1/chat/completions" and "tag" not in body for path, body in calls)
    rows = load_rows(tracker.database)
    assert [row["estimated_cost_usd"] for row in rows] == ["0.0014", None, None]
    assert [row["status"] for row in rows] == ["success", "success", "error"]
    assert rows[-1]["error_type"] == "BadRequestError"
    assert "private-provider-error" not in json.dumps(rows)
    assert not worker.is_alive()
