from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import select

from boeing_rag.config import get_settings
from boeing_rag.db import init_db, session_scope
from boeing_rag.orm import ChunkRecord, DocumentRecord
from boeing_rag.schemas import QueryFilters

app = typer.Typer(help="Boeing report RAG commands.")
console = Console()


@app.command("init-db")
def init_database() -> None:
    init_db()
    console.print("[green]Database tables are ready.[/green]")


@app.command("reset-index")
def reset_index() -> None:
    from sqlalchemy import delete

    from boeing_rag.services import vector_store

    init_db()
    vector_store().delete_collection()
    with session_scope() as session:
        session.execute(delete(ChunkRecord))
        session.execute(delete(DocumentRecord))
    console.print("[green]Cleared Qdrant collection and document registry.[/green]")


@app.command()
def ingest(
    pdf_dir: Path | None = typer.Option(None, help="Directory containing Boeing PDFs."),
    force: bool = typer.Option(False, help="Re-parse and re-index existing files."),
    limit: int | None = typer.Option(None, help="Only ingest the first N PDFs."),
    render_pages: bool = typer.Option(True, help="Render page PNGs for visual citation review."),
    ocr: bool = typer.Option(False, help="Request OCR/VLM extraction for scanned/image-only PDFs."),
    auto_ocr: bool = typer.Option(True, help="Automatically enable OCR for low-text PDFs."),
    vision: bool = typer.Option(False, help="Use Nebius Qwen VL to parse visual/table evidence."),
    vision_max_pages: int | None = typer.Option(None, help="Maximum pages to send to the VLM."),
    vision_all_image_pages: bool = typer.Option(
        False, help="Send image-bearing pages too, not only low-text/review/fail-table pages."
    ),
) -> None:
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
    init_db()
    with session_scope() as session:
        ingested = ingestion_pipeline().ingest_directory(
            session=session,
            pdf_dir=pdf_dir or settings.boeing_pdf_dir,
            force=force,
            limit=limit,
            render_pages=render_pages,
        )
    console.print(f"[green]Done.[/green] Indexed/skipped {len(ingested)} document(s).")


@app.command()
def ask(
    question: str,
    report_type: str | None = typer.Option(None),
    report_year: int | None = typer.Option(None),
    report_year_min: int | None = typer.Option(None),
    report_year_max: int | None = typer.Option(None),
    content_type: str | None = typer.Option(None),
    top_k: int | None = typer.Option(None),
    json_output: bool = typer.Option(False, "--json", help="Print raw JSON response."),
) -> None:
    from boeing_rag.services import answer_generator, retriever

    filters = QueryFilters(
        report_type=report_type,
        report_year=report_year,
        report_year_min=report_year_min,
        report_year_max=report_year_max,
        content_type=content_type,
    )
    with session_scope() as session:
        results = retriever().retrieve(session, question, filters, top_k=top_k)
        response = answer_generator().answer(question, results)
    if json_output:
        console.print(json.dumps(response.model_dump(), indent=2))
        return
    console.print(response.answer)
    table = Table(title="Sources")
    table.add_column("#")
    table.add_column("Citation")
    table.add_column("Type")
    table.add_column("Score")
    for index, source in enumerate(response.sources, start=1):
        table.add_row(str(index), source.citation_label, source.content_type, f"{source.score:.3f}")
    console.print(table)


@app.command()
def list_documents() -> None:
    with session_scope() as session:
        documents = session.scalars(select(DocumentRecord).order_by(DocumentRecord.report_year)).all()
    table = Table(title="Indexed Documents")
    table.add_column("ID")
    table.add_column("Year")
    table.add_column("Type")
    table.add_column("Pages")
    table.add_column("Status")
    table.add_column("File")
    for doc in documents:
        table.add_row(
            doc.id,
            str(doc.report_year or ""),
            doc.report_type,
            str(doc.page_count),
            doc.status,
            doc.file_name,
        )
    console.print(table)


@app.command()
def stats() -> None:
    with session_scope() as session:
        docs = session.query(DocumentRecord).count()
        chunks = session.query(ChunkRecord).count()
        tables = session.query(ChunkRecord).filter(ChunkRecord.content_type == "table").count()
    console.print({"documents": docs, "chunks": chunks, "table_chunks": tables})


@app.command("table-audit")
def table_audit() -> None:
    with session_scope() as session:
        tables = (
            session.query(ChunkRecord)
            .filter(ChunkRecord.content_type == "table")
            .order_by(ChunkRecord.document_id, ChunkRecord.page_start, ChunkRecord.ordinal)
            .all()
        )
    table = Table(title="Table Extraction Audit")
    table.add_column("Citation")
    table.add_column("Shape")
    table.add_column("Status")
    table.add_column("Score")
    table.add_column("Issues")
    for chunk in tables:
        meta = chunk.metadata_json or {}
        table.add_row(
            chunk.citation_label,
            f"{meta.get('table_rows', '?')}x{meta.get('table_cols', '?')}",
            str(meta.get("table_quality_status", "unknown")),
            str(meta.get("table_quality_score", "")),
            ", ".join(meta.get("table_quality_issues") or []),
        )
    console.print(table)


if __name__ == "__main__":
    app()
