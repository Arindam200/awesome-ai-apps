export type DocumentSummary = {
  id: string;
  file_name: string;
  report_year: number | null;
  report_type: string;
  title: string | null;
  page_count: number;
  status: string;
  chunk_count: number;
};

export type QueryFilters = {
  document_id?: string | null;
  report_year?: number | null;
  report_year_min?: number | null;
  report_year_max?: number | null;
  report_type?: string | null;
  content_type?: string | null;
};

export type SourceCitation = {
  chunk_id: string;
  document_id: string;
  file_name: string;
  report_year: number | null;
  report_type: string;
  page_start: number | null;
  page_end: number | null;
  citation_label: string;
  content_type: string;
  text: string;
  score: number;
  page_image_path: string | null;
  section_path: string[];
  pdf_url: string | null;
  page_image_url: string | null;
};

export type QueryResponse = {
  question: string;
  answer: string;
  sources: SourceCitation[];
};

export type TableAudit = {
  chunk_id: string;
  document_id: string;
  file_name: string;
  report_year: number | null;
  page_start: number | null;
  citation_label: string;
  rows: number | null;
  cols: number | null;
  quality_score: number | null;
  quality_status: string | null;
  quality_issues: string[];
  csv_path: string | null;
  html_path: string | null;
  json_path: string | null;
  markdown_preview: string;
};

export type UploadJobFile = {
  name: string;
  relative_path: string | null;
  status: string;
  document_id: string | null;
  error: string | null;
};

export type UploadJobStatus = {
  job_id: string;
  status: string;
  total_files: number;
  processed_files: number;
  failed_files: number;
  current_file: string | null;
  message: string;
  files: UploadJobFile[];
  started_at: number;
  finished_at: number | null;
};
