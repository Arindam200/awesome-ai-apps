"""A small local stand-in for an LLM provider's billing API, with switchable faults.

It runs on localhost in a background thread. Scenarios turn faults on and off to
reproduce what real APIs do: rate limits, expired keys, retired model ids.

    GET /v2/usage?month=2026-11&page=1   paginated request logs
    GET /v2/models/<model_id>            pricing (v2 schema: pricing.unit_usd)
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

PAGE_SIZE = 10

# Mock catalog, USD per 1M tokens: (input, cached input, output)
CATALOG = {
    "deepseek-ai/DeepSeek-V4.1-Flash-1017-fast": (0.60, 0.012, 2.40),
    "meta-llama/Llama-3.3-70B-Instruct": (0.13, 0.013, 0.40),
    "Qwen/Qwen3-235B-A22B-Instruct-2507": (0.20, 0.020, 0.60),
}
RETIRED = {"Qwen/Qwen3-235B-A22B-Instruct": "Qwen/Qwen3-235B-A22B-Instruct-2507"}


def _usage_rows(model_ids: list[str]) -> list[dict]:
    """26 deterministic request logs. Some counts arrive as strings like "1,240"
    (the logs come from a CSV export), and Llama never hits the prompt cache."""
    rows, n = [], 0
    plan = [(model_ids[0], 12), (model_ids[1], 8), (model_ids[2], 6)]
    for model, count in plan:
        for i in range(count):
            n += 1
            prompt = 900 + 137 * n
            cached = 0 if "Llama" in model else (prompt * 3) // 4
            output = 60 + 11 * n
            row = {"request_id": f"req_{n:03d}", "model": model,
                   "prompt_tokens": prompt, "cached_tokens": cached, "completion_tokens": output}
            if i % 3 == 1:  # every third row came through the CSV exporter
                row = {**row, "prompt_tokens": f"{prompt:,}", "cached_tokens": f"{cached:,}",
                       "completion_tokens": f"{output:,}"}
            rows.append(row)
    return rows


class FaultState:
    """What the API is doing wrong right now. Scenarios set this before each run."""

    def __init__(self):
        self.reset()

    def reset(self, rate_limit_pricing: int = 0, expired_key: bool = False,
              retired_model_in_logs: bool = False):
        self.rate_limit_left = rate_limit_pricing   # next N pricing calls get HTTP 429
        self.expired_key = expired_key              # every call gets HTTP 401
        ids = list(CATALOG)
        if retired_model_in_logs:                   # logs still use the old Qwen id
            ids[2] = "Qwen/Qwen3-235B-A22B-Instruct"
        self.rows = _usage_rows(ids)
        self.requests: list[str] = []


FAULTS = FaultState()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # keep the agent's terminal clean
        pass

    def _send(self, status: int, body: dict, headers: dict | None = None):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        FAULTS.requests.append(url.path)
        if FAULTS.expired_key:
            return self._send(401, {"error": "api_key_expired",
                                    "message": "The API key expired on 2026-11-20. "
                                               "Create a new key in the billing console."})
        if url.path == "/v2/usage":
            return self._usage(parse_qs(url.query))
        if url.path.startswith("/v2/models/"):
            return self._model(unquote(url.path.removeprefix("/v2/models/")))
        return self._send(404, {"error": "not_found"})

    def _usage(self, q):
        month = q.get("month", [""])[0]
        if month != "2026-11":
            return self._send(400, {"error": "invalid_month",
                                    "message": "Usage is available for 2026-11 only (format YYYY-MM)."})
        page = int(q.get("page", ["1"])[0])
        rows = FAULTS.rows
        start = (page - 1) * PAGE_SIZE
        chunk = rows[start:start + PAGE_SIZE]
        next_page = page + 1 if start + PAGE_SIZE < len(rows) else None
        return self._send(200, {"month": month, "page": page, "next_page": next_page,
                                "total": len(rows), "data": chunk})

    def _model(self, model_id: str):
        if FAULTS.rate_limit_left > 0:
            FAULTS.rate_limit_left -= 1
            return self._send(429, {"error": "rate_limited", "message": "Too many requests."},
                              {"Retry-After": "1"})
        if model_id in RETIRED:
            new = RETIRED[model_id]
            return self._send(404, {"error": "model_retired",
                                    "message": f"{model_id} was retired and is now billed as {new}.",
                                    "use_instead": new})
        if model_id not in CATALOG:
            return self._send(404, {"error": "model_not_found", "message": f"Unknown model {model_id}",
                                    "known_models": list(CATALOG)})
        unit, cached, output = CATALOG[model_id]
        return self._send(200, {
            "model": model_id,
            "api_version": "2026-11-01",
            "pricing": {  # v1 of this API had a flat "price_usd" key here
                "unit_usd": unit, "cached_unit_usd": cached, "output_unit_usd": output,
                "per": "1M tokens"},
        })


def start_server(port: int = 0) -> tuple[ThreadingHTTPServer, str]:
    """Start the API in a daemon thread. Returns the server and its base URL."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"
