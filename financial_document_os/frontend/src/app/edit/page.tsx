"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";

interface Occurrence {
  citation_id: number;
  field_name: string;
  page_no: number;
  snippet: string;
}
interface DocImpact {
  document_id: number;
  document_title: string;
  occurrences: Occurrence[];
}
interface Impact {
  match_value: string;
  documents_affected: number;
  occurrences_total: number;
  documents: DocImpact[];
}
interface EditResult {
  document_id: number;
  document_title?: string;
  status: string;
  items_processed?: number;
  edit_id?: number;
  error?: string;
}

export default function EditPage() {
  const [enabled, setEnabled] = useState(true);
  const [matchValue, setMatchValue] = useState("100 Market St, Suite 400, San Francisco, CA 94105");
  const [replacement, setReplacement] = useState("500 Howard St, Floor 12, San Francisco, CA 94105");
  const [impact, setImpact] = useState<Impact | null>(null);
  const [results, setResults] = useState<EditResult[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetch(`${API_URL}/health`).then((r) => r.json()).then((h) => setEnabled(h.editing_enabled));
  }, []);

  const analyze = async () => {
    setBusy(true);
    setResults(null);
    const res = await fetch(`${API_URL}/edit/impact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ match_value: matchValue }),
    }).then((r) => r.json());
    setImpact(res);
    setBusy(false);
  };

  const apply = async () => {
    setBusy(true);
    const res = await fetch(`${API_URL}/edit/apply`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ match_value: matchValue, replacement_text: replacement }),
    }).then((r) => r.json());
    setResults(res.edits ?? []);
    setBusy(false);
  };

  return (
    <div>
      <h1 className="font-serif text-4xl">Edit Across Documents</h1>
      <p className="mt-1 text-sm text-muted">
        Change a value once; rewrite it in every PDF it appears in, preserving
        layout. Powered by the Unsiloed Edit API.
      </p>

      {!enabled && (
        <div className="mt-6 rounded-sm border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Editing is disabled — the bbox calibration test did not pass in this
          environment. Extraction, explorer, analytics, and anomalies are
          unaffected.
        </div>
      )}

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <label className="text-sm">
          <span className="text-muted">Find this value</span>
          <input
            value={matchValue}
            onChange={(e) => setMatchValue(e.target.value)}
            className="mt-1 w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </label>
        <label className="text-sm">
          <span className="text-muted">Replace with</span>
          <input
            value={replacement}
            onChange={(e) => setReplacement(e.target.value)}
            className="mt-1 w-full rounded-sm border border-line bg-card px-3 py-2 text-sm outline-none focus:border-accent"
          />
        </label>
      </div>

      <div className="mt-3 flex gap-2">
        <button
          onClick={analyze}
          disabled={busy || !matchValue.trim()}
          className="rounded-sm border border-line px-4 py-2 text-sm font-bold hover:bg-accent-soft disabled:opacity-50"
        >
          {busy && !results ? "Analyzing…" : "Analyze impact"}
        </button>
        {impact && impact.documents_affected > 0 && enabled && !results && (
          <button
            onClick={apply}
            disabled={busy}
            className="rounded-sm bg-accent px-4 py-2 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50"
          >
            {busy ? "Editing…" : `Apply to ${impact.documents_affected} documents`}
          </button>
        )}
      </div>

      {impact && !results && (
        <div className="mt-6">
          <p className="text-sm text-muted">
            Found <b className="text-ink">{impact.occurrences_total}</b> occurrences
            across <b className="text-ink">{impact.documents_affected}</b> documents:
          </p>
          <div className="mt-3 space-y-2">
            {impact.documents.map((d) => (
              <div key={d.document_id} className="rounded-sm border border-line bg-card p-3">
                <div className="font-serif">{d.document_title}</div>
                <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted">
                  {d.occurrences.map((o) => (
                    <span key={o.citation_id} className="rounded-sm bg-paper px-2 py-0.5">
                      p.{o.page_no} · {o.field_name}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {results && (
        <div className="mt-6">
          <p className="text-sm font-bold text-ink">Edits applied:</p>
          <div className="mt-3 space-y-2">
            {results.map((r) => (
              <div
                key={r.document_id}
                className="flex items-center justify-between rounded-sm border border-line bg-card p-3"
              >
                <div>
                  <span className="font-serif">{r.document_title ?? `Document ${r.document_id}`}</span>
                  <span className="ml-2 text-xs text-muted">
                    {r.status === "succeeded"
                      ? `${r.items_processed} edit(s) applied`
                      : `failed: ${r.error ?? "unknown"}`}
                  </span>
                </div>
                {r.status === "succeeded" && r.edit_id && (
                  <a
                    href={`${API_URL}/edit/download/${r.edit_id}`}
                    className="rounded-sm bg-accent px-3 py-1.5 text-xs font-bold text-white hover:opacity-90"
                  >
                    Download PDF ↓
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
