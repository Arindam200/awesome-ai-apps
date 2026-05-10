from pydantic import BaseModel, Field


class QueryFilters(BaseModel):
    document_id: str | None = None
    file_name: str | None = None
    report_year: int | None = None
    report_year_min: int | None = None
    report_year_max: int | None = None
    report_type: str | None = None
    content_type: str | None = None


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)
    filters: QueryFilters = Field(default_factory=QueryFilters)
    top_k: int | None = None


class SourceCitation(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    report_year: int | None
    report_type: str
    page_start: int | None
    page_end: int | None
    citation_label: str
    content_type: str
    text: str
    score: float
    page_image_path: str | None = None
    section_path: list[str] = Field(default_factory=list)
    pdf_url: str | None = None
    page_image_url: str | None = None


class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list[SourceCitation]


class DocumentSummary(BaseModel):
    id: str
    file_name: str
    report_year: int | None
    report_type: str
    title: str | None
    page_count: int
    status: str
    chunk_count: int


class TableAudit(BaseModel):
    chunk_id: str
    document_id: str
    file_name: str
    report_year: int | None
    page_start: int | None
    citation_label: str
    rows: int | None
    cols: int | None
    quality_score: float | None
    quality_status: str | None
    quality_issues: list[str]
    csv_path: str | None
    html_path: str | None
    json_path: str | None
    markdown_preview: str


class UploadJobFile(BaseModel):
    name: str
    relative_path: str | None = None
    status: str
    document_id: str | None = None
    error: str | None = None


class UploadJobStatus(BaseModel):
    job_id: str
    status: str
    total_files: int
    processed_files: int
    failed_files: int
    current_file: str | None = None
    message: str
    files: list[UploadJobFile]
    started_at: float
    finished_at: float | None = None
