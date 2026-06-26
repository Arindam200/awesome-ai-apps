"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, Signal } from "@/lib/api";
import { useProject } from "@/components/ProjectProvider";
import { Card } from "@/components/ui/Card";
import { Badge, levelTone } from "@/components/ui/Badge";

const TYPES = ["", "feature_request", "competitor_launch", "ecosystem_mention", "security", "community"];
const SOURCES = ["", "document", "github", "hackernews", "reddit", "osv"];

const selectClass =
  "rounded-[6px] border border-line bg-surface px-3 py-1.5 text-sm text-ink outline-none transition-colors focus:border-primary";

export default function SignalsPage() {
  const { selected } = useProject();
  const [signals, setSignals] = useState<Signal[]>([]);
  const [type, setType] = useState("");
  const [source, setSource] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!selected) return;
    const params = (type ? `&signal_type=${type}` : "") + (source ? `&source_kind=${source}` : "");
    setLoaded(false);
    api.signals(selected.id, params).then(setSignals).finally(() => setLoaded(true));
  }, [selected, type, source]);

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">Signals</h1>
        <div className="flex gap-2">
          <select value={type} onChange={(e) => setType(e.target.value)} className={selectClass}>
            {TYPES.map((t) => (
              <option key={t} value={t}>
                {t ? t.replace("_", " ") : "all types"}
              </option>
            ))}
          </select>
          <select value={source} onChange={(e) => setSource(e.target.value)} className={selectClass}>
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {s || "all sources"}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loaded && signals.length === 0 && (
        <p className="mt-12 text-center font-mono text-xs uppercase tracking-[0.16em] text-faint">
          No signals yet — run the pipeline from the Brief page.
        </p>
      )}

      <div className="mt-6 space-y-3">
        {signals.map((s) => (
          <Link key={s.id} href={`/citations/${s.id}`} className="block">
            <Card hover className="p-4">
              <div className="flex items-center justify-between gap-4">
                <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-faint">
                  {s.signal_type.replace("_", " ")} · {s.source_kind}
                </span>
                <span className="flex items-center gap-2">
                  {s.citation_count > 0 && (
                    <Badge tone="blue">
                      {s.citation_count} citation{s.citation_count > 1 ? "s" : ""}
                    </Badge>
                  )}
                  {s.urgency && ["high", "critical"].includes(s.urgency) && (
                    <Badge tone={levelTone(s.urgency)}>{s.urgency}</Badge>
                  )}
                </span>
              </div>
              <h2 className="mt-1.5 font-display text-lg font-semibold text-ink">{s.title}</h2>
              {s.summary && <p className="mt-1 line-clamp-2 text-sm text-muted">{s.summary}</p>}
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
