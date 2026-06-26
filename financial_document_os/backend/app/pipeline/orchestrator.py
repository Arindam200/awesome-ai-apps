"""Document processing pipeline: ingest -> classify -> extract -> normalize -> analyze.

Per-upload trigger (no firehose connectors). Stages are idempotent: content-hash
dedup on docs, succeeded-job cache on extraction. A failed document never blocks
the run.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.intelligence import anomalies, resolve
from app.intelligence.normalize import normalize_extractions
from app.models import Document, ExtractionJob, PipelineRun, Project
from app.pipeline.pages import render_pages
from app.unsiloed.registry import schemas_for_category
from app.unsiloed.worker import drain

logger = logging.getLogger(__name__)


def _set_stage(db: Session, run: PipelineRun, stage: str, **stats):
    run.stage = stage
    run.stats = {**(run.stats or {}), **stats}
    db.commit()
    logger.info("run %s -> %s %s", run.id, stage, stats or "")


def run_pipeline(db: Session, run: PipelineRun) -> None:
    project = db.get(Project, run.project_id)
    errors: list[str] = []

    try:
        # 1. INGEST — select docs needing processing
        _set_stage(db, run, "ingest")
        pending = list(
            db.scalars(
                select(Document).where(
                    Document.project_id == project.id,
                    Document.status.in_(["pending", "classified", "extracting"]),
                )
            )
        )
        doc_ids = [d.id for d in pending]
        _set_stage(db, run, "ingest", pending_documents=len(pending))

        # 2. CLASSIFY
        _set_stage(db, run, "classify")
        classify_stats = drain(db, [d.id for d in pending if d.status == "pending"], deadline_s=900)
        for doc in pending:
            if doc.status != "pending":
                continue
            job = db.scalar(
                select(ExtractionJob).where(
                    ExtractionJob.document_id == doc.id,
                    ExtractionJob.kind == "classify",
                    ExtractionJob.status == "succeeded",
                )
            )
            if job:
                raw = job.raw_response or {}
                category = (raw.get("result") or {}).get("classification") or raw.get("classification") or "other"
                doc.doc_category = str(category)
                doc.status = "classified"
            else:
                doc.status = "failed"
                errors.append(f"classify failed: doc {doc.id}")
        db.commit()
        _set_stage(db, run, "classify", classify=classify_stats)

        # 3. EXTRACT — queue per-category schemas, drain, render pages
        for doc in pending:
            if doc.status != "classified":
                continue
            for schema_name in schemas_for_category(doc.doc_category):
                exists = db.scalar(
                    select(ExtractionJob.id).where(
                        ExtractionJob.document_id == doc.id,
                        ExtractionJob.kind == "extract",
                        ExtractionJob.schema_name == schema_name,
                        ExtractionJob.status.in_(["queued", "submitted", "succeeded"]),
                    )
                )
                if not exists:
                    db.add(ExtractionJob(document_id=doc.id, kind="extract", schema_name=schema_name))
            doc.status = "extracting"
        db.commit()

        extract_stats = drain(db, doc_ids, deadline_s=2400)
        for doc in pending:
            if doc.status == "extracting":
                doc.status = "extracted"
                try:
                    render_pages(db, doc)
                except Exception as e:
                    errors.append(f"render doc {doc.id}: {e}")
        db.commit()
        _set_stage(db, run, "extract", extract=extract_stats)

        # 4. NORMALIZE — typed entities + citations, then entity resolution
        _set_stage(db, run, "normalize")
        all_doc_ids = list(db.scalars(select(Document.id).where(Document.project_id == project.id)))
        n_entities = normalize_extractions(db, project, all_doc_ids)
        n_resolved = resolve.run(db, project)
        _set_stage(db, run, "normalize", entities=n_entities, vendors_resolved=n_resolved)

        # 5. ANALYZE — anomaly detection
        _set_stage(db, run, "analyze")
        n_anomalies = anomalies.run(db, project)
        _set_stage(db, run, "analyze", anomalies=n_anomalies)

        run.status = "succeeded"
        run.stats = {**(run.stats or {}), "errors": errors}
    except Exception as e:
        logger.exception("pipeline run %s failed", run.id)
        db.rollback()  # clear any failed-flush state so the status write can commit
        run = db.get(PipelineRun, run.id)
        run.status = "failed"
        run.error = str(e)[:2000]
        run.stats = {**(run.stats or {}), "errors": errors}
    finally:
        try:
            run.finished_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("could not finalize run %s status", run.id)
