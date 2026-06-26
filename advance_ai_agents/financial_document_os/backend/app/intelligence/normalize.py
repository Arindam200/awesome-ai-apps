"""Normalization: Unsiloed extraction results -> typed entity rows + citations.

Reuses the verified Unsiloed response parsing:
  result.<array_prop>.value -> list of items
  item.<field> = {value, score:{extraction_score,...}, citation:{bbox,page,page_width,page_height}|null}
Coerces string values into numeric/date columns so SQL math + anomaly rules work.
"""

import logging
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ENTITY_MODELS, EntityCitation, ExtractionJob
from app.unsiloed.registry import SCHEMA_ENTITY_MAP

logger = logging.getLogger(__name__)


# ---------- Unsiloed response parsing (verified shape) ----------

def _unwrap(field):
    """Returns (value, extraction_score, citation_dict_or_None)."""
    if isinstance(field, dict) and "value" in field:
        score = field.get("score")
        if isinstance(score, dict):
            score = score.get("extraction_score", score.get("grounding_score"))
        return field.get("value"), score, field.get("citation")
    return field, None, None


def _extract_items(raw_response: dict, array_prop: str) -> list:
    data = raw_response.get("result") or raw_response.get("extracted_data") or raw_response.get("data") or {}
    arr = data.get(array_prop)
    value, _, _ = _unwrap(arr)
    return value if isinstance(value, list) else []


# ---------- value coercion ----------

def _to_num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return v
    s = re.sub(r"[^0-9.\-]", "", str(v).replace(",", ""))
    if s in ("", "-", ".", "-."):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _to_date(v):
    if not v:
        return None
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d %b %Y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return date(int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            return None
    return None


def _to_int(v):
    n = _to_num(v)
    return int(n) if n is not None else None


# field_name -> coercion for each model column (everything else stays str)
NUMERIC_FIELDS = {
    "opening_balance", "closing_balance", "amount", "balance_after", "contract_value",
    "principal_amount", "interest_rate", "current_value", "cost_basis", "quantity",
    "ownership_percentage",
}
DATE_FIELDS = {
    "statement_period_start", "statement_period_end", "start_date", "end_date",
    "maturity_date", "due_date", "valuation_date", "txn_date",
}
INT_FIELDS = {"tax_year"}


def _coerce(field_name: str, value):
    if value is None:
        return None
    if field_name in NUMERIC_FIELDS:
        return _to_num(value)
    if field_name in DATE_FIELDS:
        return _to_date(value)
    if field_name in INT_FIELDS:
        return _to_int(value)
    return str(value)


_LEGAL_SUFFIXES = re.compile(r"\b(llc|l\.l\.c|inc|incorporated|llp|l\.l\.p|ltd|corp|corporation|co|company|plc|gmbh)\b\.?", re.I)


def normalize_name(name: str | None) -> str:
    """Canonical key for entity resolution — lowercased, legal suffixes stripped."""
    if not name:
        return ""
    s = _LEGAL_SUFFIXES.sub("", str(name).lower())
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


# columns that exist on each model (for filtering extracted fields into columns)
def _model_columns(model) -> set[str]:
    return {c.name for c in model.__table__.columns}


def normalize_extractions(db: Session, project, document_ids: list[int]) -> int:
    """Turn succeeded extract jobs into typed entity rows + bbox citations.

    Idempotent: clears prior non-canonical entities + citations for these docs
    first, so re-runs don't duplicate. Commits per job so one bad row can't lose
    the batch.
    """
    if not document_ids:
        return 0

    # idempotency: drop prior per-document entities + their citations
    db.query(EntityCitation).filter(EntityCitation.document_id.in_(document_ids)).delete(
        synchronize_session=False
    )
    for kind, model in ENTITY_MODELS.items():
        q = db.query(model).filter(model.document_id.in_(document_ids))
        if kind == "vendor":
            q = q.filter(model.is_canonical.is_(False))  # keep canonical vendors
        q.delete(synchronize_session=False)
    db.commit()

    jobs = list(
        db.scalars(
            select(ExtractionJob).where(
                ExtractionJob.document_id.in_(document_ids),
                ExtractionJob.kind == "extract",
                ExtractionJob.status == "succeeded",
            )
        )
    )
    created = 0
    for job in jobs:
        if job.schema_name not in SCHEMA_ENTITY_MAP:
            continue
        array_prop, entity_kind = SCHEMA_ENTITY_MAP[job.schema_name]
        model = ENTITY_MODELS[entity_kind]
        columns = _model_columns(model)
        items = _extract_items(job.raw_response or {}, array_prop)

        try:
            for item in items:
                if not isinstance(item, dict):
                    continue
                col_values, citations, scores, raw_fields = {}, [], [], {}
                for fname, fval in item.items():
                    value, score, citation = _unwrap(fval)
                    raw_fields[fname] = value
                    if score is not None:
                        scores.append(score)
                    if fname in columns:
                        col_values[fname] = _coerce(fname, value)
                    if citation and citation.get("bbox"):
                        citations.append((fname, citation, score, str(value)[:300]))

                if not any(v is not None for v in col_values.values()):
                    continue

                # vendors.normalized_name is NOT NULL — derive it (resolution refines later)
                if entity_kind == "vendor":
                    col_values["normalized_name"] = normalize_name(col_values.get("name"))
                # contracts table holds both contracts and loans — tag the type by source schema
                if entity_kind == "contract":
                    col_values["contract_type"] = (
                        "loan_agreement" if job.schema_name == "loans" else "vendor_contract"
                    )

                row = model(
                    project_id=project.id,
                    document_id=job.document_id,
                    confidence=min(scores) if scores else None,
                    source_page=(citations[0][1].get("page") if citations else None),
                    raw_fields=raw_fields,
                    **col_values,
                )
                db.add(row)
                db.flush()
                created += 1

                for fname, citation, score, snippet in citations:
                    db.add(
                        EntityCitation(
                            entity_kind=entity_kind,
                            entity_id=row.id,
                            field_name=fname,
                            document_id=job.document_id,
                            page_no=int(citation.get("page", 1)),
                            bbox=citation,
                            extraction_score=score,
                            snippet=snippet,
                        )
                    )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("normalize failed for job %s (%s); skipping", job.id, job.schema_name)
    return created
