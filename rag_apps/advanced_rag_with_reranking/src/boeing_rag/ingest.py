from __future__ import annotations

from pathlib import Path

import fitz
from rich.console import Console
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from boeing_rag.chunking import ChunkBuilder, ChunkPayload
from boeing_rag.config import Settings
from boeing_rag.contextual import Contextualizer
from boeing_rag.embeddings import EmbeddingProvider, batched
from boeing_rag.orm import ChunkRecord, DocumentRecord
from boeing_rag.parser import DoclingPdfParser, ParsedDocument
from boeing_rag.sparse import SparseEmbeddingProvider
from boeing_rag.utils import sha256_file, stable_uuid
from boeing_rag.vision import VisionParser
from boeing_rag.vector_store import VectorStore


class IngestionPipeline:
    def __init__(
        self,
        settings: Settings,
        parser: DoclingPdfParser,
        chunk_builder: ChunkBuilder,
        embeddings: EmbeddingProvider,
        sparse_embeddings: SparseEmbeddingProvider,
        vector_store: VectorStore,
        contextualizer: Contextualizer,
        vision_parser: VisionParser | None = None,
        console: Console | None = None,
    ) -> None:
        self.settings = settings
        self.parser = parser
        self.chunk_builder = chunk_builder
        self.embeddings = embeddings
        self.sparse_embeddings = sparse_embeddings
        self.vector_store = vector_store
        self.contextualizer = contextualizer
        self.vision_parser = vision_parser
        self.console = console or Console()

    def ingest_directory(
        self,
        session: Session,
        pdf_dir: Path,
        force: bool = False,
        limit: int | None = None,
        render_pages: bool = True,
    ) -> list[str]:
        paths = sorted(pdf_dir.glob("*.pdf"))
        if limit:
            paths = paths[:limit]
        ingested: list[str] = []
        for path in paths:
            document_id = self.ingest_file(session, path, force=force, render_pages=render_pages)
            if document_id:
                ingested.append(document_id)
                session.commit()
        return ingested

    def ingest_file(
        self,
        session: Session,
        pdf_path: Path,
        force: bool = False,
        render_pages: bool = True,
    ) -> str | None:
        file_hash = sha256_file(pdf_path)
        existing = session.scalar(select(DocumentRecord).where(DocumentRecord.file_hash == file_hash))
        if existing and not force and existing.status == "indexed":
            self.console.print(f"[yellow]Skipping[/yellow] {pdf_path.name}; already indexed as {existing.id}")
            return existing.id

        do_ocr = self._should_ocr(pdf_path)
        ocr_label = " with OCR" if do_ocr else ""
        self.console.print(f"[cyan]Parsing[/cyan] {pdf_path.name}{ocr_label}")
        parsed = self.parser.parse(pdf_path, render_pages=render_pages, do_ocr=do_ocr)

        self._replace_document(session, parsed)
        chunks = self.chunk_builder.build(parsed)
        chunks.extend(self._build_visual_chunks(parsed, len(chunks)))
        chunks = self.contextualizer.contextualize(parsed, chunks)
        chunk_records = self._insert_chunks(session, parsed, chunks)
        session.flush()

        self._index_chunks(session, parsed, chunk_records)
        document = session.get(DocumentRecord, parsed.document_id)
        if document:
            document.status = "indexed"
        self.console.print(
            f"[green]Indexed[/green] {pdf_path.name}: {len(chunk_records)} chunks, "
            f"{parsed.page_count} pages, {len(parsed.tables)} tables"
        )
        return parsed.document_id

    def _should_ocr(self, pdf_path: Path) -> bool:
        if self.settings.docling_do_ocr:
            return True
        if not self.settings.auto_ocr:
            return False
        try:
            with fitz.open(pdf_path) as doc:
                sample_count = min(len(doc), 5)
                if sample_count == 0:
                    return False
                text_chars = sum(len((doc[index].get_text("text") or "").strip()) for index in range(sample_count))
                avg_chars = text_chars / sample_count
                return avg_chars < self.settings.min_page_text_chars_for_ocr
        except Exception:
            return False

    def _build_visual_chunks(self, parsed: ParsedDocument, start_ordinal: int) -> list[ChunkPayload]:
        if not self.vision_parser or not self.vision_parser.enabled():
            return []

        visual_chunks: list[ChunkPayload] = []
        selected_pages = self.vision_parser.select_pages(parsed)
        if not selected_pages:
            self.console.print("[yellow]Visual parsing enabled, but no candidate pages were selected.[/yellow]")
            return []

        self.console.print(f"[cyan]Visual parsing[/cyan] {len(selected_pages)} page(s)")
        for offset, page in enumerate(selected_pages, start=1):
            try:
                visual_text = self.vision_parser.parse_page(parsed, page)
            except Exception as exc:
                self.console.print(f"[red]VLM failed[/red] {parsed.file_name} p. {page.page_number}: {exc}")
                continue
            if not visual_text:
                continue
            ordinal = start_ordinal + offset
            text = f"Visual extraction for page {page.page_number}\n\n{visual_text}"
            chunk_id = f"{parsed.document_id}:v{ordinal:05d}:{stable_uuid(text)[:8]}"
            visual_chunks.append(
                ChunkPayload(
                    id=chunk_id,
                    document_id=parsed.document_id,
                    ordinal=ordinal,
                    text=text,
                    raw_text=text,
                    contextual_text=text,
                    content_type="image",
                    page_start=page.page_number,
                    page_end=page.page_number,
                    section_path=["Visual extraction"],
                    citation_label=f"{parsed.file_name}, p. {page.page_number}, visual extraction",
                    extraction_method=f"nebius_vlm:{self.settings.nebius_vision_model}",
                    token_estimate=max(1, len(text) // 4),
                    metadata={
                        "page_image_path": page.image_path,
                        "visual_model": self.settings.nebius_vision_model,
                    },
                )
            )
        return visual_chunks

    def _replace_document(self, session: Session, parsed: ParsedDocument) -> None:
        existing = session.scalar(select(DocumentRecord).where(DocumentRecord.id == parsed.document_id))
        if existing:
            self.vector_store.delete_document(existing.id)
            session.execute(delete(ChunkRecord).where(ChunkRecord.document_id == existing.id))
            session.delete(existing)
            session.flush()

        session.add(
            DocumentRecord(
                id=parsed.document_id,
                file_name=parsed.file_name,
                file_path=parsed.file_path,
                file_hash=parsed.file_hash,
                report_year=parsed.report_year,
                report_type=parsed.report_type,
                title=parsed.title,
                page_count=parsed.page_count,
                status="parsed",
                metadata_json=parsed.metadata,
            )
        )

    def _insert_chunks(
        self,
        session: Session,
        parsed: ParsedDocument,
        chunks: list[ChunkPayload],
    ) -> list[ChunkRecord]:
        records: list[ChunkRecord] = []
        for chunk in chunks:
            record = ChunkRecord(
                id=chunk.id,
                document_id=parsed.document_id,
                ordinal=chunk.ordinal,
                text=chunk.text,
                raw_text=chunk.raw_text,
                contextual_text=chunk.contextual_text,
                content_type=chunk.content_type,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                section_path=chunk.section_path,
                citation_label=chunk.citation_label,
                extraction_method=chunk.extraction_method,
                token_estimate=chunk.token_estimate,
                vector_id=stable_uuid(chunk.id),
                metadata_json=chunk.metadata,
            )
            records.append(record)
            session.add(record)
        return records

    def _index_chunks(
        self,
        session: Session,
        parsed: ParsedDocument,
        chunk_records: list[ChunkRecord],
    ) -> None:
        if not chunk_records:
            return
        index_texts = [chunk.contextual_text or chunk.text for chunk in chunk_records]
        dense_vectors: list[list[float]] = []
        sparse_vectors = []
        for texts in batched(index_texts, 64):
            dense_vectors.extend(self.embeddings.embed_texts(texts))
            sparse_vectors.extend(self.sparse_embeddings.embed_texts(texts))
        self.vector_store.ensure_collection(len(dense_vectors[0]))
        document = session.get(DocumentRecord, parsed.document_id)
        if not document:
            raise RuntimeError(f"Document {parsed.document_id} missing after insert")
        self.vector_store.upsert_chunks(chunk_records, {document.id: document}, dense_vectors, sparse_vectors)
