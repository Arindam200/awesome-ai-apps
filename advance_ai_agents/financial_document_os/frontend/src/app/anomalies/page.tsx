"use client";

import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import EvidencePanel, { EvidenceTarget } from "@/components/EvidencePanel";

interface Anomaly {
  id: number;
  rule: string;
  severity: string;
  title: string;
  description: string;
  entity_refs: { entity_kind: string; entity_id: number }[];
  evidence_citation_ids: number[];
}

const SEV_STYLE: Record<string, string> = {
  high: "border-l-accent",
  medium: "border-l-amber-500",
  low: "border-l-line",
};
const SEV_BADGE: Record<string, string> = {
  high: "bg-accent text-white",
  medium: "bg-amber-100 text-amber-800",
  low: "bg-line text-muted",
};

export default function AnomaliesPage() {
  const [items, setItems] = useState<Anomaly[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [target, setTarget] = useState<EvidenceTarget | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/anomalies`)
      .then((r) => r.json())
      .then(setItems)
      .finally(() => setLoaded(true));
  }, []);

  const counts = items.reduce<Record<string, number>>((acc, a) => {
    acc[a.severity] = (acc[a.severity] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className={target ? "lg:pr-[540px]" : ""}>
      <h1 className="font-serif text-4xl">Anomalies</h1>
      <p className="mt-1 text-sm text-muted">
        Inconsistencies found automatically across your documents. Each is backed
        by source evidence.
      </p>

      {loaded && items.length > 0 && (
        <div className="mt-4 flex gap-3 text-sm">
          {["high", "medium", "low"].map(
            (s) =>
              counts[s] && (
                <span key={s} className={`rounded-sm px-2 py-0.5 text-xs font-bold ${SEV_BADGE[s]}`}>
                  {counts[s]} {s}
                </span>
              ),
          )}
        </div>
      )}

      {loaded && items.length === 0 && (
        <p className="mt-12 text-center text-muted">
          No anomalies detected. Process some documents first.
        </p>
      )}

      <div className="mt-6 space-y-3">
        {items.map((a) => (
          <div
            key={a.id}
            className={`rounded-sm border border-line border-l-4 bg-card p-4 ${SEV_STYLE[a.severity] ?? ""}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <span className={`mr-2 rounded-sm px-1.5 py-0.5 text-[10px] font-bold uppercase ${SEV_BADGE[a.severity]}`}>
                  {a.severity}
                </span>
                <span className="font-serif text-lg">{a.title}</span>
                <p className="mt-1 text-sm text-ink/80">{a.description}</p>
              </div>
              {a.entity_refs.length > 0 && a.evidence_citation_ids.length > 0 && (
                <button
                  onClick={() =>
                    setTarget({
                      kind: a.entity_refs[0].entity_kind,
                      id: a.entity_refs[0].entity_id,
                      label: a.title,
                    })
                  }
                  className="shrink-0 text-[11px] font-bold text-accent hover:underline"
                >
                  evidence ↗
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      <EvidencePanel target={target} onClose={() => setTarget(null)} />
    </div>
  );
}
