"""Financial Document OS data model.

Typed entity tables (NL->SQL friendly, type-enforced for anomaly math) + one
shared entity_citations table keyed by (entity_kind, entity_id, field_name)
that grounds every displayed value back to a page + bbox in the source PDF.
"""

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

# ---------- infra (reused shape from maintainer-brief) ----------


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    status: Mapped[str] = mapped_column(Text, default="running")  # running|succeeded|failed
    stage: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
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
    status: Mapped[str] = mapped_column(Text, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pages: Mapped[list["DocumentPage"]] = relationship(back_populates="document")


class DocumentPage(Base):
    __tablename__ = "document_pages"

    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), primary_key=True)
    page_no: Mapped[int] = mapped_column(Integer, primary_key=True)
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
    status: Mapped[str] = mapped_column(Text, default="queued")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    raw_response: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------- shared citation (grounds every field to a bbox) ----------


class EntityCitation(Base):
    __tablename__ = "entity_citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    entity_kind: Mapped[str] = mapped_column(Text)  # account|transaction|vendor|contract|investment|obligation|tax
    entity_id: Mapped[int] = mapped_column(Integer)
    field_name: Mapped[str] = mapped_column(Text)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    page_no: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[dict] = mapped_column(JSONB)  # verbatim {bbox:[x0,y0,x1,y1], page, page_width, page_height}
    extraction_score: Mapped[float | None] = mapped_column(Float)
    snippet: Mapped[str | None] = mapped_column(Text)


# ---------- seven typed entity tables ----------


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int | None] = mapped_column(ForeignKey("documents.id"))
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    tax_id: Mapped[str | None] = mapped_column(Text)
    is_canonical: Mapped[bool] = mapped_column(Boolean, default=False)
    canonical_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    needs_review: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    institution_name: Mapped[str | None] = mapped_column(Text)
    account_holder: Mapped[str | None] = mapped_column(Text)
    account_number_masked: Mapped[str | None] = mapped_column(Text)
    account_type: Mapped[str | None] = mapped_column(Text)
    currency: Mapped[str | None] = mapped_column(Text)
    opening_balance: Mapped[float | None] = mapped_column(Numeric(18, 2))
    closing_balance: Mapped[float | None] = mapped_column(Numeric(18, 2))
    statement_period_start: Mapped[date | None] = mapped_column(Date)
    statement_period_end: Mapped[date | None] = mapped_column(Date)
    canonical_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"))
    txn_date: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    counterparty: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    direction: Mapped[str | None] = mapped_column(Text)  # debit|credit
    balance_after: Mapped[float | None] = mapped_column(Numeric(18, 2))
    category: Mapped[str | None] = mapped_column(Text)
    canonical_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    contract_type: Mapped[str | None] = mapped_column(Text)  # vendor_contract|loan_agreement
    counterparty: Mapped[str | None] = mapped_column(Text)
    contract_value: Mapped[float | None] = mapped_column(Numeric(18, 2))
    currency: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    renewal_terms: Mapped[str | None] = mapped_column(Text)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    # loan-specific
    principal_amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    interest_rate: Mapped[float | None] = mapped_column(Numeric(8, 4))
    maturity_date: Mapped[date | None] = mapped_column(Date)
    company_address: Mapped[str | None] = mapped_column(Text)
    canonical_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Investment(Base):
    __tablename__ = "investments"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    holding_name: Mapped[str | None] = mapped_column(Text)
    ticker: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[float | None] = mapped_column(Numeric(18, 4))
    cost_basis: Mapped[float | None] = mapped_column(Numeric(18, 2))
    current_value: Mapped[float | None] = mapped_column(Numeric(18, 2))
    ownership_percentage: Mapped[float | None] = mapped_column(Numeric(8, 4))
    valuation_date: Mapped[date | None] = mapped_column(Date)
    canonical_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Obligation(Base):
    __tablename__ = "obligations"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    obligation_type: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    counterparty: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    due_date: Mapped[date | None] = mapped_column(Date)
    canonical_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TaxItem(Base):
    __tablename__ = "tax_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    tax_year: Mapped[int | None] = mapped_column(Integer)
    jurisdiction: Mapped[str | None] = mapped_column(Text)
    filing_type: Mapped[str | None] = mapped_column(Text)
    line_item: Mapped[str | None] = mapped_column(Text)
    counterparty: Mapped[str | None] = mapped_column(Text)
    amount: Mapped[float | None] = mapped_column(Numeric(18, 2))
    canonical_vendor_id: Mapped[int | None] = mapped_column(ForeignKey("vendors.id"))
    confidence: Mapped[float | None] = mapped_column(Float)
    source_page: Mapped[int | None] = mapped_column(Integer)
    raw_fields: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------- analysis + edits ----------


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    rule: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text)  # low|medium|high
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    entity_refs: Mapped[list] = mapped_column(JSONB, default=list)  # [{entity_kind, entity_id}]
    evidence_citation_ids: Mapped[list] = mapped_column(JSONB, default=list)
    source: Mapped[str] = mapped_column(Text, default="rule")  # rule|llm
    status: Mapped[str] = mapped_column(Text, default="open")  # open|dismissed
    dedup_key: Mapped[str] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    __table_args__ = (UniqueConstraint("project_id", "dedup_key"),)


class DocumentEdit(Base):
    __tablename__ = "document_edits"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    field_name: Mapped[str | None] = mapped_column(Text)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list] = mapped_column(JSONB, default=list)  # edit_request items sent
    pdf_url: Mapped[str | None] = mapped_column(Text)
    edited_file_path: Mapped[str | None] = mapped_column(Text)
    new_job_id: Mapped[str | None] = mapped_column(Text)
    original_size: Mapped[int | None] = mapped_column(Integer)
    edited_size: Mapped[int | None] = mapped_column(Integer)
    items_processed: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(Text, default="pending")  # pending|succeeded|failed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# entity_kind -> ORM class, used by normalization, citations API, NL->SQL evidence
ENTITY_MODELS = {
    "account": Account,
    "transaction": Transaction,
    "vendor": Vendor,
    "contract": Contract,
    "investment": Investment,
    "obligation": Obligation,
    "tax": TaxItem,
}
