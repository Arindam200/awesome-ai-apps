"""Okahu/Monocle configuration and trace helpers."""

import logging
import os
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from typing import Any

from research.config.settings import get_settings

logger = logging.getLogger(__name__)

_CONFIGURED_WORKFLOWS: set[str] = set()


def configure_okahu(workflow_name: str | None = None) -> bool:
    """Configure Monocle tracing for local files and/or Okahu Cloud."""

    settings = get_settings()
    workflow = workflow_name or settings.okahu_workflow_name
    exporter = settings.monocle_exporter or ""

    if settings.okahu_api_key is not None:
        os.environ["OKAHU_API_KEY"] = settings.okahu_api_key.get_secret_value()
    if exporter:
        os.environ["MONOCLE_EXPORTER"] = exporter

    exporter_names = {name.strip().lower() for name in exporter.split(",") if name}
    has_local_export = "file" in exporter_names
    has_cloud_export = "okahu" in exporter_names and settings.okahu_api_key is not None

    if not has_local_export and not has_cloud_export:
        logger.info("Okahu/Monocle tracing disabled.")
        return False

    if workflow in _CONFIGURED_WORKFLOWS:
        return True

    try:
        from monocle_apptrace import setup_monocle_telemetry

        setup_monocle_telemetry(workflow_name=workflow)
        _CONFIGURED_WORKFLOWS.add(workflow)
        logger.info(
            "Okahu/Monocle tracing enabled for workflow '%s' with exporter '%s'.",
            workflow,
            exporter or "<default>",
        )
        return True
    except Exception:
        logger.exception("Could not configure Okahu/Monocle tracing.")
        return False


@contextmanager
def trace_span(
    span_name: str,
    attributes: dict[str, Any] | None = None,
) -> Iterator[None]:
    """Create a synchronous Monocle trace span when tracing is available."""

    try:
        from monocle_apptrace.instrumentation.common.instrumentor import monocle_trace
    except Exception:
        logger.debug("Monocle sync span skipped: %s", span_name, exc_info=True)
        yield
        return

    with monocle_trace(span_name=span_name, attributes=attributes or {}):
        from opentelemetry import trace
        from opentelemetry.trace import Status, StatusCode

        span = trace.get_current_span()
        try:
            yield
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
        else:
            span.set_status(Status(StatusCode.OK))


@asynccontextmanager
async def atrace_span(
    span_name: str,
    attributes: dict[str, Any] | None = None,
) -> AsyncIterator[None]:
    """Create an async Monocle trace span when tracing is available."""

    try:
        from monocle_apptrace.instrumentation.common.instrumentor import amonocle_trace
    except Exception:
        logger.debug("Monocle async span skipped: %s", span_name, exc_info=True)
        yield
        return

    async with amonocle_trace(span_name=span_name, attributes=attributes or {}):
        from opentelemetry import trace
        from opentelemetry.trace import Status, StatusCode

        span = trace.get_current_span()
        try:
            yield
        except Exception as exc:
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            span.record_exception(exc)
            raise
        else:
            span.set_status(Status(StatusCode.OK))
