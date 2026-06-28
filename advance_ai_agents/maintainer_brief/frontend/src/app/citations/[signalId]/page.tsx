"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ArrowUpRight } from "lucide-react";
import { api, Signal } from "@/lib/api";
import CitationViewer from "@/components/CitationViewer";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { SectionLabel } from "@/components/ui/SectionLabel";

function ConfidenceDots({ score }: { score: number | null }) {
  if (score == null) return null;
  const filled = Math.round(score * 5);
  return (
    <span className="inline-flex items-center gap-1" title={`confidence ${(score * 100).toFixed(0)}%`}>
      {[...Array(5)].map((_, i) => (
        <span key={i} className={`h-1.5 w-1.5 rounded-full ${i < filled ? "bg-primary" : "bg-line"}`} />
      ))}
      <span className="ml-1 font-mono text-[10px] text-muted">{(score * 100).toFixed(0)}%</span>
    </span>
  );
}

export default function CitationPage({ params }: { params: Promise<{ signalId: string }> }) {
  const { signalId } = use(params);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [error, setError] = useState(false);
  const [activePage, setActivePage] = useState<number | null>(null);

  useEffect(() => {
    api.signal(Number(signalId)).then(setSignal).catch(() => setError(true));
  }, [signalId]);

  if (error)
    return <p className="font-mono text-xs uppercase tracking-[0.16em] text-faint">Signal not found.</p>;
  if (!signal)
    return <p className="font-mono text-xs uppercase tracking-[0.16em] text-faint">Loading…</p>;

  const citations = signal.citations ?? [];
  const pages = signal.document?.pages ?? [];
  const citedPageNos = [...new Set(citations.map((c) => c.page_no))].sort((a, b) => a - b);
  const currentPageNo = activePage ?? citedPageNos[0] ?? pages[0]?.page_no;
  const currentPage = pages.find((p) => p.page_no === currentPageNo);
  const pageCitations = citations.filter((c) => c.page_no === currentPageNo);

  if (!signal.document) {
    return (
      <div className="mx-auto max-w-2xl">
        <SignalPanel signal={signal} />
        {signal.source_url && (
          <a
            href={signal.source_url}
            target="_blank"
            rel="noreferrer"
            className="mt-6 inline-flex items-center justify-center gap-2 rounded-[6px] bg-primary px-5 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-primary-hover"
          >
            Open original source
            <ArrowUpRight size={15} />
          </a>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
      <div>
        <SignalPanel signal={signal} />

        <Card className="mt-6 p-5">
          <SectionLabel label="Source document" />
          <p className="mt-3 font-display text-base font-semibold text-ink">{signal.document.title}</p>
          <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.1em] text-faint">
            {signal.document.doc_category ?? "document"} · {signal.document.page_count ?? "?"} pages · parsed by Unsiloed
          </p>
          {citedPageNos.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {citedPageNos.map((p) => (
                <button
                  key={p}
                  onClick={() => setActivePage(p)}
                  className={`rounded-[5px] border px-2 py-1 font-mono text-[11px] transition-colors ${
                    p === currentPageNo
                      ? "border-primary bg-primary text-white"
                      : "border-line text-muted hover:border-primary hover:text-primary"
                  }`}
                >
                  p.{p}
                </button>
              ))}
            </div>
          )}
        </Card>

        {pageCitations.length > 0 && (
          <Card className="mt-6 p-5">
            <SectionLabel label="Citations on this page" />
            <ul className="mt-4 space-y-3">
              {pageCitations.map((c) => (
                <li key={c.id} className="text-sm">
                  <span className="font-mono text-[11px] uppercase tracking-[0.1em] text-primary">
                    {c.field_name}
                  </span>
                  <p className="mt-0.5 text-ink/80">{c.snippet}</p>
                </li>
              ))}
            </ul>
          </Card>
        )}
      </div>

      <div>
        {currentPage ? (
          <CitationViewer documentId={signal.document.id} page={currentPage} citations={pageCitations} />
        ) : (
          <Card className="p-10 text-center text-sm text-muted">
            {citations.length > 0
              ? "Page images not rendered yet — re-run the pipeline."
              : "This extraction returned no bounding-box citations."}
          </Card>
        )}
      </div>
    </div>
  );
}

function SignalPanel({ signal }: { signal: Signal }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-faint">
          {signal.signal_type.replace("_", " ")} · {signal.source_kind}
        </span>
        <ConfidenceDots score={signal.confidence} />
      </div>
      <h1 className="mt-2 font-display text-2xl font-semibold leading-snug text-ink">{signal.title}</h1>
      {signal.summary && (
        <p className="mt-3 text-sm leading-relaxed text-ink/80">{signal.summary}</p>
      )}
      <div className="mt-4 flex flex-wrap gap-2">
        {signal.urgency && <Badge tone="neutral">urgency · {signal.urgency}</Badge>}
        {signal.category && <Badge tone="neutral">{signal.category}</Badge>}
      </div>
      <Link
        href="/signals"
        className="mt-4 inline-flex items-center gap-1 font-mono text-[11px] uppercase tracking-[0.12em] text-primary"
      >
        <ArrowLeft size={12} /> All signals
      </Link>
    </Card>
  );
}
