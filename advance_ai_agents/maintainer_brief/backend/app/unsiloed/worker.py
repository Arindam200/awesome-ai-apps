"""Drains the extraction_jobs queue: submit queued jobs, poll until terminal.

Invoked by the orchestrator's EXTRACT stage — not a daemon. Postgres rows are
the queue. A failed document never blocks the brief.
"""

import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, ExtractionJob
from app.unsiloed.client import POLL_INTERVAL_S, UnsiloedClient, is_failure, is_success
from app.unsiloed.registry import DOC_CATEGORIES, get_schema

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 2  # initial submit + one re-submit on a Failed status


def _submit(client: UnsiloedClient, db: Session, job: ExtractionJob) -> None:
    doc = db.get(Document, job.document_id)
    try:
        if job.kind == "classify":
            job.unsiloed_job_id = client.submit_classify(doc.file_path, DOC_CATEGORIES)
        elif job.kind == "extract":
            job.unsiloed_job_id = client.submit_extract(doc.file_path, get_schema(job.schema_name))
        else:
            raise ValueError(f"unknown job kind {job.kind}")
        job.status = "submitted"
        job.attempts += 1
    except Exception as e:
        logger.exception("submit failed for job %s (%s %s)", job.id, job.kind, doc.file_path)
        job.attempts += 1
        if job.attempts >= MAX_ATTEMPTS:
            job.status = "failed"
            job.raw_response = {"error": str(e)}
    db.commit()


def drain(db: Session, document_ids: list[int], deadline_s: float = 600) -> dict:
    """Run all queued/submitted jobs for the given documents to a terminal state.

    Returns stats: {succeeded, failed, timed_out}.
    """
    client = UnsiloedClient()
    start = time.monotonic()
    stats = {"succeeded": 0, "failed": 0, "timed_out": 0}
    if not document_ids:
        return stats

    while True:
        jobs = list(
            db.scalars(
                select(ExtractionJob).where(
                    ExtractionJob.document_id.in_(document_ids),
                    ExtractionJob.status.in_(["queued", "submitted"]),
                )
            )
        )
        if not jobs:
            break
        if time.monotonic() - start > deadline_s:
            for job in jobs:
                job.status = "failed"
                job.raw_response = {"error": "stage deadline exceeded"}
                stats["timed_out"] += 1
            db.commit()
            break

        for job in jobs:
            if job.status == "queued":
                _submit(client, db, job)

        # Round-robin poll all submitted jobs once, then sleep
        for job in jobs:
            if job.status != "submitted" or not job.unsiloed_job_id:
                continue
            try:
                result = client.poll(job.kind, job.unsiloed_job_id)
            except Exception:
                logger.exception("poll failed for job %s", job.id)
                continue
            status = result.get("status")
            if is_success(status):
                job.status = "succeeded"
                job.raw_response = result
                job.updated_at = datetime.now(timezone.utc)
                stats["succeeded"] += 1
            elif is_failure(status):
                job.raw_response = result
                if job.attempts < MAX_ATTEMPTS:
                    logger.warning("job %s failed on Unsiloed side, re-submitting", job.id)
                    job.status = "queued"
                    job.unsiloed_job_id = None
                else:
                    job.status = "failed"
                    stats["failed"] += 1
            db.commit()

        if any(j.status in ("queued", "submitted") for j in jobs):
            time.sleep(POLL_INTERVAL_S)

    return stats
