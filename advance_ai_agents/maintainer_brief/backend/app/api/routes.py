"""All API routes. Small app — one router file beats six."""

import re
import threading

import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.connectors.documents import ALLOWED_SUFFIXES, register_document
from app.connectors.github_conn import repo_metadata
from app.db import SessionLocal, get_db
from app.feedback import verify as verify_feedback
from app.models import (
    Brief,
    Document,
    DocumentPage,
    Feedback,
    PipelineRun,
    Project,
    Signal,
    SignalCitation,
)
from app.newsletter.render import render_brief_html, section_flags
from app.newsletter.send import build_subject, send_brief
from app.pipeline.orchestrator import run_pipeline
from app.scheduler import schedule_project, unschedule_project

router = APIRouter()


# ---------- projects ----------

def _project_dict(p: Project) -> dict:
    return {"id": p.id, "slug": p.slug, "name": p.name, "config": p.config}


@router.get("/projects")
def list_projects(db: Session = Depends(get_db)):
    projects = db.scalars(select(Project).order_by(Project.created_at)).all()
    return [_project_dict(p) for p in projects]


@router.get("/projects/{project_id}")
def get_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    return _project_dict(p)


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60] or "project"


def _unique_slug(db: Session, base: str) -> str:
    slug, i = base, 2
    while db.scalar(select(Project.id).where(Project.slug == slug)):
        slug = f"{base}-{i}"
        i += 1
    return slug


class ProjectCreate(BaseModel):
    name: str
    config: dict  # github/keywords/competitors/community/security/newsletter/documents


@router.post("/projects")
def create_project(req: ProjectCreate, db: Session = Depends(get_db)):
    if not req.name.strip():
        raise HTTPException(422, "name is required")
    project = Project(slug=_unique_slug(db, _slugify(req.name)), name=req.name.strip(), config=req.config or {})
    db.add(project)
    db.commit()
    schedule_project(project)
    return _project_dict(project)


class ProjectUpdate(BaseModel):
    name: str | None = None
    config: dict | None = None


