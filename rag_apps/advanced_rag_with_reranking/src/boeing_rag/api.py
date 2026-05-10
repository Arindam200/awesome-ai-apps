from pathlib import Path
import json
import re
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func
from sqlalchemy.orm import Session

from boeing_rag.config import get_settings
from boeing_rag.db import SessionLocal, init_db
from boeing_rag.orm import ChunkRecord, DocumentRecord
from boeing_rag.retrieval import citation_from_result
from boeing_rag.schemas import (
    DocumentSummary,
    QueryRequest,
    QueryResponse,
    TableAudit,
    UploadJobStatus,
)
from boeing_rag.services import answer_generator, retriever
from boeing_rag.upload_jobs import UploadedPdf, create_upload_job, get_upload_job

app = FastAPI(title="Boeing RAG", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, int | str]:
    documents = session.query(DocumentRecord).count()
    chunks = session.query(ChunkRecord).count()
    return {"status": "ok", "documents": documents, "chunks": chunks}


@app.get("/documents", response_model=list[DocumentSummary])
def documents(session: Session = Depends(get_session)) -> list[DocumentSummary]:
    rows = (
        session.query(DocumentRecord, func.count(ChunkRecord.id))
        .outerjoin(ChunkRecord)
        .group_by(DocumentRecord.id)
        .order_by(DocumentRecord.report_year.nullslast(), DocumentRecord.file_name)
        .all()
    )
    return [
        DocumentSummary(
            id=doc.id,
            file_name=doc.file_name,
            report_year=doc.report_year,
            report_type=doc.report_type,
            title=doc.title,
            page_count=doc.page_count,
            status=doc.status,
            chunk_count=chunk_count,
        )
        for doc, chunk_count in rows
    ]


@app.api_route("/documents/{document_id}/file", methods=["GET", "HEAD"])
def document_file(
    document_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> FileResponse:
    document = session.get(DocumentRecord, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(document.file_path)
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.file_name,
        headers={
            "Content-Disposition": f'inline; filename="{document.file_name}"',
            **_asset_cors_headers(request),
        },
    )


@app.api_route("/chunks/{chunk_id}/page-image", methods=["GET", "HEAD"])
def chunk_page_image(
    chunk_id: str,
    request: Request,
    session: Session = Depends(get_session),
) -> FileResponse:
    chunk = session.get(ChunkRecord, chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail="Chunk not found")
    image_path = (chunk.metadata_json or {}).get("page_image_path")
    if not image_path:
        raise HTTPException(status_code=404, detail="No page image for this chunk")
    path = Path(image_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="Page image file not found")
    return FileResponse(path, media_type="image/png", headers=_asset_cors_headers(request))


def _asset_cors_headers(request: Request) -> dict[str, str]:
    origin = request.headers.get("origin")
    allowed_origin = origin if origin and _is_local_origin(origin) else "*"
    return {
        "Access-Control-Allow-Origin": allowed_origin,
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Expose-Headers": "Accept-Ranges, Content-Length, Content-Range",
        "Vary": "Origin",
    }


def _is_local_origin(origin: str) -> bool:
    return origin.startswith(("http://localhost", "http://127.0.0.1"))


@app.get("/tables", response_model=list[TableAudit])
def tables(session: Session = Depends(get_session)) -> list[TableAudit]:
    chunks = (
        session.query(ChunkRecord)
        .join(DocumentRecord)
        .filter(ChunkRecord.content_type == "table")
        .order_by(DocumentRecord.file_name, ChunkRecord.page_start, ChunkRecord.ordinal)
        .all()
    )
    audits: list[TableAudit] = []
    for chunk in chunks:
        meta = chunk.metadata_json or {}
        doc = chunk.document
        audits.append(
            TableAudit(
                chunk_id=chunk.id,
                document_id=doc.id,
                file_name=doc.file_name,
                report_year=doc.report_year,
                page_start=chunk.page_start,
                citation_label=chunk.citation_label,
                rows=meta.get("table_rows"),
                cols=meta.get("table_cols"),
                quality_score=meta.get("table_quality_score"),
                quality_status=meta.get("table_quality_status"),
                quality_issues=meta.get("table_quality_issues") or [],
                csv_path=meta.get("table_csv_path"),
                html_path=meta.get("table_html_path"),
                json_path=meta.get("table_json_path"),
                markdown_preview=chunk.text[:2500],
            )
        )
    return audits


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest, session: Session = Depends(get_session)) -> QueryResponse:
    results = retriever().retrieve(session, request.question, request.filters, request.top_k)
    return answer_generator().answer(request.question, results)


