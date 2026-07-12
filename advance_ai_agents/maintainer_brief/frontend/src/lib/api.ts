export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "mb.token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string) {
  localStorage.setItem(TOKEN_KEY, t);
}
export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}
export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const t = getToken();
  return t ? { ...extra, Authorization: `Bearer ${t}` } : extra;
}
export function loginUrl(): string {
  return `${API_URL}/auth/login`;
}

/** On 401, drop the token and bounce to the sign-in gate. */
function onUnauthorized() {
  clearToken();
  if (typeof window !== "undefined" && window.location.pathname !== "/") {
    window.location.href = "/";
  } else if (typeof window !== "undefined") {
    window.location.reload();
  }
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", headers: authHeaders() });
  if (res.status === 401) {
    onUnauthorized();
    throw new Error("unauthorized");
  }
  if (!res.ok) throw new Error(`${res.status} ${path}`);
  return res.json();
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) {
    onUnauthorized();
    throw new Error("unauthorized");
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail ?? `${res.status} ${path}`);
  }
  return res.json();
}

export interface Project {
  id: number;
  slug: string;
  name: string;
  config: Record<string, unknown>;
}

export interface Citation {
  id: number;
  document_id: number;
  field_name: string | null;
  page_no: number;
  bbox: number[] | Record<string, number>;
  snippet: string | null;
}

export interface PageInfo {
  page_no: number;
  width_px: number;
  height_px: number;
  width_pt: number;
  height_pt: number;
}

export interface Signal {
  id: number;
  signal_type: string;
  source_kind: string;
  source_url: string | null;
  document_id: number | null;
  title: string;
  summary: string | null;
  category: string | null;
  urgency: string | null;
  sentiment: number | null;
  keywords: string[] | null;
  confidence: number | null;
  observed_at: string;
  citation_count: number;
  payload?: Record<string, unknown>;
  citations?: Citation[];
  document?: {
    id: number;
    title: string | null;
    source_url: string | null;
    doc_category: string | null;
    page_count: number | null;
    pages: PageInfo[];
  };
}

export interface IssueRef {
  number: number;
  repo: string;
  title: string;
  url: string;
  reactions: number;
  comments: number;
}

export interface PrRef {
  number: number;
  repo: string;
  title: string;
  url: string;
  author: string | null;
  age_days: number | null;
  note: string;
}

export interface BriefJson {
  headline: string;
  stats: {
    open_issues?: number;
    open_prs?: number;
    stars?: number;
    latest_release?: string | null;
    unreleased_prs?: number;
  };
  triage: {
    title: string;
    kind: string; // duplicates | hot | unanswered | stalled
    action: string;
    issues: IssueRef[];
  }[];
  ship_it: {
    latest_release: string | null;
    unreleased_count: number;
    release_summary: string;
    ready_to_merge: PrRef[];
    needs_review: PrRef[];
    security: { id: string; severity: string; url: string; package?: string }[];
  };
  people: PrRef[];
  worth_replying_to: {
    source: string;
    title: string;
    url: string;
    why: string;
    age_days: number | null;
  }[];
}

export interface Brief {
  id: number;
  project_id: number;
  period_start: string;
  period_end: string;
  brief_json: BriefJson;
  sent_at: string | null;
  created_at: string;
}

export interface Run {
  id: number;
  status: string;
  stage: string | null;
  stats: Record<string, unknown>;
  error: string | null;
}

export const SECTION_KEYS = [
  "triage",
  "ship_it",
  "people",
  "worth_replying_to",
] as const;
export type SectionKey = (typeof SECTION_KEYS)[number];

export const SECTION_LABELS: Record<SectionKey, string> = {
  triage: "Triage This Week",
  ship_it: "Ship It",
  people: "People",
  worth_replying_to: "Worth Replying To",
};

export interface GithubRepoMeta {
  full_name: string;
  name: string;
  description: string;
  topics: string[];
  stargazers_count: number;
  language: string | null;
  owner_avatar: string | null;
  html_url: string | null;
  suggested_keywords: string[];
}

export interface BriefHtml {
  html: string;
  subject: string;
  sections: Record<SectionKey, boolean>;
  default_recipients: string[];
}

export interface DocumentRow {
  id: number;
  title: string | null;
  source_url: string | null;
  doc_category: string | null;
  page_count: number | null;
  status: string;
  signal_count: number;
  created_at: string;
}

export interface SendResult {
  sent_to: string[];
  resend_id: string | null;
  test: boolean;
}

// Curated starter projects for the create gallery
export interface GalleryPreset {
  emoji: string;
  name: string;
  repos: string[];
  keywords: string[];
  competitors: { name: string; keywords: string[] }[];
  subreddits: string[];
  hn_queries: string[];
  blurb: string;
}

