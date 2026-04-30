import type {
  DocumentSummary,
  QueryFilters,
  QueryResponse,
  SourceCitation,
  TableAudit,
  UploadJobStatus,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

export function assetUrl(path: string | null | undefined): string {
  if (!path) return "";
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE}${path}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getDocuments(): Promise<DocumentSummary[]> {
  return request<DocumentSummary[]>("/documents");
}

export function getTables(): Promise<TableAudit[]> {
  return request<TableAudit[]>("/tables");
}

export function askQuestion(
  question: string,
  filters: QueryFilters,
  topK: number,
): Promise<QueryResponse> {
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify({ question, filters, top_k: topK }),
  });
}

export async function streamQuestion(
  question: string,
  filters: QueryFilters,
  topK: number,
  handlers: {
    onSources: (sources: SourceCitation[]) => void;
    onDelta: (text: string) => void;
    onDone: () => void;
    onError: (message: string) => void;
  },
): Promise<void> {
  const response = await fetch(`${API_BASE}/query/stream`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ question, filters, top_k: topK }),
  });
  if (!response.ok || !response.body) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";
    for (const eventBlock of events) {
      handleSseEvent(eventBlock, handlers);
    }
  }
  if (buffer.trim()) handleSseEvent(buffer, handlers);
}

function handleSseEvent(
  block: string,
  handlers: {
    onSources: (sources: SourceCitation[]) => void;
    onDelta: (text: string) => void;
    onDone: () => void;
    onError: (message: string) => void;
  },
) {
  const event = block.match(/^event:\s*(.+)$/m)?.[1]?.trim();
  const dataLine = block.match(/^data:\s*(.+)$/m)?.[1];
  const data = dataLine ? JSON.parse(dataLine) : {};
  if (event === "sources") handlers.onSources(data.sources ?? []);
  if (event === "delta") handlers.onDelta(data.text ?? "");
  if (event === "done") handlers.onDone();
  if (event === "error") handlers.onError(data.message ?? "Streaming query failed");
}

export function ingest(
  limit?: number,
  ocr = false,
  vision = false,
): Promise<{ ingested: string[]; count: number }> {
  const params = new URLSearchParams();
  if (limit) params.set("limit", String(limit));
  params.set("ocr", String(ocr));
  params.set("vision", String(vision));
  params.set("vision_max_pages", "4");
  params.set("render_pages", "true");
  return request(`/ingest?${params.toString()}`, { method: "POST" });
}

export async function uploadDocuments(
  files: File[],
  force = false,
  renderPages = true,
): Promise<UploadJobStatus> {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append("files", file, file.name);
    formData.append("relative_paths", relativePathFor(file));
  });
  formData.set("force", String(force));
  formData.set("render_pages", String(renderPages));

  const response = await fetch(`${API_BASE}/ingest/upload`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Upload failed with ${response.status}`);
  }
  return response.json() as Promise<UploadJobStatus>;
}

export function getUploadJob(jobId: string): Promise<UploadJobStatus> {
  return request<UploadJobStatus>(`/ingest/jobs/${jobId}`);
}

function relativePathFor(file: File): string {
  return (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
}