@app.post("/query/stream")
def query_stream(request: QueryRequest) -> StreamingResponse:
    def event_stream():
        session = SessionLocal()
        try:
            results = retriever().retrieve(session, request.question, request.filters, request.top_k)
            sources = [citation_from_result(result).model_dump() for result in results]
            yield _sse("sources", {"question": request.question, "sources": sources})
            for delta in answer_generator().stream_answer(request.question, results):
                yield _sse("delta", {"text": delta})
            yield _sse("done", {})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
        finally:
            session.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/ingest/upload", response_model=UploadJobStatus)
async def ingest_upload(
    files: list[UploadFile] = File(...),
    relative_paths: list[str] = Form(default=[]),
    force: bool = Form(False),
    render_pages: bool = Form(True),
) -> UploadJobStatus:
    settings = get_settings()
    pdf_uploads = [
        (index, file)
        for index, file in enumerate(files)
        if file.filename and file.filename.lower().endswith(".pdf")
    ]
    if not pdf_uploads:
        raise HTTPException(status_code=400, detail="Upload at least one PDF file")

    job_seed = f"{int(time.time() * 1000)}-{uuid4().hex[:8]}"
    job_dir = settings.upload_dir / job_seed
    job_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[UploadedPdf] = []
    for index, upload in pdf_uploads:
        relative_path = relative_paths[index] if index < len(relative_paths) else upload.filename
        safe_relative = _safe_relative_pdf_path(relative_path or upload.filename or f"upload-{index}.pdf")
        destination = job_dir / safe_relative
        if destination.exists():
            destination = destination.with_name(f"{destination.stem}-{index}{destination.suffix}")
            safe_relative = str(destination.relative_to(job_dir))
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            while chunk := await upload.read(1024 * 1024):
                handle.write(chunk)
        saved_files.append(
            UploadedPdf(
                key=f"{index}:{safe_relative}",
                name=Path(safe_relative).name,
                relative_path=safe_relative,
                path=destination,
            )
        )
        await upload.close()

    return create_upload_job(saved_files, force=force, render_pages=render_pages)


@app.get("/ingest/jobs/{job_id}", response_model=UploadJobStatus)
def ingest_job_status(job_id: str) -> UploadJobStatus:
    try:
        return get_upload_job(job_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Ingestion job not found") from None


def _safe_relative_pdf_path(value: str) -> str:
    parts = [
        _safe_name_for_path(part)
        for part in Path(value).parts
        if part not in {"", ".", "..", "/"}
    ]
    if not parts:
        parts = ["uploaded.pdf"]
    if not parts[-1].lower().endswith(".pdf"):
        parts[-1] = f"{parts[-1]}.pdf"
    return str(Path(*parts))


def _safe_name_for_path(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._ -]+", "_", value).strip(" .")
    return cleaned or "upload"


@app.post("/ingest")
def ingest(
    limit: int | None = None,
    force: bool = False,
    render_pages: bool = True,
    ocr: bool = False,
    auto_ocr: bool = True,
    vision: bool = False,
    vision_max_pages: int | None = None,
    vision_all_image_pages: bool = False,
) -> dict[str, object]:
    from boeing_rag.db import session_scope
    from boeing_rag.services import ingestion_pipeline

    settings = get_settings()
    settings.docling_do_ocr = ocr or settings.docling_do_ocr
    settings.auto_ocr = auto_ocr
    settings.visual_parse = vision or settings.visual_parse
    if vision_max_pages is not None:
        settings.visual_parse_max_pages = vision_max_pages
    settings.visual_parse_include_all_image_pages = (
        vision_all_image_pages or settings.visual_parse_include_all_image_pages
    )
    if settings.visual_parse:
        render_pages = True
    with session_scope() as session:
        document_ids = ingestion_pipeline().ingest_directory(
            session,
            settings.boeing_pdf_dir,
            force=force,
            limit=limit,
            render_pages=render_pages,
        )
    return {"ingested": document_ids, "count": len(document_ids)}
