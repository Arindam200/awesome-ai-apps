"""Document ingest: dashboard uploads -> documents table.

New documents get a classify job queued; the pipeline's CLASSIFY stage turns
the category into extract jobs.
"""

import hashlib
import logging
import mimetypes
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import DOCS_DIR
from app.models import Document, ExtractionJob, Project

logger = logging.getLogger(__name__)

ALLOWED_SUFFIXES = {".pdf", ".pptx", ".ppt", ".docx", ".doc", ".png", ".jpg", ".jpeg", ".tiff", ".xlsx", ".xls"}


def _safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:120]


def register_document(
    db: Session,
    project: Project,
    *,
    content: bytes,
    filename: str,
    title: str | None = None,
    source_url: str | None = None,
    doc_category: str | None = None,
) -> Document | None:
    """Store bytes on disk and insert a documents row + classify job.

    Pass doc_category for documents whose category is already known (e.g. the
    pipeline-generated digest) — skips the classify round-trip.
    Returns None if this exact content was already ingested (cache hit).
    """
    content_hash = hashlib.sha256(content).hexdigest()
    existing = db.scalar(
        select(Document).where(Document.project_id == project.id, Document.content_hash == content_hash)
    )
    if existing:
        logger.info("document %s already ingested (hash match, doc %s)", filename, existing.id)
        return None

    suffix = Path(filename).suffix.lower() or ".pdf"
    dest = DOCS_DIR / f"{content_hash[:16]}_{_safe_name(Path(filename).stem)}{suffix}"
    dest.write_bytes(content)

    doc = Document(
        project_id=project.id,
        title=title or Path(filename).stem,
        source_url=source_url,
        file_path=str(dest),
        content_hash=content_hash,
        mime_type=mimetypes.guess_type(filename)[0] or "application/pdf",
        doc_category=doc_category,
        status="classified" if doc_category else "pending",
    )
    db.add(doc)
    db.flush()
    if not doc_category:
        db.add(ExtractionJob(document_id=doc.id, kind="classify"))
    db.commit()
    return doc
