import React from "react";
import { createRoot } from "react-dom/client";
import {
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Database,
  FileSearch,
  Filter,
  FolderOpen,
  Loader2,
  RefreshCw,
  Search,
  Send,
  SlidersHorizontal,
  Upload,
} from "lucide-react";
import { assetUrl, getDocuments, getTables, getUploadJob, ingest, streamQuestion, uploadDocuments } from "./api";
import { PdfChunkPreview } from "./PdfChunkPreview";
import type { DocumentSummary, QueryResponse, SourceCitation, TableAudit, UploadJobStatus } from "./types";
import "./styles.css";

const exampleQuestions = [
  "Compare Boeing's sustainability priorities in 2021 and 2024.",
  "What does Boeing say about sustainable aviation fuel?",
  "Where does Boeing discuss 737 MAX risks?",
  "Summarize emissions-related goals and cite the pages.",
];

function App() {
  const [documents, setDocuments] = React.useState<DocumentSummary[]>([]);
  const [selectedDocument, setSelectedDocument] = React.useState("");
  const [reportType, setReportType] = React.useState("");
  const [yearFrom, setYearFrom] = React.useState("");
  const [yearTo, setYearTo] = React.useState("");
  const [contentType, setContentType] = React.useState("");
  const [question, setQuestion] = React.useState(exampleQuestions[1]);
  const [topK, setTopK] = React.useState(8);
  const [response, setResponse] = React.useState<QueryResponse | null>(null);
  const [tables, setTables] = React.useState<TableAudit[]>([]);
  const [showTables, setShowTables] = React.useState(false);
  const [selectedSource, setSelectedSource] = React.useState(0);
  const [loading, setLoading] = React.useState(false);
  const [streaming, setStreaming] = React.useState(false);
  const [ingesting, setIngesting] = React.useState(false);
  const [error, setError] = React.useState("");
  const [activeView, setActiveView] = React.useState<"ask" | "upload">("ask");

  const refreshDocuments = React.useCallback(async () => {
    try {
      const [nextDocuments, nextTables] = await Promise.all([getDocuments(), getTables()]);
      setDocuments(nextDocuments);
      setTables(nextTables);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load documents");
    }
  }, []);

  React.useEffect(() => {
    refreshDocuments();
  }, [refreshDocuments]);

  async function submitQuery(event?: React.FormEvent) {
    event?.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setStreaming(false);
    setError("");
    setSelectedSource(0);
    setResponse(null);
    try {
      const filters = {
        document_id: selectedDocument || null,
        report_type: reportType || null,
        report_year_min: yearFrom ? Number(yearFrom) : null,
        report_year_max: yearTo ? Number(yearTo) : null,
        content_type: contentType || null,
      };
      await streamQuestion(question, filters, topK, {
        onSources: (sources) => {
          setStreaming(true);
          setResponse({ question, answer: "", sources });
        },
        onDelta: (text) => {
          setResponse((current) =>
            current ? { ...current, answer: current.answer + text } : current,
          );
        },
        onDone: () => {
          setStreaming(false);
        },
        onError: (message) => {
          setError(message);
          setStreaming(false);
        },
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
      setStreaming(false);
    }
  }

  async function runIngest(ocr: boolean, vision = false) {
    setIngesting(true);
    setError("");
    try {
      await ingest(undefined, ocr, vision);
      await refreshDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ingestion failed");
    } finally {
      setIngesting(false);
    }
  }

  const selected = response?.sources[selectedSource] ?? null;
  const indexedChunks = documents.reduce((sum, doc) => sum + doc.chunk_count, 0);
  const indexedPages = documents.reduce((sum, doc) => sum + doc.page_count, 0);
  const tableCounts = tables.reduce(
    (acc, table) => {
      const key = table.quality_status ?? "unknown";
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>,
  );

  return (
    <main className="app-shell">
      <aside className="sidebar">
        <div className="brand-row">
          <div className="brand-mark">
            <Database size={20} />
          </div>
          <div>
            <h1>Boeing RAG</h1>
            <p>Annual and sustainability reports</p>
          </div>
        </div>

        <section className="metrics">
          <div>
            <span>{documents.length}</span>
            <p>Docs</p>
          </div>
          <div>
            <span>{indexedPages}</span>
            <p>Pages</p>
          </div>
          <div>
            <span>{indexedChunks}</span>
            <p>Chunks</p>
          </div>
        </section>

        <section className="table-health">
          <button className="table-health-toggle" onClick={() => setShowTables((value) => !value)}>
            <span>Table Audit</span>
            <strong>{tables.length}</strong>
          </button>
          <div className="table-status-row">
            <span className="status-pass">{tableCounts.pass ?? 0} pass</span>
            <span className="status-review">{tableCounts.review ?? 0} review</span>
            <span className="status-fail">{tableCounts.fail ?? 0} fail</span>
          </div>
        </section>

        <section className="control-section">
          <div className="section-title">
            <Filter size={16} />
            <span>Filters</span>
          </div>
          <label>
            Document
            <select value={selectedDocument} onChange={(event) => setSelectedDocument(event.target.value)}>
              <option value="">All indexed documents</option>
              {documents.map((doc) => (
                <option value={doc.id} key={doc.id}>
                  {doc.report_year ? `${doc.report_year} ` : ""}
                  {doc.file_name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Report Type
            <select value={reportType} onChange={(event) => setReportType(event.target.value)}>
              <option value="">All types</option>
              <option value="annual_report">Annual reports</option>
              <option value="sustainability_report">Sustainability reports</option>
            </select>
          </label>
          <div className="split-inputs">
            <label>
              From
              <input value={yearFrom} onChange={(event) => setYearFrom(event.target.value)} inputMode="numeric" />
            </label>
            <label>
              To
              <input value={yearTo} onChange={(event) => setYearTo(event.target.value)} inputMode="numeric" />
            </label>
          </div>
          <label>
            Content
            <select value={contentType} onChange={(event) => setContentType(event.target.value)}>
              <option value="">Text and tables</option>
              <option value="text">Text only</option>
              <option value="table">Tables only</option>
              <option value="image">Visual extractions</option>
            </select>
          </label>
          <label>
            Evidence Count
            <input
              type="range"
              min="3"
              max="14"
              value={topK}
              onChange={(event) => setTopK(Number(event.target.value))}
            />
            <span className="range-readout">{topK} sources</span>
          </label>
        </section>

        <section className="control-section">
          <div className="section-title">
            <SlidersHorizontal size={16} />
            <span>Indexing</span>
          </div>
          <button className="secondary-button" onClick={() => runIngest(false)} disabled={ingesting}>
            {ingesting ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
            Ingest PDFs
          </button>
          <button className="secondary-button" onClick={() => runIngest(true)} disabled={ingesting}>
            {ingesting ? <Loader2 className="spin" size={16} /> : <FileSearch size={16} />}
            Ingest With OCR
          </button>
          <button className="secondary-button" onClick={() => runIngest(false, true)} disabled={ingesting}>
            {ingesting ? <Loader2 className="spin" size={16} /> : <FileSearch size={16} />}
            Ingest With Vision
          </button>
        </section>
      </aside>

      <section className="workspace">
        <nav className="workspace-tabs" aria-label="Workspace">
          <button className={activeView === "ask" ? "active" : ""} onClick={() => setActiveView("ask")}>
            <BookOpen size={16} />
            Ask
          </button>
          <button className={activeView === "upload" ? "active" : ""} onClick={() => setActiveView("upload")}>
            <Upload size={16} />
            Upload
          </button>
        </nav>

        {error && <div className="error-banner">{error}</div>}

        {activeView === "upload" ? (
          <UploadScreen onError={setError} onRefreshDocuments={refreshDocuments} />
        ) : (
          <>
        <form className="query-bar" onSubmit={submitQuery}>
          <Search size={19} />
          <textarea value={question} onChange={(event) => setQuestion(event.target.value)} rows={2} />
          <button type="submit" disabled={loading || !question.trim()} title="Ask">
            {loading ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
          </button>
        </form>

        <div className="examples">
          {exampleQuestions.map((item) => (
            <button key={item} onClick={() => setQuestion(item)}>
              {item}
            </button>
          ))}
        </div>

        {showTables && (
          <section className="table-audit-panel">
            <div className="panel-heading">
              <FileSearch size={18} />
              <span>Table Extraction Audit</span>
            </div>
            <div className="table-audit-grid">
              {tables.map((table) => (
                <article className={`table-card ${table.quality_status ?? "unknown"}`} key={table.chunk_id}>
                  <div className="table-card-top">
                    <strong>{table.citation_label}</strong>
                    <span>{table.quality_status ?? "unknown"}</span>
                  </div>
                  <div className="table-card-meta">
                    <span>{table.rows ?? "?"} x {table.cols ?? "?"}</span>
                    <span>score {table.quality_score?.toFixed(2) ?? "n/a"}</span>
                  </div>
                  {table.quality_issues.length > 0 && (
                    <p className="table-issues">{table.quality_issues.join(", ")}</p>
                  )}
                  <pre>{table.markdown_preview}</pre>
                </article>
              ))}
            </div>
          </section>
        )}

        <section className="answer-layout">
          <article className="answer-panel">
            <div className="panel-heading">
              <BookOpen size={18} />
              <span>Answer</span>
            </div>
            {response ? (
              <>
                {streaming && <div className="streaming-status">Streaming answer...</div>}
                <AnswerText
                  answer={response.answer}
                  sources={response.sources}
                  onSelectSource={setSelectedSource}
                />
              </>
            ) : (
              <div className="empty-state">
                Ask a question over the indexed Boeing reports. Answers are grounded in retrieved evidence and cite exact documents and pages.
              </div>
            )}
          </article>

          <aside className="sources-panel">
            <div className="panel-heading">
              <FileSearch size={18} />
              <span>Evidence</span>
            </div>
            <div className="source-list">
              {response?.sources.map((source, index) => (
                <button
                  className={index === selectedSource ? "source-item selected" : "source-item"}
                  key={source.chunk_id}
                  onClick={() => setSelectedSource(index)}
                >
                  <span>{index + 1}</span>
                  <strong>{source.citation_label}</strong>
                  <small>{source.content_type} · score {source.score.toFixed(2)}</small>
                </button>
              ))}
            </div>
            {selected && (
              <div className="source-detail">
                <div className="source-meta">
                  <span>{selected.report_type.replace("_", " ")}</span>
                  <span>{selected.report_year ?? "year unknown"}</span>
                  {selected.page_start && <span>page {selected.page_start}</span>}
                  {selected.section_path.length > 0 && <span>{selected.section_path.join(" > ")}</span>}
                  {selected.content_type === "image" && <span>visual extraction</span>}
                </div>
                <SourcePreview source={selected} />
                <EvidenceHighlight source={selected} />
              </div>
            )}
          </aside>
        </section>
          </>
        )}
      </section>
    </main>
  );
}

function UploadScreen({
  onError,
  onRefreshDocuments,
}: {
  onError: (message: string) => void;
  onRefreshDocuments: () => Promise<void>;
}) {
  const folderInputRef = React.useRef<HTMLInputElement | null>(null);
  const fileInputRef = React.useRef<HTMLInputElement | null>(null);
  const [selectedFiles, setSelectedFiles] = React.useState<File[]>([]);
  const [job, setJob] = React.useState<UploadJobStatus | null>(null);
  const [uploading, setUploading] = React.useState(false);
  const [force, setForce] = React.useState(false);
  const [renderPages, setRenderPages] = React.useState(true);

  const pdfFiles = React.useMemo(
    () => selectedFiles.filter((file) => file.name.toLowerCase().endsWith(".pdf")),
    [selectedFiles],
  );
  const totalSize = pdfFiles.reduce((sum, file) => sum + file.size, 0);
  const progress = job?.total_files ? Math.round((job.processed_files / job.total_files) * 100) : 0;
  const activeJob = job?.status === "queued" || job?.status === "running";

  React.useEffect(() => {
    if (!job || !activeJob) return;
    const timer = window.setInterval(async () => {
      try {
        const nextJob = await getUploadJob(job.job_id);
        setJob(nextJob);
        if (nextJob.status === "completed" || nextJob.status === "failed") {
          window.clearInterval(timer);
          await onRefreshDocuments();
        }
      } catch (err) {
        onError(err instanceof Error ? err.message : "Could not refresh ingestion progress");
      }
    }, 1200);
    return () => window.clearInterval(timer);
  }, [activeJob, job, onError, onRefreshDocuments]);

  function chooseFiles(fileList: FileList | null) {
    const nextFiles = Array.from(fileList ?? []);
    setSelectedFiles(nextFiles);
    setJob(null);
    onError("");
  }

  async function startUpload() {
    if (!pdfFiles.length) return;
    setUploading(true);
    onError("");
    try {
      const nextJob = await uploadDocuments(pdfFiles, force, renderPages);
      setJob(nextJob);
    } catch (err) {
      onError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  return (
    <section className="upload-screen">
      <div className="upload-hero">
        <div>
          <span className="eyebrow">Corpus ingestion</span>
          <h2>Upload Boeing PDFs into the RAG index</h2>
          <p>Select a folder or choose individual PDFs. The backend parses, chunks, contextualizes, embeds, and indexes each document while progress updates here.</p>
        </div>
        <div className="upload-stats">
          <strong>{pdfFiles.length}</strong>
          <span>PDFs selected</span>
          <small>{formatBytes(totalSize)}</small>
        </div>
      </div>

      <div className="upload-actions">
        <input
          ref={folderInputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(event) => chooseFiles(event.target.files)}
          {...{ webkitdirectory: "", directory: "" }}
        />
        <input
          ref={fileInputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          hidden
          onChange={(event) => chooseFiles(event.target.files)}
        />
        <button className="upload-choice" onClick={() => folderInputRef.current?.click()} type="button">
          <FolderOpen size={18} />
          Select Folder
        </button>
        <button className="upload-choice" onClick={() => fileInputRef.current?.click()} type="button">
          <FileSearch size={18} />
          Select PDFs
        </button>
        <label className="inline-check">
          <input type="checkbox" checked={force} onChange={(event) => setForce(event.target.checked)} />
          Reindex matching files
        </label>
        <label className="inline-check">
          <input type="checkbox" checked={renderPages} onChange={(event) => setRenderPages(event.target.checked)} />
          Render page previews
        </label>
      </div>

      <div className="upload-progress-panel">
        <div className="progress-header">
          <div>
            <strong>{job?.message ?? (pdfFiles.length ? "Ready to upload" : "No PDFs selected")}</strong>
            <span>{job?.current_file ?? "Upload jobs run one document at a time for reliable indexing."}</span>
          </div>
          <button onClick={startUpload} disabled={!pdfFiles.length || uploading || activeJob} type="button">
            {uploading || activeJob ? <Loader2 className="spin" size={16} /> : <Upload size={16} />}
            {uploading ? "Uploading..." : activeJob ? "Processing..." : "Start Ingestion"}
          </button>
        </div>
        <div className="progress-track" aria-label="Ingestion progress">
          <span style={{ width: `${progress}%` }} />
        </div>
        <div className="progress-readout">
          <span>{job ? `${job.processed_files}/${job.total_files} processed` : `${pdfFiles.length} ready`}</span>
          <span>{job?.failed_files ? `${job.failed_files} failed` : `${progress}%`}</span>
        </div>
      </div>

      <div className="upload-file-list">
        {(job?.files ?? pdfFiles.map(fileToQueuedJobFile)).map((file) => (
          <div className="upload-file-row" key={file.relative_path ?? file.name}>
            <span className={`file-status ${file.status}`}>
              {file.status === "indexed" ? <CheckCircle2 size={15} /> : file.status === "failed" ? <AlertCircle size={15} /> : <FileSearch size={15} />}
            </span>
            <div>
              <strong>{file.name}</strong>
              <small>{file.relative_path ?? file.status}{file.error ? ` · ${file.error}` : ""}</small>
            </div>
            <em>{file.status}</em>
          </div>
        ))}
      </div>
    </section>
  );
}

function fileToQueuedJobFile(file: File) {
  const relativePath = (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
  return {
    name: file.name,
    relative_path: relativePath,
    status: "queued",
    document_id: null,
    error: null,
  };
}

function formatBytes(bytes: number): string {
  if (!bytes) return "0 MB";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** exponent).toFixed(exponent === 0 ? 0 : 1)} ${units[exponent]}`;
}

function AnswerText({
  answer,
  sources,
  onSelectSource,
}: {
  answer: string;
  sources: SourceCitation[];
  onSelectSource: (index: number) => void;
}) {
  return (
    <div className="answer-text">
      {answer.split("\n").map((line, index) => {
        if (line.trim().toLowerCase() === "references:") {
          return (
            <h3 className="references-title" key={`${index}-${line}`}>
              References:
            </h3>
          );
        }
        return (
          <p className={line.startsWith("- [") ? "reference-line" : undefined} key={`${index}-${line}`}>
            <ClickableCitations line={line} sources={sources} onSelectSource={onSelectSource} />
          </p>
        );
      })}
    </div>
  );
}

function ClickableCitations({
  line,
  sources,
  onSelectSource,
}: {
  line: string;
  sources: SourceCitation[];
  onSelectSource: (index: number) => void;
}) {
  const parts = line.split(/(\[\d+\])/g);
  return (
    <>
      {parts.map((part, index) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (!match) return <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>;
        const sourceIndex = Number(match[1]) - 1;
        const source = sources[sourceIndex];
        if (!source) return <React.Fragment key={`${part}-${index}`}>{part}</React.Fragment>;
        return (
          <button
            className="citation-chip"
            key={`${part}-${index}`}
            title={source.citation_label}
            onClick={() => onSelectSource(sourceIndex)}
            type="button"
          >
            {part}
          </button>
        );
      })}
    </>
  );
}

function SourcePreview({ source }: { source: SourceCitation }) {
  const pdfPageUrl = source.pdf_url ? buildPdfUrl(source, false) : "";
  const pdfSearchUrl = source.pdf_url ? buildPdfUrl(source, true) : "";
  const imageUrl = assetUrl(source.page_image_url);

  return (
    <div className="source-preview">
      <div className="preview-actions">
        {source.pdf_url && (
          <a href={pdfPageUrl} target="_blank" rel="noreferrer">
            Open PDF page
          </a>
        )}
        {pdfSearchUrl && (
          <a href={pdfSearchUrl} target="_blank" rel="noreferrer">
            Find chunk in PDF
          </a>
        )}
        {source.page_image_url && (
          <a href={imageUrl} target="_blank" rel="noreferrer">
            Open page image
          </a>
        )}
      </div>
      {pdfPageUrl ? (
        <PdfChunkPreview source={source} />
      ) : imageUrl ? (
        <img src={imageUrl} alt={source.citation_label} />
      ) : (
        <div className="preview-empty">No document preview available for this source.</div>
      )}
    </div>
  );
}

function EvidenceHighlight({ source }: { source: SourceCitation }) {
  return (
    <section className={`chunk-highlight ${source.content_type}`}>
      <div className="chunk-highlight-heading">
        <strong>Retrieved evidence chunk</strong>
        <span>{source.content_type}</span>
      </div>
      <pre>{source.text}</pre>
    </section>
  );
}

function buildPdfUrl(source: SourceCitation, includeSearch: boolean): string {
  const baseUrl = assetUrl(source.pdf_url);
  const params = new URLSearchParams();
  if (source.page_start) params.set("page", String(source.page_start));
  if (includeSearch) {
    const phrase = chunkSearchPhrase(source.text);
    if (phrase) params.set("search", phrase);
  }
  const hash = params.toString();
  return hash ? `${baseUrl}#${hash}` : baseUrl;
}

function chunkSearchPhrase(text: string): string {
  const cleanLines = text
    .split("\n")
    .map((line) => line.replace(/[|*_`#>-]/g, " ").replace(/\s+/g, " ").trim())
    .filter((line) => line.length > 24 && !/^[-\s]+$/.test(line));
  const candidate = cleanLines[0] ?? text.replace(/\s+/g, " ").trim();
  return candidate.slice(0, 120);
}

createRoot(document.getElementById("root")!).render(<App />);
