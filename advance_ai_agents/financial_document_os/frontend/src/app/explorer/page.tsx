"use client";

import { useEffect, useState } from "react";
import {
  EntityKind,
  EntityTable,
  ENTITY_LABELS,
  api,
} from "@/lib/api";
import EvidencePanel, { EvidenceTarget } from "@/components/EvidencePanel";

function fmtHeader(col: string) {
  return col.replace(/_/g, " ");
}

function fmtValue(v: unknown) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "number")
    return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return String(v);
}

export default function ExplorerPage() {
  const [kinds, setKinds] = useState<EntityKind[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [table, setTable] = useState<EntityTable | null>(null);
  const [target, setTarget] = useState<EvidenceTarget | null>(null);

  useEffect(() => {
    api.entityKinds().then((k) => {
      setKinds(k);
      const first = k.find((x) => x.count > 0) ?? k[0];
      if (first) setActive(first.kind);
    });
  }, []);

  useEffect(() => {
    if (active) api.entities(active).then(setTable);
  }, [active]);

  return (
    <div className={target ? "lg:pr-[540px]" : ""}>
      <h1 className="font-serif text-4xl">Entity Explorer</h1>
      <p className="mt-1 text-sm text-muted">
        Your documents, as a database. Click any highlighted value to see it in
        the source PDF.
      </p>

      <div className="mt-6 flex flex-wrap gap-2 border-b border-line">
        {kinds.map((k) => (
          <button
            key={k.kind}
            onClick={() => setActive(k.kind)}
            className={`-mb-px border-b-2 px-3 py-2 text-sm ${
              active === k.kind
                ? "border-accent font-bold text-ink"
                : "border-transparent text-muted hover:text-ink"
            }`}
          >
            {ENTITY_LABELS[k.kind] ?? k.kind}
            <span className="ml-1.5 text-xs text-muted">{k.count}</span>
          </button>
        ))}
      </div>

      {table && (
        <div className="mt-4 overflow-x-auto rounded-sm border border-line">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-paper text-left text-[11px] uppercase tracking-wide text-muted">
                {table.columns.map((c) => (
                  <th key={c} className="whitespace-nowrap px-3 py-2 font-bold">
                    {fmtHeader(c)}
                  </th>
                ))}
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => (
                <tr key={row.id} className="border-t border-line hover:bg-paper/60">
                  {table.columns.map((c) => {
                    const cited = (row.cited_fields as string[]).includes(c);
                    return (
                      <td key={c} className="whitespace-nowrap px-3 py-2">
                        {cited ? (
                          <button
                            onClick={() =>
                              setTarget({
                                kind: table.kind,
                                id: row.id,
                                field: c,
                                label: `${fmtHeader(c)}: ${fmtValue(row[c])}`,
                              })
                            }
                            className="rounded-sm px-1 text-left text-accent underline decoration-dotted underline-offset-2 hover:bg-accent-soft"
                            title="View source evidence"
                          >
                            {fmtValue(row[c])}
                          </button>
                        ) : (
                          <span className="text-ink/80">{fmtValue(row[c])}</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="px-3 py-2 text-right">
                    <button
                      onClick={() =>
                        setTarget({
                          kind: table.kind,
                          id: row.id,
                          label: `${ENTITY_LABELS[table.kind]} #${row.id}`,
                        })
                      }
                      className="text-[11px] font-bold text-accent hover:underline"
                    >
                      evidence ↗
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {table.rows.length === 0 && (
            <p className="px-3 py-6 text-center text-muted">
              No {ENTITY_LABELS[table.kind]?.toLowerCase()} extracted yet.
            </p>
          )}
        </div>
      )}

      <EvidencePanel target={target} onClose={() => setTarget(null)} />
    </div>
  );
}