export const GALLERY: GalleryPreset[] = [
  {
    emoji: "🕸️", name: "Meshery", repos: ["meshery/meshery", "layer5io/kanvas"],
    keywords: ["meshery", "service mesh", "cloud native management", "kanvas"],
    competitors: [{ name: "Backstage", keywords: ["backstage"] }, { name: "Istio", keywords: ["istio"] }],
    subreddits: ["kubernetes", "devops"], hn_queries: ["meshery", "service mesh"],
    blurb: "Cloud-native manager for Kubernetes, service meshes, and apps.",
  },
  {
    emoji: "🦜", name: "LangChain", repos: ["langchain-ai/langchain"],
    keywords: ["langchain", "llm", "rag", "agents"],
    competitors: [{ name: "LlamaIndex", keywords: ["llamaindex", "llama index"] }],
    subreddits: ["LangChain", "LocalLLaMA"], hn_queries: ["langchain", "llm framework"],
    blurb: "Framework for building applications with large language models.",
  },
  {
    emoji: "▲", name: "Next.js", repos: ["vercel/next.js"],
    keywords: ["next.js", "react", "vercel", "ssr"],
    competitors: [{ name: "Remix", keywords: ["remix"] }, { name: "SvelteKit", keywords: ["sveltekit"] }],
    subreddits: ["nextjs", "reactjs"], hn_queries: ["next.js"],
    blurb: "The React framework for the web.",
  },
  {
    emoji: "☸️", name: "Kubernetes", repos: ["kubernetes/kubernetes"],
    keywords: ["kubernetes", "k8s", "container orchestration"],
    competitors: [{ name: "Nomad", keywords: ["nomad"] }],
    subreddits: ["kubernetes"], hn_queries: ["kubernetes"],
    blurb: "Production-grade container orchestration.",
  },
  {
    emoji: "🔭", name: "OpenTelemetry", repos: ["open-telemetry/opentelemetry-collector"],
    keywords: ["opentelemetry", "otel", "observability", "tracing"],
    competitors: [{ name: "Datadog", keywords: ["datadog"] }],
    subreddits: ["devops", "observability"], hn_queries: ["opentelemetry"],
    blurb: "Vendor-neutral observability: traces, metrics, and logs.",
  },
  {
    emoji: "⚡", name: "Supabase", repos: ["supabase/supabase"],
    keywords: ["supabase", "postgres", "backend as a service"],
    competitors: [{ name: "Firebase", keywords: ["firebase"] }],
    subreddits: ["Supabase"], hn_queries: ["supabase"],
    blurb: "The open-source Firebase alternative.",
  },
];

export interface MeUser {
  id: number;
  login: string;
  name: string | null;
  avatar_url: string | null;
}

export const api = {
  me: () => get<MeUser>("/auth/me"),
  logout: () => send<{ ok: boolean }>("POST", "/auth/logout"),
  projects: () => get<Project[]>("/projects"),
  project: (id: number) => get<Project>(`/projects/${id}`),
  createProject: (name: string, config: Record<string, unknown>) =>
    send<Project>("POST", "/projects", { name, config }),
  updateProject: (id: number, patch: { name?: string; config?: Record<string, unknown> }) =>
    send<Project>("PATCH", `/projects/${id}`, patch),
  deleteProject: (id: number) => send<{ status: string }>("DELETE", `/projects/${id}`),
  validateGithubRepo: (repo: string) =>
    get<GithubRepoMeta>(`/github/repo?repo=${encodeURIComponent(repo)}`),
  latestBrief: (projectId: number) =>
    get<Brief>(`/briefs/latest?project_id=${projectId}`),
  brief: (id: number) => get<Brief>(`/briefs/${id}`),
  briefHtml: (id: number) => get<BriefHtml>(`/briefs/${id}/html`),
  sendBrief: (
    id: number,
    body: { recipients?: string[]; subject?: string; from_name?: string; test?: boolean },
  ) => send<SendResult>("POST", `/briefs/${id}/send`, body),
  signals: (projectId: number, params = "") =>
    get<Signal[]>(`/signals?project_id=${projectId}${params}`),
  signal: (id: number) => get<Signal>(`/signals/${id}`),
  documents: (projectId: number) =>
    get<DocumentRow[]>(`/documents?project_id=${projectId}`),
  run: (id: number) => get<Run>(`/runs/${id}`),
  pageImageUrl: (documentId: number, pageNo: number) =>
    `${API_URL}/assets/pages/${documentId}/${pageNo}.png`,
};
