"""End-to-end pipeline: ingest -> route -> extract -> normalize -> analyze
-> synthesize -> render -> send.

Stages 1-3 are best-effort per item; 6-8 fail the run. Every stage is
idempotent (content-hash + dedup keys), so re-running is always safe.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors import documents as doc_conn
from app.connectors import github_conn, hackernews, reddit, security
from app.intelligence.normalize import normalize_extractions, normalize_raw_items
from app.intelligence.sentiment import score_sentiment
from app.intelligence.synthesize import synthesize_brief
from app.intelligence.trends import compute_trends
from app.models import Brief, Document, ExtractionJob, PipelineRun, Project
from app.newsletter.render import render_brief_html
from app.newsletter.send import send_brief
from app.pipeline.pages import render_pages
from app.unsiloed.registry import schemas_for_category
from app.unsiloed.worker import drain

logger = logging.getLogger(__name__)

MAX_NEW_DOCS_PER_RUN = 10

CONNECTORS = [github_conn, hackernews, reddit, security]


def _period(project: Project) -> tuple[date, date]:
    cadence = (project.config.get("newsletter") or {}).get("cadence", "weekly")
    today = datetime.now(timezone.utc).date()
    days = 1 if cadence == "daily" else 7
    return today - timedelta(days=days), today + timedelta(days=1)


def _set_stage(db: Session, run: PipelineRun, stage: str, **stats):
    run.stage = stage
    run.stats = {**(run.stats or {}), **stats}
    db.commit()
    logger.info("run %s -> %s %s", run.id, stage, stats or "")


def run_pipeline(db: Session, run: PipelineRun) -> None:
    project = db.get(Project, run.project_id)
    period_start, period_end = _period(project)
    since = datetime.combine(period_start, datetime.min.time(), tzinfo=timezone.utc)
    errors: list[str] = []

    try:
        # 1. INGEST
        _set_stage(db, run, "ingest")
        raw_items = []
        for connector in CONNECTORS:
            try:
                raw_items.extend(connector.fetch(project.config, since))
            except Exception as e:
                errors.append(f"{connector.__name__}: {e}")
                logger.exception("connector failed (continuing)")
        try:
            new_docs = doc_conn.ingest_config_documents(db, project)
        except Exception as e:
            errors.append(f"documents: {e}")
            new_docs = []
        _set_stage(db, run, "ingest", raw_items=len(raw_items), new_documents=len(new_docs))

        # 2. ROUTE: classify pending docs, then queue extract jobs per category
        _set_stage(db, run, "route")
        pending_docs = list(
            db.scalars(
                select(Document).where(
                    Document.project_id == project.id,
                    Document.status.in_(["pending", "classified", "extracting"]),
                ).limit(MAX_NEW_DOCS_PER_RUN)
            )
        )
        doc_ids = [d.id for d in pending_docs]
        classify_stats = drain(db, [d.id for d in pending_docs if d.status == "pending"], deadline_s=300)
        for doc in pending_docs:
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
                # live shape (verified): result.classification
                category = (
                    (raw.get("result") or {}).get("classification")
                    or raw.get("classification")
                    or "other"
                )
                doc.doc_category = str(category)
                doc.status = "classified"
            else:
                doc.status = "failed"
        db.commit()

        for doc in pending_docs:
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

        # 3. EXTRACT + page rendering
        _set_stage(db, run, "extract", classify=classify_stats)
        extract_stats = drain(db, doc_ids, deadline_s=600)
        for doc in pending_docs:
            if doc.status == "extracting":
                doc.status = "extracted"
                try:
                    render_pages(db, doc)
                except Exception as e:
                    errors.append(f"pages doc {doc.id}: {e}")
        db.commit()
        _set_stage(db, run, "extract", extract=extract_stats)

        # 4. NORMALIZE
        _set_stage(db, run, "normalize")
        n_api = normalize_raw_items(db, project, raw_items)
        all_doc_ids = list(db.scalars(select(Document.id).where(Document.project_id == project.id)))
        n_doc = normalize_extractions(db, project, all_doc_ids)
        n_sent = score_sentiment(db, project)
        _set_stage(db, run, "normalize", api_signals=n_api, doc_signals=n_doc, sentiment_scored=n_sent)

        # 5. ANALYZE
        _set_stage(db, run, "analyze")
        trend_rows = compute_trends(db, project, period_start, period_end)
        _set_stage(db, run, "analyze", trend_metrics=len(trend_rows))

        # 6. SYNTHESIZE
        _set_stage(db, run, "synthesize")
        brief_json = synthesize_brief(db, project, period_start, period_end)
        brief = Brief(
            project_id=project.id,
            run_id=run.id,
            period_start=period_start,
            period_end=period_end,
            brief_json=brief_json,
        )
        db.add(brief)
        db.commit()

        # 7. RENDER
        _set_stage(db, run, "render")
        brief.html = render_brief_html(db, project, brief)
        db.commit()

        # 8. SEND
        if run.dry_run:
            _set_stage(db, run, "send", skipped="dry_run")
        else:
            _set_stage(db, run, "send")
            send_brief(db, project, brief)

        run.status = "succeeded"
        run.stats = {**(run.stats or {}), "errors": errors, "brief_id": brief.id}
    except Exception as e:
        logger.exception("pipeline run %s failed", run.id)
        run.status = "failed"
        run.error = str(e)
        run.stats = {**(run.stats or {}), "errors": errors}
    finally:
        run.finished_at = datetime.now(timezone.utc)
        db.commit()
