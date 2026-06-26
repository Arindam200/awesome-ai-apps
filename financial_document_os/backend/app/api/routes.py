"""API routes for Financial Document OS."""

import threading
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.connectors.documents import ALLOWED_SUFFIXES, register_document
from app.db import SessionLocal, get_db
from app.models import (
    Account,
    Contract,
    Document,
    DocumentPage,
    ENTITY_MODELS,
    EntityCitation,
    Investment,
    Obligation,
    PipelineRun,
    Project,
    TaxItem,
    Transaction,
    Vendor,
)
from app.pipeline.orchestrator import run_pipeline

router = APIRouter()


def _default_project(db: Session) -> Project:
    project = db.scalar(select(Project).limit(1))
    if not project:
        raise HTTPException(500, "no project configured")
    return project


# ---------- runs ----------

class RunRequest(BaseModel):
    project_id: int | None = None


def _run_in_thread(run_id: int):
    db = SessionLocal()
    try:
        run_pipeline(db, db.get(PipelineRun, run_id))
    finally:
        db.close()


@router.post("/runs")
def create_run(req: RunRequest, db: Session = Depends(get_db)):
    project = db.get(Project, req.project_id) if req.project_id else _default_project(db)
    active = db.scalar(
        select(PipelineRun.id).where(PipelineRun.project_id == project.id, PipelineRun.status == "running")
    )
    if active:
        raise HTTPException(409, f"run {active} already in progress")
    run = PipelineRun(project_id=project.id, stats={})
    db.add(run)
    db.commit()
    threading.Thread(target=_run_in_thread, args=(run.id,), daemon=True).start()
    return {"run_id": run.id, "status": run.status}


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return {
        "id": run.id, "status": run.status, "stage": run.stage,
        "stats": run.stats, "error": run.error,
        "started_at": run.started_at, "finished_at": run.finished_at,
    }


@router.get("/runs")
def list_runs(db: Session = Depends(get_db)):
    runs = db.scalars(select(PipelineRun).order_by(PipelineRun.id.desc()).limit(10)).all()
    return [{"id": r.id, "status": r.status, "stage": r.stage, "started_at": r.started_at} for r in runs]


# ---------- documents ----------

@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    project = _default_project(db)
    docs = db.scalars(
        select(Document).where(Document.project_id == project.id).order_by(Document.created_at.desc())
    ).all()
    return [
        {
            "id": d.id, "title": d.title, "doc_category": d.doc_category,
            "page_count": d.page_count, "status": d.status, "created_at": d.created_at,
        }
        for d in docs
    ]


@router.post("/documents/upload")
async def upload_document(file: UploadFile, db: Session = Depends(get_db)):
    project = _default_project(db)
    if Path(file.filename or "").suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(422, f"unsupported file type; allowed: {sorted(ALLOWED_SUFFIXES)}")
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(413, "file exceeds 100MB Unsiloed limit")
    doc = register_document(db, project, content=content, filename=file.filename or "upload.pdf")
    if doc is None:
        return {"status": "duplicate", "detail": "this exact file was already ingested"}
    return {"status": "created", "document_id": doc.id}


# ---------- entities ----------

ENTITY_DISPLAY = {
    "account": ["institution_name", "account_holder", "account_number_masked", "account_type",
                "currency", "opening_balance", "closing_balance", "statement_period_start", "statement_period_end"],
    "transaction": ["txn_date", "description", "counterparty", "amount", "direction", "balance_after", "category"],
    "vendor": ["name", "address", "tax_id", "is_canonical", "needs_review"],
    "contract": ["contract_type", "counterparty", "contract_value", "currency", "start_date", "end_date",
                 "principal_amount", "interest_rate", "maturity_date", "company_address"],
    "investment": ["holding_name", "ticker", "quantity", "cost_basis", "current_value",
                   "ownership_percentage", "valuation_date"],
    "obligation": ["obligation_type", "description", "counterparty", "amount", "due_date"],
    "tax": ["tax_year", "jurisdiction", "filing_type", "line_item", "counterparty", "amount"],
}


