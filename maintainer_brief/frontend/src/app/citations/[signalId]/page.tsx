"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, Signal } from "@/lib/api";
import CitationViewer from "@/components/CitationViewer";

function ConfidenceDots({ score }: { score: number | null }) {
  if (score == null) return null;
  const filled = Math.round(score * 5);
  return (
    <span className="inline-flex items-center gap-1" title={`confidence ${(score * 100).toFixed(0)}%`}>
      {[...Array(5)].map((_, i) => (
        <span
          key={i}
          className={`h-1.5 w-1.5 rounded-full ${i < filled ? "bg-accent" : "bg-line"}`}
        />
      ))}
      <span className="ml-1 text-xs text-muted">{(score * 100).toFixed(0)}%</span>
    </span>
  );
}

export default function CitationPage({
  params,
}: {
  params: Promise<{ signalId: string }>;
}) {
  const { signalId } = use(params);
  const [signal, setSignal] = useState<Signal | null>(null);
  const [error, setError] = useState(false);
  const [activePage, setActivePage] = useState<number | null>(null);

  useEffect(() => {
    api
      .signal(Number(signalId))
      .then(setSignal)
      .catch(() => setError(true));
  }, [signalId]);

  if (error) return <p className="text-muted">Signal not found.</p>;
  if (!signal) return <p className="text-muted">Loading…</p>;

  const citations = signal.citations ?? [];
  const pages = signal.document?.pages ?? [];
  const citedPageNos = [...new Set(citations.map((c) => c.page_no))].sort(
    (a, b) => a - b,
  );
  const currentPageNo = activePage ?? citedPageNos[0] ?? pages[0]?.page_no;
  const currentPage = pages.find((p) => p.page_no === currentPageNo);
  const pageCitations = citations.filter((c) => c.page_no === currentPageNo);

  // Signal from an API source (GitHub/HN/...) — no document to show
  if (!signal.document) {
    return (
      <div className="mx-auto max-w-2xl">
        <SignalPanel signal={signal} />
        {signal.source_url && (
          <a
            href={signal.source_url}
            target="_blank"
            rel="noreferrer"
            className="mt-6 inline-block rounded-sm bg-accent px-4 py-2 text-sm font-bold text-white"
          >
            Open original source ↗
          </a>
        )}
      </div>
    );
  }

  return (
    <div className="grid gap-8 lg:grid-cols-[380px_1fr]">
      <div>
        <SignalPanel signal={signal} />

        <div className="mt-6 rounded-sm border border-line bg-card p-5">
          <h3 className="text-xs font-bold uppercase tracking-[1.5px] text-accent">
            Source document
          </h3>
          <p className="mt-2 font-serif text-base">{signal.document.title}</p>
          <p className="mt-1 text-xs text-muted">
            {signal.document.doc_category ?? "document"} ·{" "}
            {signal.document.page_count ?? "?"} pages · parsed by Unsiloed
          </p>
          {citedPageNos.length > 1 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {citedPageNos.map((p) => (
                <button
                  key={p}
                  onClick={() => setActivePage(p)}
                  className={`rounded-sm border px-2 py-1 text-xs ${
                    p === currentPageNo
                      ? "border-accent bg-accent text-white"
                      : "border-line hover:bg-accent-soft"
                  }`}
                >
                  p.{p}
                </button>
              ))}
            </div>
          )}
        </div>

        {pageCitations.length > 0 && (
          <div className="mt-6 rounded-sm border border-line bg-card p-5">
            <h3 className="text-xs font-bold uppercase tracking-[1.5px] text-accent">
              Citations on this page
            </h3>
            <ul className="mt-3 space-y-3">
              {pageCitations.map((c) => (
                <li key={c.id} className="text-sm">
                  <span className="font-mono text-xs text-accent">
                    {c.field_name}
                  </span>
                  <p className="mt-0.5 text-ink/80">{c.snippet}</p>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div>
        {currentPage ? (
          <CitationViewer
            documentId={signal.document.id}
            page={currentPage}
            citations={pageCitations}
          />
        ) : (
          <div className="rounded-sm border border-line bg-card p-10 text-center text-muted">
            {citations.length > 0
              ? "Page images not rendered yet — re-run the pipeline."
              : "This extraction returned no bounding-box citations."}
          </div>
        )}
      </div>
    </div>
  );
}

function SignalPanel({ signal }: { signal: Signal }) {
  return (
    <div className="rounded-sm border border-line bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-bold uppercase tracking-[1.5px] text-muted">
          {signal.signal_type.replace("_", " ")} · {signal.source_kind}
        </span>
        <ConfidenceDots score={signal.confidence} />
      </div>
      <h1 className="mt-2 font-serif text-2xl leading-snug">{signal.title}</h1>
      {signal.summary && (
        <p className="mt-3 text-sm leading-relaxed text-ink/80">
          {signal.summary}
        </p>
      )}
      <dl className="mt-4 grid grid-cols-2 gap-2 text-xs text-muted">
        {signal.urgency && (
          <div>
            <dt className="font-bold uppercase tracking-wider">Urgency</dt>
            <dd>{signal.urgency}</dd>
          </div>
        )}
        {signal.category && (
          <div>
            <dt className="font-bold uppercase tracking-wider">Category</dt>
            <dd>{signal.category}</dd>
          </div>
        )}
      </dl>
      <Link href="/signals" className="mt-4 inline-block text-xs text-accent">
        ← All signals
      </Link>
    </div>
  );
}
