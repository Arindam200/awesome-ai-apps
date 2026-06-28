from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[str] = mapped_column(Text, default="running")  # running|succeeded|failed
    stage: Mapped[str | None] = mapped_column(Text)  # ingest|route|extract|normalize|analyze|synthesize|render|send
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    dry_run: Mapped[bool] = mapped_column(default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (UniqueConstraint("project_id", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    title: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(Text)
    doc_category: Mapped[str | None] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending|classified|extracting|extracted|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    page_no: Mapped[int] = mapped_column(Integer, primary_key=True)  # 1-based, matches Unsiloed page_no
    image_path: Mapped[str] = mapped_column(Text)
    width_px: Mapped[int] = mapped_column(Integer)
    height_px: Mapped[int] = mapped_column(Integer)
    width_pt: Mapped[float] = mapped_column(Float)
    height_pt: Mapped[float] = mapped_column(Float)

    document: Mapped[Document] = relationship(back_populates="pages")


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    kind: Mapped[str] = mapped_column(Text)  # classify|parse|extract
    schema_name: Mapped[str | None] = mapped_column(Text)
    unsiloed_job_id: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="queued")  # queued|submitted|succeeded|failed
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (UniqueConstraint("project_id", "dedup_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    signal_type: Mapped[str] = mapped_column(Text)  # feature_request|competitor_launch|ecosystem_mention|security|community
    source_kind: Mapped[str] = mapped_column(Text)  # github|hackernews|reddit|document|osv
    source_url: Mapped[str | None] = mapped_column(Text)
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str | None] = mapped_column(Text)  # low|medium|high|critical
    sentiment: Mapped[float | None] = mapped_column(Float)  # -1..1
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float | None] = mapped_column(Float)
    dedup_key: Mapped[str] = mapped_column(Text)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    citations: Mapped[list["SignalCitation"]] = relationship(back_populates="signal")


class SignalCitation(Base):
    __tablename__ = "signal_citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    signal_id: Mapped[int] = mapped_column(ForeignKey("signals.id", ondelete="CASCADE"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    field_name: Mapped[str | None] = mapped_column(Text)
    page_no: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list] = mapped_column(JSONB)  # stored verbatim as Unsiloed returned it
    snippet: Mapped[str | None] = mapped_column(Text)

    signal: Mapped[Signal] = relationship(back_populates="citations")


class TrendMetric(Base):
    __tablename__ = "trend_metrics"
    __table_args__ = (UniqueConstraint("project_id", "metric_key", "period_start"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    metric_key: Mapped[str] = mapped_column(Text)  # 'mentions:wasm', 'sentiment:overall', 'type:feature_request'
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    value: Mapped[float] = mapped_column(Float)
    prior_value: Mapped[float | None] = mapped_column(Float)


class Brief(Base):
    __tablename__ = "briefs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    run_id: Mapped[int | None] = mapped_column(ForeignKey("pipeline_runs.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    brief_json: Mapped[dict] = mapped_column(JSONB)
    html: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resend_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
