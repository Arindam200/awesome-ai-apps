"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Signal } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";

const TYPES = [
  "",
  "feature_request",
  "competitor_launch",
  "ecosystem_mention",
  "security",
  "community",
];
const SOURCES = ["", "document", "github", "hackernews", "reddit", "osv"];

export default function SignalsPage() {
  const { selected } = useProject();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [type, setType] = useState("");
  const [source, setSource] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!selected) return;
    const params =
      (type ? `&signal_type=${type}` : "") +
      (source ? `&source_kind=${source}` : "");
    setLoaded(false);
    api
      .signals(selected.id, params)
      .then(setSignals)
      .finally(() => setLoaded(true));
  }, [selected, type, source]);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="font-serif text-3xl">Signals</h1>
        <div className="flex gap-3">
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="rounded-sm border border-line bg-card px-3 py-1.5 text-sm"
          >
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t ? t.replace("_", " ") : "all types"}
              </option>
            ))}
          </select>
          <select
            value={source}
            onChange={(e) => setSource(e.target.value)}
            className="rounded-sm border border-line bg-card px-3 py-1.5 text-sm"
          >
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {s || "all sources"}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loaded && signals.length === 0 && (
        <p className="mt-12 text-center text-muted">
          No signals yet — run the pipeline from the Brief page.
        </p>
      )}

      <div className="mt-6 space-y-3">
        {signals.map((s) => (
          <Link
            key={s.id}
            href={`/citations/${s.id}`}
            className="block rounded-sm border border-line bg-card p-4 transition-colors hover:border-accent"
          >
            <div className="flex items-center justify-between gap-4">
              <span className="text-[10px] font-bold uppercase tracking-[1.5px] text-muted">
                {s.signal_type.replace("_", " ")} · {s.source_kind}
              </span>
              <span className="flex items-center gap-2">
                {s.citation_count > 0 && (
                  <span className="rounded-sm bg-accent-soft px-2 py-0.5 text-[10px] font-bold text-accent">
                    {s.citation_count} citation{s.citation_count > 1 ? "s" : ""}
                  </span>
                )}
                {s.urgency && ["high", "critical"].includes(s.urgency) && (
                  <span className="text-[10px] font-bold uppercase text-accent">
                    {s.urgency}
                  </span>
                )}
              </span>
            </div>
            <h2 className="mt-1 font-serif text-lg">{s.title}</h2>
            {s.summary && (
              <p className="mt-1 line-clamp-2 text-sm text-muted">
                {s.summary}
              </p>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
