"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, DocumentRow, Run, api } from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  ingest: "Reading uploads",
  classify: "Classifying documents",
  extract: "Extracting with Unsiloed",
  normalize: "Structuring entities",
  analyze: "Detecting anomalies",
};

const CATEGORY_LABELS: Record<string, string> = {
  bank_statement: "Bank statement",
  investment_statement: "Investment statement",
  vendor_contract: "Vendor contract",
  loan_agreement: "Loan agreement",
  tax_filing: "Tax filing",
  annual_report: "Annual report",
  audit_report: "Audit report",
  cap_table: "Cap table",
};

export default function DocumentsPage() {
  const [docs, setDocs] = useState<DocumentRow[]>([]);
  const [uploading, setUploading] = useState(false);
  const [run, setRun] = useState<Run | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(() => {
    api.documents().then(setDocs).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [refresh]);

  const upload = async (files: FileList) => {
    setUploading(true);
    setMsg(null);
    let created = 0;
    let dupes = 0;
    for (const file of Array.from(files)) {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API_URL}/documents/upload`, {
        method: "POST",
        body: form,
      });
      const body = await res.json().catch(() => ({}));
      if (body.status === "created") created++;
      else if (body.status === "duplicate") dupes++;
    }
    setMsg(`${created} uploaded${dupes ? `, ${dupes} already ingested` : ""}.`);
    setUploading(false);
    refresh();
  };

  const process = async () => {
    setMsg(null);
    const res = await fetch(`${API_URL}/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    if (!res.ok) {
      const b = await res.json().catch(() => ({}));
      setMsg(b.detail ?? `HTTP ${res.status}`);
      return;
    }
    const { run_id } = await res.json();
    timer.current = setInterval(async () => {
      const r = await api.run(run_id);
      setRun(r);
      if (r.status !== "running") {
        if (timer.current) clearInterval(timer.current);
        refresh();
      }
    }, 1500);
  };

  const running = run?.status === "running";
  const pending = docs.filter((d) => d.status !== "extracted").length;

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="font-serif text-4xl">Documents</h1>
          <p className="mt-1 text-sm text-muted">
            Upload bank statements, contracts, loans, tax filings, investment
            statements, audits. Unsiloed turns them into structured, queryable
            entities with evidence.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={process}
            disabled={running}
            className="rounded-sm border border-line px-4 py-2 text-sm font-bold hover:bg-accent-soft disabled:opacity-50"
          >
            {running ? "Processing…" : `Process${pending ? ` (${pending})` : ""}`}
          </button>
          <label className="cursor-pointer rounded-sm bg-accent px-4 py-2 text-sm font-bold text-white hover:opacity-90">
            {uploading ? "Uploading…" : "Upload documents"}
            <input
              type="file"
              multiple
              accept=".pdf,.pptx,.docx,.png,.jpg,.jpeg,.xlsx"
              className="hidden"
              disabled={uploading}
              onChange={(e) => {
                if (e.target.files?.length) upload(e.target.files);
                e.target.value = "";
              }}
            />
          </label>
        </div>
      </div>

      {running && run?.stage && (
        <div className="mt-4 flex items-center gap-2 text-sm text-muted">
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-accent" />
          {STAGE_LABELS[run.stage] ?? run.stage}
          {run.stage === "extract" &&
            typeof (run.stats?.extract as { succeeded?: number })?.succeeded ===
              "number" &&
            ` · ${(run.stats.extract as { succeeded: number }).succeeded} extractions`}
        </div>
      )}
      {msg && <p className="mt-4 text-sm text-accent">{msg}</p>}

      {docs.length === 0 && (
        <p className="mt-12 text-center text-muted">
          No documents yet. Upload PDFs, then hit Process.
        </p>
      )}

      <div className="mt-6 space-y-2">
        {docs.map((d) => (
          <div
            key={d.id}
            className="flex items-center justify-between rounded-sm border border-line bg-card p-4"
          >
            <div>
              <h2 className="font-serif text-lg">{d.title}</h2>
              <p className="mt-0.5 text-xs text-muted">
                {d.doc_category
                  ? (CATEGORY_LABELS[d.doc_category] ?? d.doc_category)
                  : "unclassified"}
                {d.page_count ? ` · ${d.page_count} pages` : ""} · {d.status}
              </p>
            </div>
            <span
              className={`rounded-sm px-3 py-1 text-xs font-bold ${
                d.status === "extracted"
                  ? "bg-accent-soft text-accent"
                  : "bg-line text-muted"
              }`}
            >
              {d.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
