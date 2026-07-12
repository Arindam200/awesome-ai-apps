"""Normalization: raw API items + Unsiloed extractions -> signals (+ citations)."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.connectors.base import RawItem
from app.intelligence.dedup import api_dedup_key, document_dedup_key
from app.models import Document, ExtractionJob, Project, Signal, SignalCitation
from app.unsiloed.registry import SCHEMA_SIGNAL_MAP

logger = logging.getLogger(__name__)

FEATURE_LABELS = {"feature", "enhancement", "kind/enhancement", "kind/feature", "feature request"}
SENTIMENT_WORDS = {"positive": 0.6, "neutral": 0.0, "negative": -0.6}


def _match_keywords(project: Project, *texts: str) -> list[str]:
    haystack = " ".join(t for t in texts if t).lower()
    found = []
    for kw in project.config.get("keywords") or []:
        if kw.lower() in haystack:
            found.append(kw)
    for comp in project.config.get("competitors") or []:
        for kw in comp.get("keywords") or []:
            if kw.lower() in haystack:
                found.append(comp["name"])
                break
    return sorted(set(found))


def _insert_signal(db: Session, **kwargs) -> Signal | None:
    """Insert unless dedup_key already exists. Returns the new Signal or None."""
    exists = db.scalar(
        select(Signal.id).where(
            Signal.project_id == kwargs["project_id"], Signal.dedup_key == kwargs["dedup_key"]
        )
    )
    if exists:
        return None
    signal = Signal(**kwargs)
    db.add(signal)
    db.flush()
    return signal


# ---------- API sources ----------

def normalize_raw_items(db: Session, project: Project, items: list[RawItem]) -> int:
    created = 0
    for item in items:
        observed = item.observed_at or datetime.now(timezone.utc)
        keywords = _match_keywords(project, item.title, item.body)

        if item.source_kind == "github":
            kind = item.extra.get("kind")
            labels = set(item.extra.get("labels") or [])
            disc_category = (item.extra.get("category") or "").lower()
            if kind == "issue" and labels & FEATURE_LABELS:
                signal_type, category = "feature_request", "github_issue"
            elif kind == "discussion" and ("idea" in disc_category or "feature" in disc_category):
                signal_type, category = "feature_request", "github_discussion"
            elif kind == "release":
                signal_type, category = "community", "release"
            else:
                signal_type, category = "community", kind or "issue"
        elif item.source_kind in ("hackernews", "reddit"):
            # Algolia/Reddit search match loosely — require a real keyword hit
            if not keywords:
                continue
            signal_type, category = "ecosystem_mention", item.extra.get("kind", "post")
        elif item.source_kind == "osv":
            signal_type, category = "security", str(item.extra.get("severity", "unknown"))
        elif item.source_kind == "web":
            # Exa results are already query-scoped + semantic — no keyword-hit
            # requirement (semantic matches may lack the literal keyword).
            signal_type, category = "ecosystem_mention", "web"
        else:
            signal_type, category = "community", item.source_kind

        signal = _insert_signal(
            db,
            project_id=project.id,
            signal_type=signal_type,
            source_kind=item.source_kind,
            source_url=item.source_url,
            title=item.title[:500],
            summary=item.body[:1000] or None,
            category=category,
            urgency="high" if signal_type == "security" else None,
            keywords=keywords or None,
            payload=item.extra,
            confidence=1.0,
            dedup_key=api_dedup_key(item.source_kind, item.source_url),
            observed_at=observed,
        )
        if signal:
            created += 1
    db.commit()
    return created


# ---------- Unsiloed extractions ----------
#
# Live response shape (verified 2026-06-12):
#   result.<array_prop> = {score: {...}, value: [ item, ... ]}
#   item.<field> = {
#     score: {grounding_score: float, extraction_score: float},
#     value: <extracted value>,
#     citation: {bbox: [x0,y0,x1,y1], page: int,
#                page_width: float, page_height: float} | null
#   }


def _unwrap(field):
    """Returns (value, extraction_score, citation_dict_or_None)."""
    if isinstance(field, dict) and "value" in field:
        score = field.get("score")
        if isinstance(score, dict):
            score = score.get("extraction_score", score.get("grounding_score"))
        return field.get("value"), score, field.get("citation")
    return field, None, None


def _extract_items(raw_response: dict, array_prop: str) -> list:
    data = (
        raw_response.get("result")
        or raw_response.get("extracted_data")
        or raw_response.get("data")
        or {}
    )
    arr = data.get(array_prop)
    value, _, _ = _unwrap(arr)
    return value if isinstance(value, list) else []


def normalize_extractions(db: Session, project: Project, document_ids: list[int]) -> int:
    """Turn succeeded extract jobs into signals + bbox citations."""
    created = 0
    jobs = db.scalars(
        select(ExtractionJob).where(
            ExtractionJob.document_id.in_(document_ids) if document_ids else False,
            ExtractionJob.kind == "extract",
            ExtractionJob.status == "succeeded",
        )
    ) if document_ids else []

    for job in jobs:
        doc = db.get(Document, job.document_id)
        array_prop, signal_type = SCHEMA_SIGNAL_MAP[job.schema_name]
        items = _extract_items(job.raw_response or {}, array_prop)

        for item in items:
            if not isinstance(item, dict):
                continue
            fields, citations, scores = {}, [], []
            for fname, fval in item.items():
                value, score, citation = _unwrap(fval)
                fields[fname] = value
                if score is not None:
                    scores.append(score)
                if citation and citation.get("bbox"):
                    # store the full citation verbatim — bbox corners PLUS the
                    # page dims Unsiloed normalized to (the scaling reference)
                    citations.append((fname, citation.get("page", 1), citation, str(value)[:300]))

            title = str(
                fields.get("feature_name")
                or fields.get("project_name")
                or fields.get("vulnerability_id")
                or fields.get("affected_component")
                or fields.get("summary", "")[:80]
                or "extracted signal"
            )
            sentiment = SENTIMENT_WORDS.get(str(fields.get("sentiment", "")).lower())
            urgency = fields.get("urgency") or fields.get("severity")

            signal = _insert_signal(
                db,
                project_id=project.id,
                signal_type=signal_type,
                source_kind="document",
                source_url=doc.source_url,
                document_id=doc.id,
                title=title[:500],
                summary=fields.get("summary"),
                category=fields.get("category") or fields.get("mention_type") or fields.get("relevance"),
                urgency=str(urgency).lower() if urgency else None,
                sentiment=sentiment,
                keywords=_match_keywords(project, title, str(fields.get("summary") or "")) or None,
                payload=fields,
                confidence=min(scores) if scores else None,
                dedup_key=document_dedup_key(doc.id, signal_type, title),
                observed_at=doc.created_at or datetime.now(timezone.utc),
            )
            if signal:
                created += 1
                for fname, page_no, bbox, snippet in citations:
                    db.add(
                        SignalCitation(
                            signal_id=signal.id,
                            document_id=doc.id,
                            field_name=fname,
                            page_no=int(page_no),
                            bbox=bbox,
                            snippet=snippet,
                        )
                    )
    db.commit()
    return created
