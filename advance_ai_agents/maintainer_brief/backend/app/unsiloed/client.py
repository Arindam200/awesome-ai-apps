"""Unsiloed API client: submit/poll with a shared rate limiter and retries.

All Unsiloed traffic — submits AND polls — goes through one token bucket kept
at 50 req/60s, under the documented 60/60s limit.
"""

import json
import logging
import threading
import time
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings

logger = logging.getLogger(__name__)

POLL_INTERVAL_S = 5

# Verified against the live API (2026-06-12): statuses are lowercase
# ("completed"/"failed"), not the docs' "Succeeded"/"Failed". Accept both.
SUCCESS_STATUSES = {"completed", "succeeded", "success"}
FAILURE_STATUSES = {"failed", "error", "cancelled"}


def is_success(status: str | None) -> bool:
    return (status or "").lower() in SUCCESS_STATUSES


def is_failure(status: str | None) -> bool:
    return (status or "").lower() in FAILURE_STATUSES


def is_terminal(status: str | None) -> bool:
    return is_success(status) or is_failure(status)


class TokenBucket:
    def __init__(self, rate: int = 50, per_seconds: float = 60.0):
        self.capacity = rate
        self.tokens = float(rate)
        self.refill_per_s = rate / per_seconds
        self.lock = threading.Lock()
        self.last = time.monotonic()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.refill_per_s)
                self.last = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) / self.refill_per_s
            time.sleep(wait)


_bucket = TokenBucket()


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code == 429 or exc.response.status_code >= 500
    return False


class UnsiloedClient:
    def __init__(self):
        self.base_url = settings.unsiloed_base_url.rstrip("/")
        self.client = httpx.Client(
            headers={"api-key": settings.unsiloed_api_key},
            timeout=httpx.Timeout(120.0, connect=15.0),
        )

    @retry(
        retry=retry_if_exception(_is_retryable),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        reraise=True,
    )
    def _request(self, method: str, path: str, **kwargs) -> dict:
        _bucket.acquire()
        resp = self.client.request(method, f"{self.base_url}{path}", **kwargs)
        resp.raise_for_status()
        return resp.json()

    def submit_extract(
        self,
        file_path: str | Path,
        schema: dict,
        *,
        model: str | None = None,
        enable_citations: bool = True,
    ) -> str:
        data = {
            "schema_data": json.dumps(schema),
            "model": model or settings.unsiloed_model,
            "enable_citations": json.dumps(enable_citations),
        }
        with open(file_path, "rb") as f:
            result = self._request(
                "POST",
                "/v2/extract",
                data=data,
                files={"pdf_file": (Path(file_path).name, f, "application/pdf")},
            )
        return result["job_id"]

    def submit_classify(self, file_path: str | Path, categories: list[str]) -> str:
        with open(file_path, "rb") as f:
            result = self._request(
                "POST",
                "/classify",
                data={"categories": json.dumps(categories)},
                files={"pdf_file": (Path(file_path).name, f, "application/pdf")},
            )
        return result["job_id"]

    def poll(self, kind: str, unsiloed_job_id: str) -> dict:
        """One status check. kind: classify|parse|extract."""
        path = {"classify": "/classify", "parse": "/parse", "extract": "/extract"}[kind]
        return self._request("GET", f"{path}/{unsiloed_job_id}")

    def wait(self, kind: str, unsiloed_job_id: str, deadline_s: float = 600) -> dict:
        """Poll until terminal status or deadline. Returns the final response."""
        start = time.monotonic()
        while True:
            result = self.poll(kind, unsiloed_job_id)
            if is_terminal(result.get("status")):
                return result
            if time.monotonic() - start > deadline_s:
                raise TimeoutError(f"Unsiloed {kind} job {unsiloed_job_id} not done after {deadline_s}s")
            time.sleep(POLL_INTERVAL_S)
