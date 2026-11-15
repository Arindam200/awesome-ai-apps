"""Small, dependency-free JSONL tracing primitives for agent workflows."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class SpanRecord:
    """Serializable representation of one agent, tool, retrieval, or model span."""

    trace_id: str
    span_id: str
    parent_span_id: str | None
    name: str
    kind: str
    status: str
    started_at: str
    ended_at: str
    duration_ms: float
    attributes: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None


class Span:
    """Mutable span handle exposed inside a recorder context manager."""

    def __init__(self, attributes: dict[str, Any]) -> None:
        self.attributes = attributes

    def set(self, **attributes: Any) -> None:
        self.attributes.update(attributes)


class JsonlTraceRecorder:
    """Record nested spans as newline-delimited JSON for local inspection."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._current_span: ContextVar[tuple[str, str] | None] = ContextVar(
            "current_span", default=None
        )

    @contextmanager
    def span(
        self,
        name: str,
        *,
        kind: str,
        trace_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """Capture timing, hierarchy, attributes, and exception details for one span."""

        parent = self._current_span.get()
        resolved_trace_id = trace_id or (parent[0] if parent else uuid.uuid4().hex)
        span_id = uuid.uuid4().hex[:16]
        handle = Span(dict(attributes or {}))
        token = self._current_span.set((resolved_trace_id, span_id))
        started_at = _utc_now()
        started = time.perf_counter()
        status = "ok"
        error = None

        try:
            yield handle
        except Exception as exc:
            status = "error"
            error = {"type": type(exc).__name__, "message": str(exc)}
            raise
        finally:
            duration_ms = round((time.perf_counter() - started) * 1000, 3)
            self._current_span.reset(token)
            self._write(
                SpanRecord(
                    trace_id=resolved_trace_id,
                    span_id=span_id,
                    parent_span_id=parent[1] if parent else None,
                    name=name,
                    kind=kind,
                    status=status,
                    started_at=started_at,
                    ended_at=_utc_now(),
                    duration_ms=duration_ms,
                    attributes=handle.attributes,
                    error=error,
                )
            )

    def _write(self, record: SpanRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as trace_file:
            trace_file.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def load_spans(path: str | Path) -> list[dict[str, Any]]:
    """Load trace records while ignoring blank lines."""

    with Path(path).open(encoding="utf-8") as trace_file:
        return [json.loads(line) for line in trace_file if line.strip()]
