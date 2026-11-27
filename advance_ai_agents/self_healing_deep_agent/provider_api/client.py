"""HTTP client the tools use. It lives outside tools/, so the agent can't edit it.

Every HTTP failure becomes a typed error. The healing middleware uses these
types to tell "the API is having a moment" apart from "our code is wrong".
"""
from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.request


class ProviderError(Exception):
    def __init__(self, status: int, body: dict, retry_after: float | None = None):
        self.status, self.body, self.retry_after = status, body, retry_after
        super().__init__(f"HTTP {status}: {body.get('error')}: {body.get('message', '')}".strip())


class RateLimitError(ProviderError):   # 429: wait and retry
    pass


class ServerError(ProviderError):      # 5xx: wait and retry
    pass


class AuthError(ProviderError):        # 401/403: a person has to fix the key
    pass


class RequestError(ProviderError):     # 400/404: the arguments were wrong
    pass


_trace = threading.local()


def start_trace() -> list:
    """Record every HTTP call made on this thread (like a browser's network tab)."""
    _trace.calls = []
    return _trace.calls


def _record(path: str, status: int, body):
    calls = getattr(_trace, "calls", None)
    if calls is not None:
        calls.append({"request": f"GET {path}", "status": status, "body": body})


def base_url() -> str:
    return os.environ.get("PROVIDER_API_URL", "http://127.0.0.1:8765")


def get_json(path: str, timeout: float = 10) -> dict:
    req = urllib.request.Request(base_url() + path, headers={"Authorization": "Bearer demo-key"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
            _record(path, resp.status, data)
            return data
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except ValueError:
            body = {}
        _record(path, e.code, body)
        retry = float(e.headers.get("Retry-After", 0) or 0) or None
        if e.code == 429:
            raise RateLimitError(e.code, body, retry) from None
        if e.code >= 500:
            raise ServerError(e.code, body, retry) from None
        if e.code in (401, 403):
            raise AuthError(e.code, body) from None
        raise RequestError(e.code, body) from None
    except (urllib.error.URLError, TimeoutError) as e:
        raise ServerError(0, {"error": "unreachable", "message": str(e)}) from None