@router.get("/entities/kinds")
def entity_kinds(db: Session = Depends(get_db)):
    project = _default_project(db)
    out = []
    for kind, model in ENTITY_MODELS.items():
        count = db.scalar(select(func.count(model.id)).where(model.project_id == project.id))
        out.append({"kind": kind, "count": count or 0, "columns": ENTITY_DISPLAY[kind]})
    return out


def _ser(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    return v


def _row_dict(row, columns) -> dict:
    d = {"id": row.id, "document_id": row.document_id, "confidence": row.confidence,
         "source_page": row.source_page}
    for c in columns:
        d[c] = _ser(getattr(row, c, None))
    return d


@router.get("/entities/{kind}")
def list_entities(kind: str, limit: int = 200, db: Session = Depends(get_db)):
    if kind not in ENTITY_MODELS:
        raise HTTPException(404, f"unknown entity kind {kind}")
    project = _default_project(db)
    model = ENTITY_MODELS[kind]
    columns = ENTITY_DISPLAY[kind]
    rows = db.scalars(
        select(model).where(model.project_id == project.id).order_by(model.id).limit(min(limit, 1000))
    ).all()
    # which (id, field) pairs have a citation
    cited = set(
        db.execute(
            select(EntityCitation.entity_id, EntityCitation.field_name).where(
                EntityCitation.entity_kind == kind,
                EntityCitation.entity_id.in_([r.id for r in rows]) if rows else False,
            )
        ).all()
    )
    return {
        "kind": kind,
        "columns": columns,
        "rows": [
            {**_row_dict(r, columns),
             "cited_fields": [c for c in columns if (r.id, c) in cited]}
            for r in rows
        ],
    }


@router.get("/entities/{kind}/{entity_id}/citations")
def entity_citations(kind: str, entity_id: int, field: str | None = None, db: Session = Depends(get_db)):
    if kind not in ENTITY_MODELS:
        raise HTTPException(404, f"unknown entity kind {kind}")
    q = select(EntityCitation).where(
        EntityCitation.entity_kind == kind, EntityCitation.entity_id == entity_id
    )
    if field:
        q = q.where(EntityCitation.field_name == field)
    cits = db.scalars(q).all()
    if not cits:
        return {"citations": [], "document": None}

    doc = db.get(Document, cits[0].document_id)
    pages = db.scalars(
        select(DocumentPage).where(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_no)
    ).all()
    return {
        "citations": [
            {"id": c.id, "field_name": c.field_name, "page_no": c.page_no,
             "bbox": c.bbox, "snippet": c.snippet, "extraction_score": c.extraction_score}
            for c in cits
        ],
        "document": {
            "id": doc.id, "title": doc.title, "doc_category": doc.doc_category,
            "page_count": doc.page_count,
            "pages": [
                {"page_no": p.page_no, "width_px": p.width_px, "height_px": p.height_px,
                 "width_pt": p.width_pt, "height_pt": p.height_pt}
                for p in pages
            ],
        },
    }


# ---------- document editing ----------

class ImpactRequest(BaseModel):
    match_value: str
    field_name: str | None = None


class ApplyEditRequest(BaseModel):
    match_value: str
    replacement_text: str
    field_name: str | None = None


@router.post("/edit/impact")
def edit_impact(req: ImpactRequest, db: Session = Depends(get_db)):
    from app.intelligence.edit import find_impact

    project = _default_project(db)
    impact = find_impact(db, project, req.match_value, req.field_name)
    return {
        "match_value": req.match_value,
        "documents_affected": len(impact),
        "occurrences_total": sum(len(d["occurrences"]) for d in impact),
        "documents": impact,
    }


@router.post("/edit/apply")
def edit_apply(req: ApplyEditRequest, db: Session = Depends(get_db)):
    from app.intelligence.edit import apply_edit

    if not settings.editing_enabled:
        raise HTTPException(403, "editing is disabled (calibration not passed)")
    project = _default_project(db)
    return apply_edit(db, project, req.match_value, req.replacement_text, req.field_name)


@router.get("/edit/download/{edit_id}")
def edit_download(edit_id: int, db: Session = Depends(get_db)):
    from app.models import DocumentEdit

    edit = db.get(DocumentEdit, edit_id)
    if not edit or not edit.edited_file_path:
        raise HTTPException(404, "edited file not found")
    return FileResponse(edit.edited_file_path, media_type="application/pdf",
                        filename=f"edited_{edit.document_id}.pdf")


# ---------- anomalies ----------

@router.get("/anomalies")
def list_anomalies(db: Session = Depends(get_db)):
    from app.models import Anomaly

    project = _default_project(db)
    rows = db.scalars(
        select(Anomaly).where(Anomaly.project_id == project.id).order_by(Anomaly.id)
    ).all()
    sev_order = {"high": 0, "medium": 1, "low": 2}
    rows.sort(key=lambda a: sev_order.get(a.severity, 3))
    return [
        {
            "id": a.id, "rule": a.rule, "severity": a.severity, "title": a.title,
            "description": a.description, "entity_refs": a.entity_refs,
            "evidence_citation_ids": a.evidence_citation_ids, "source": a.source,
        }
        for a in rows
    ]


# ---------- natural-language analytics ----------

class AskRequest(BaseModel):
    question: str


@router.post("/ask")
def ask(req: AskRequest):
    from app.intelligence.nl2sql import answer

    if not req.question.strip():
        raise HTTPException(422, "empty question")
    return answer(req.question.strip())


# ---------- vendors (resolved graph) ----------

# entity_kind -> (model, name column) that can link to a canonical vendor
LINKED = {
    "transaction": (Transaction, "counterparty"),
    "contract": (Contract, "counterparty"),
    "obligation": (Obligation, "counterparty"),
    "tax": (TaxItem, "counterparty"),
    "account": (Account, "institution_name"),
    "investment": (Investment, "holding_name"),
}


@router.get("/vendors")
def list_vendors(db: Session = Depends(get_db)):
    project = _default_project(db)
    canon = db.scalars(
        select(Vendor).where(Vendor.project_id == project.id, Vendor.is_canonical.is_(True))
        .order_by(Vendor.name)
    ).all()
    out = []
    for v in canon:
        counts, docs, total_paid = {}, set(), 0.0
        for kind, (model, _) in LINKED.items():
            rows = db.execute(
                select(model.document_id, getattr(model, "amount", model.id)).where(
                    model.canonical_vendor_id == v.id
                )
            ).all()
            if rows:
                counts[kind] = len(rows)
                for doc_id, _amt in rows:
                    docs.add(doc_id)
            if kind == "transaction":
                paid = db.scalar(
                    select(func.coalesce(func.sum(Transaction.amount), 0)).where(
                        Transaction.canonical_vendor_id == v.id, Transaction.direction == "debit"
                    )
                )
                total_paid = float(paid or 0)
        out.append({
            "id": v.id, "name": v.name, "address": v.address, "tax_id": v.tax_id,
            "document_count": len(docs), "counts": counts, "total_paid": total_paid,
        })
    return sorted(out, key=lambda x: x["document_count"], reverse=True)


@router.get("/vendors/{vendor_id}/references")
def vendor_references(vendor_id: int, db: Session = Depends(get_db)):
    v = db.get(Vendor, vendor_id)
    if not v:
        raise HTTPException(404, "vendor not found")
    refs = []
    for kind, (model, _) in LINKED.items():
        columns = ENTITY_DISPLAY[kind]
        rows = db.scalars(
            select(model).where(model.canonical_vendor_id == vendor_id).order_by(model.id)
        ).all()
        cited = set(
            db.execute(
                select(EntityCitation.entity_id, EntityCitation.field_name).where(
                    EntityCitation.entity_kind == kind,
                    EntityCitation.entity_id.in_([r.id for r in rows]) if rows else False,
                )
            ).all()
        )
        for r in rows:
            refs.append({
                "kind": kind, **_row_dict(r, columns),
                "cited_fields": [c for c in columns if (r.id, c) in cited],
                "columns": columns,
            })
    return {"vendor": {"id": v.id, "name": v.name, "address": v.address, "tax_id": v.tax_id}, "references": refs}


# ---------- page image assets ----------

@router.get("/assets/pages/{document_id}/{page_no}.png")
def page_image(document_id: int, page_no: int, db: Session = Depends(get_db)):
    page = db.get(DocumentPage, (document_id, page_no))
    if not page:
        raise HTTPException(404, "page not rendered")
    return FileResponse(page.image_path, media_type="image/png")
