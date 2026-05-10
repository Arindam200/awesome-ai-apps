from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from boeing_rag.db import session_scope
from boeing_rag.schemas import UploadJobFile, UploadJobStatus
from boeing_rag.services import ingestion_pipeline


@dataclass
class UploadedPdf:
    key: str
    name: str
    relative_path: str | None
    path: Path


@dataclass
class UploadJob:
    job_id: str
    files: list[UploadedPdf]
    force: bool
    render_pages: bool
    status: str = "queued"
    processed_files: int = 0
    failed_files: int = 0
    current_file: str | None = None
    message: str = "Queued"
    started_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    file_statuses: dict[str, UploadJobFile] = field(default_factory=dict)


_jobs: dict[str, UploadJob] = {}
_lock = threading.Lock()


def create_upload_job(files: list[UploadedPdf], force: bool, render_pages: bool) -> UploadJobStatus:
    job = UploadJob(
        job_id=uuid4().hex,
        files=files,
        force=force,
        render_pages=render_pages,
        file_statuses={
            file.key: UploadJobFile(
                name=file.name,
                relative_path=file.relative_path,
                status="queued",
            )
            for file in files
        },
    )
    with _lock:
        _jobs[job.job_id] = job
    thread = threading.Thread(target=_run_job, args=(job.job_id,), daemon=True)
    thread.start()
    return get_upload_job(job.job_id)


def get_upload_job(job_id: str) -> UploadJobStatus:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            raise KeyError(job_id)
        return _snapshot(job)


def _run_job(job_id: str) -> None:
    with _lock:
        job = _jobs[job_id]
        job.status = "running"
        job.message = "Preparing uploaded PDFs"

    pipeline = ingestion_pipeline()
    for file in job.files:
        _mark_file(job_id, file.key, status="processing")
        with _lock:
            job = _jobs[job_id]
            job.current_file = file.name
            job.message = f"Processing {file.name}"
        try:
            with session_scope() as session:
                document_id = pipeline.ingest_file(
                    session,
                    file.path,
                    force=job.force,
                    render_pages=job.render_pages,
                )
            _mark_file(job_id, file.key, status="indexed", document_id=document_id)
            with _lock:
                job = _jobs[job_id]
                job.processed_files += 1
                job.message = f"Indexed {job.processed_files} of {len(job.files)} PDFs"
        except Exception as exc:
            _mark_file(job_id, file.key, status="failed", error=str(exc))
            with _lock:
                job = _jobs[job_id]
                job.processed_files += 1
                job.failed_files += 1
                job.message = f"Failed {file.name}"

    with _lock:
        job = _jobs[job_id]
        job.current_file = None
        job.finished_at = time.time()
        job.status = "failed" if job.failed_files == len(job.files) else "completed"
        job.message = (
            f"Completed {job.processed_files - job.failed_files} of {len(job.files)} PDFs"
            if job.failed_files
            else f"Completed {len(job.files)} PDFs"
        )


def _mark_file(
    job_id: str,
    key: str,
    status: str,
    document_id: str | None = None,
    error: str | None = None,
) -> None:
    with _lock:
        file_state = _jobs[job_id].file_statuses[key]
        file_state.status = status
        file_state.document_id = document_id
        file_state.error = error


def _snapshot(job: UploadJob) -> UploadJobStatus:
    return UploadJobStatus(
        job_id=job.job_id,
        status=job.status,
        total_files=len(job.files),
        processed_files=job.processed_files,
        failed_files=job.failed_files,
        current_file=job.current_file,
        message=job.message,
        files=list(job.file_statuses.values()),
        started_at=job.started_at,
        finished_at=job.finished_at,
    )
