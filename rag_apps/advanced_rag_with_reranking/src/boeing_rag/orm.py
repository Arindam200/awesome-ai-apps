from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from boeing_rag.db import Base


class DocumentRecord(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(300), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    report_year: Mapped[int | None] = mapped_column(Integer, index=True)
    report_type: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="pending", index=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    chunks: Mapped[list["ChunkRecord"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class ChunkRecord(Base):
    __tablename__ = "chunks"
    __table_args__ = (UniqueConstraint("document_id", "ordinal", name="uq_document_chunk_ordinal"),)

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    contextual_text: Mapped[str | None] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(String(40), default="text", index=True)
    page_start: Mapped[int | None] = mapped_column(Integer, index=True)
    page_end: Mapped[int | None] = mapped_column(Integer, index=True)
    section_path: Mapped[list[str]] = mapped_column(JSON, default=list)
    citation_label: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(80), default="docling+pymupdf")
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    vector_id: Mapped[str | None] = mapped_column(String(120), index=True)
    score: Mapped[float | None] = mapped_column(Float)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[DocumentRecord] = relationship(back_populates="chunks")