@router.patch("/projects/{project_id}")
def update_project(project_id: int, req: ProjectUpdate, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    if req.name:
        p.name = req.name.strip()
    if req.config is not None:
        p.config = _deep_merge(p.config or {}, req.config)
    db.commit()
    schedule_project(p)
    return _project_dict(p)


def _deep_merge(base: dict, patch: dict) -> dict:
    out = dict(base)
    for k, v in patch.items():
        out[k] = _deep_merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


@router.delete("/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    p = db.get(Project, project_id)
    if not p:
        raise HTTPException(404, "project not found")
    slug = p.slug
    # children (signals/citations/documents/briefs/runs) cascade by project_id cleanup
    db.query(SignalCitation).filter(
        SignalCitation.signal_id.in_(select(Signal.id).where(Signal.project_id == project_id))
    ).delete(synchronize_session=False)
    for model in (Signal, Document, Brief, PipelineRun):
        db.query(model).filter(model.project_id == project_id).delete(synchronize_session=False)
    db.delete(p)
    db.commit()
    unschedule_project(slug)
    return {"status": "deleted"}


# ---------- github helpers ----------

@router.get("/github/repo")
def github_repo(repo: str):
    repo = repo.strip().removeprefix("https://github.com/").strip("/")
    if repo.count("/") != 1:
        raise HTTPException(422, "expected 'org/name'")
    try:
        meta = repo_metadata(repo)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(404, "repository not found")
        raise HTTPException(502, f"github error: {e.response.status_code}")
    # derive starter keywords from topics + repo name words
    words = re.split(r"[-_/]", meta["name"])
    keywords = sorted({*(t for t in meta["topics"]), *(w.lower() for w in words if len(w) > 2)})
    meta["suggested_keywords"] = keywords[:8]
    return meta


# ---------- runs ----------

class RunRequest(BaseModel):
    project_id: int
    dry_run: bool = True


def _run_in_thread(run_id: int):
    db = SessionLocal()
    try:
        run = db.get(PipelineRun, run_id)
        run_pipeline(db, run)
    finally:
        db.close()


@router.post("/runs")
def create_run(req: RunRequest, db: Session = Depends(get_db)):
    project = db.get(Project, req.project_id)
    if not project:
        raise HTTPException(404, "project not found")
    active = db.scalar(
        select(PipelineRun.id).where(
            PipelineRun.project_id == project.id, PipelineRun.status == "running"
        )
    )
    if active:
        raise HTTPException(409, f"run {active} already in progress")
    run = PipelineRun(project_id=project.id, dry_run=req.dry_run, stats={})
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
        "id": run.id,
        "status": run.status,
        "stage": run.stage,
        "stats": run.stats,
        "error": run.error,
        "dry_run": run.dry_run,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
    }


# ---------- signals ----------

@router.get("/signals")
def list_signals(
    project_id: int,
    signal_type: str | None = None,
    source_kind: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = (
        select(Signal)
        .options(selectinload(Signal.citations))
        .where(Signal.project_id == project_id)
        .order_by(Signal.observed_at.desc())
        .limit(min(limit, 500))
    )
    if signal_type:
        q = q.where(Signal.signal_type == signal_type)
    if source_kind:
        q = q.where(Signal.source_kind == source_kind)
    return [_signal_dict(s) for s in db.scalars(q)]


def _signal_dict(s: Signal, include_citations: bool = False) -> dict:
    d = {
        "id": s.id,
        "signal_type": s.signal_type,
        "source_kind": s.source_kind,
        "source_url": s.source_url,
        "document_id": s.document_id,
        "title": s.title,
        "summary": s.summary,
        "category": s.category,
        "urgency": s.urgency,
        "sentiment": s.sentiment,
        "keywords": s.keywords,
        "confidence": s.confidence,
        "observed_at": s.observed_at,
        "citation_count": len(s.citations),
    }
    if include_citations:
        d["payload"] = s.payload
        d["citations"] = [
            {
                "id": c.id,
                "document_id": c.document_id,
                "field_name": c.field_name,
                "page_no": c.page_no,
                "bbox": c.bbox,
                "snippet": c.snippet,
            }
            for c in s.citations
        ]
    return d


@router.get("/signals/{signal_id}")
def get_signal(signal_id: int, db: Session = Depends(get_db)):
    signal = db.get(Signal, signal_id, options=[selectinload(Signal.citations)])
    if not signal:
        raise HTTPException(404, "signal not found")
    result = _signal_dict(signal, include_citations=True)
    if signal.document_id:
        doc = db.get(Document, signal.document_id)
        pages = db.scalars(
            select(DocumentPage).where(DocumentPage.document_id == doc.id).order_by(DocumentPage.page_no)
        ).all()
        result["document"] = {
            "id": doc.id,
            "title": doc.title,
            "source_url": doc.source_url,
            "doc_category": doc.doc_category,
            "page_count": doc.page_count,
            "pages": [
                {
                    "page_no": p.page_no,
                    "width_px": p.width_px,
                    "height_px": p.height_px,
                    "width_pt": p.width_pt,
                    "height_pt": p.height_pt,
                }
                for p in pages
            ],
        }
    return result


# ---------- briefs ----------

@router.get("/briefs")
def list_briefs(project_id: int, db: Session = Depends(get_db)):
    briefs = db.scalars(
        select(Brief).where(Brief.project_id == project_id).order_by(Brief.created_at.desc()).limit(20)
    ).all()
    return [
        {
            "id": b.id,
            "period_start": b.period_start,
            "period_end": b.period_end,
            "headline": (b.brief_json or {}).get("headline"),
            "sent_at": b.sent_at,
            "created_at": b.created_at,
        }
        for b in briefs
    ]


@router.get("/briefs/latest")
def latest_brief(project_id: int, db: Session = Depends(get_db)):
    brief = db.scalar(
        select(Brief).where(Brief.project_id == project_id).order_by(Brief.created_at.desc()).limit(1)
    )
    if not brief:
        raise HTTPException(404, "no briefs yet")
    return _brief_dict(brief)


@router.get("/briefs/{brief_id}")
def get_brief(brief_id: int, db: Session = Depends(get_db)):
    brief = db.get(Brief, brief_id)
    if not brief:
        raise HTTPException(404, "brief not found")
    return _brief_dict(brief)


def _brief_dict(b: Brief) -> dict:
    return {
        "id": b.id,
        "project_id": b.project_id,
        "period_start": b.period_start,
        "period_end": b.period_end,
        "brief_json": b.brief_json,
        "html": b.html,
        "sent_at": b.sent_at,
        "resend_id": b.resend_id,
        "created_at": b.created_at,
    }


@router.get("/briefs/{brief_id}/html")
def brief_html(brief_id: int, db: Session = Depends(get_db)):
    """Live-rendered email HTML honoring the project's current section toggles."""
    brief = db.get(Brief, brief_id)
    if not brief:
        raise HTTPException(404, "brief not found")
    project = db.get(Project, brief.project_id)
    return {
        "html": render_brief_html(db, project, brief),
        "subject": build_subject(project, brief),
        "sections": section_flags(project),
        "default_recipients": (project.config.get("newsletter") or {}).get("recipients") or [],
    }


class SendRequest(BaseModel):
    recipients: list[str] | None = None
    subject: str | None = None
    from_name: str | None = None
    test: bool = False


@router.post("/briefs/{brief_id}/send")
def send_brief_endpoint(brief_id: int, req: SendRequest, db: Session = Depends(get_db)):
    brief = db.get(Brief, brief_id)
    if not brief:
        raise HTTPException(404, "brief not found")
    project = db.get(Project, brief.project_id)
    html = render_brief_html(db, project, brief)  # honor current section toggles
    try:
        result = send_brief(
            db, project, brief,
            recipients=req.recipients, subject=req.subject,
            from_name=req.from_name, html=html, test=req.test,
        )
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(502, f"resend error: {e.response.status_code} {e.response.text[:200]}")
    return result


# ---------- documents ----------

@router.get("/documents")
def list_documents(project_id: int, db: Session = Depends(get_db)):
    docs = db.scalars(
        select(Document).where(Document.project_id == project_id).order_by(Document.created_at.desc())
    ).all()
    counts = dict(
        db.execute(
            select(Signal.document_id, func.count(Signal.id))
            .where(Signal.project_id == project_id, Signal.document_id.isnot(None))
            .group_by(Signal.document_id)
        ).all()
    )
    return [
        {
            "id": d.id,
            "title": d.title,
            "source_url": d.source_url,
            "doc_category": d.doc_category,
            "page_count": d.page_count,
            "status": d.status,
            "signal_count": counts.get(d.id, 0),
            "created_at": d.created_at,
        }
        for d in docs
    ]


@router.post("/documents/upload")
async def upload_document(project_id: int, file: UploadFile, db: Session = Depends(get_db)):
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(404, "project not found")
    from pathlib import Path

    if Path(file.filename or "").suffix.lower() not in ALLOWED_SUFFIXES:
        raise HTTPException(422, f"unsupported file type; allowed: {sorted(ALLOWED_SUFFIXES)}")
    content = await file.read()
    if len(content) > 100 * 1024 * 1024:
        raise HTTPException(413, "file exceeds 100MB Unsiloed limit")
    doc = register_document(db, project, content=content, filename=file.filename or "upload.pdf")
    if doc is None:
        return {"status": "duplicate", "detail": "this exact file was already ingested"}
    return {"status": "created", "document_id": doc.id}


# ---------- page image assets ----------

@router.get("/assets/pages/{document_id}/{page_no}.png")
def page_image(document_id: int, page_no: int, db: Session = Depends(get_db)):
    page = db.get(DocumentPage, (document_id, page_no))
    if not page:
        raise HTTPException(404, "page not rendered")
    return FileResponse(page.image_path, media_type="image/png")


# ---------- feedback (one-click 👍/👎 from the email) ----------

_THANKS_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Thanks</title></head>
<body style="margin:0;font-family:Helvetica,Arial,sans-serif;background:#f6f7f9;color:#2b2926">
<div style="max-width:420px;margin:18vh auto;text-align:center;background:#fff;border:1px solid #e5e7eb;border-top:3px solid #3553ff;border-radius:6px;padding:40px 32px">
<div style="font-size:34px">{emoji}</div>
<h2 style="margin:14px 0 6px;font-size:20px">Thanks — noted.</h2>
<p style="margin:0;color:#6b6f76;font-size:14px">{msg}</p>
</div></body></html>"""


@router.get("/feedback", response_class=HTMLResponse)
def record_feedback(t: str, db: Session = Depends(get_db)):
    data = verify_feedback(t)
    if not data:
        return HTMLResponse(
            _THANKS_HTML.format(emoji="⚠️", msg="This feedback link is invalid or expired."),
            status_code=400,
        )
    brief = db.get(Brief, data["brief_id"])
    # upsert on (brief_id, item_kind, item_ref) so re-clicks update, not duplicate
    existing = db.scalar(
        select(Feedback).where(
            Feedback.brief_id == data["brief_id"],
            Feedback.item_kind == data["kind"],
            Feedback.item_ref == str(data["ref"]),
        )
    )
    if existing:
        existing.vote = data["vote"]
    else:
        db.add(
            Feedback(
                brief_id=data["brief_id"],
                project_id=brief.project_id if brief else None,
                item_kind=data["kind"],
                item_ref=str(data["ref"]),
                vote=data["vote"],
            )
        )
    db.commit()
    up = data["vote"] == "up"
    return HTMLResponse(
        _THANKS_HTML.format(
            emoji="👍" if up else "👎",
            msg="Glad it was useful." if up else "We'll tune this kind of item down.",
        )
    )


@router.get("/feedback/summary")
def feedback_summary(brief_id: int, db: Session = Depends(get_db)):
    rows = list(db.scalars(select(Feedback).where(Feedback.brief_id == brief_id)))
    up = sum(1 for r in rows if r.vote == "up")
    down = sum(1 for r in rows if r.vote == "down")
    by_item = [
        {"kind": r.item_kind, "ref": r.item_ref, "vote": r.vote}
        for r in sorted(rows, key=lambda r: r.created_at)
    ]
    return {"brief_id": brief_id, "up": up, "down": down, "total": len(rows), "items": by_item}
