"use client";

import { useEffect, useState } from "react";
import { api, CitationResponse } from "@/lib/api";
import CitationViewer from "./CitationViewer";

export interface EvidenceTarget {
  kind: string;
  id: number;
  field?: string;
  label?: string;
}

export default function EvidencePanel({
  target,
  onClose,
}: {
  target: EvidenceTarget | null;
  onClose: () => void;
}) {
  const [data, setData] = useState<CitationResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!target) {
      setData(null);
      return;
    }
    setLoading(true);
    api
      .citations(target.kind, target.id, target.field)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [target]);

  if (!target) return null;

  const pageNos = data
    ? [...new Set(data.citations.map((c) => c.page_no))].sort((a, b) => a - b)
    : [];

  return (
    <div className="fixed bottom-0 right-0 top-14 z-30 flex w-[520px] max-w-[92vw] flex-col border-l border-line bg-card shadow-2xl">
      <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-3">
        <div className="min-w-0">
          <div className="text-[10px] font-bold uppercase tracking-[1.5px] text-accent">
            Evidence
          </div>
          <div className="truncate font-serif text-lg">
            {target.label ?? `${target.kind} #${target.id}`}
          </div>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 rounded-sm border border-line px-2 py-1 text-sm text-muted hover:bg-accent-soft"
        >
          Close ✕
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-5">
        {loading && <p className="text-muted">Loading evidence…</p>}
        {!loading && data && !data.document && (
          <p className="text-muted">No source citation for this value.</p>
        )}
        {!loading && data?.document && (
          <>
            <p className="mb-3 text-xs text-muted">
              {data.document.title} · {data.document.doc_category} · extracted by
              Unsiloed
            </p>
            {pageNos.map((pageNo) => {
              const page = data.document!.pages.find((p) => p.page_no === pageNo);
              const pageCits = data.citations.filter((c) => c.page_no === pageNo);
              if (!page) return null;
              return (
                <div key={pageNo} className="mb-6">
                  <CitationViewer
                    documentId={data.document!.id}
                    page={page}
                    citations={pageCits}
                  />
                </div>
              );
            })}
            <div className="mt-2 space-y-2">
              {data.citations.map((c) => (
                <div key={c.id} className="text-sm">
                  <span className="font-mono text-xs text-accent">
                    {c.field_name}
                  </span>
                  {c.extraction_score != null && (
                    <span className="ml-2 text-[10px] text-muted">
                      {(c.extraction_score * 100).toFixed(0)}% confidence
                    </span>
                  )}
                  <p className="text-ink/80">{c.snippet}</p>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
