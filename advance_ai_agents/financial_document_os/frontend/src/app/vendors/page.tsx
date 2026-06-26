"use client";

import { useEffect, useState } from "react";
import { API_URL, ENTITY_LABELS, EntityRow } from "@/lib/api";
import EvidencePanel, { EvidenceTarget } from "@/components/EvidencePanel";

interface VendorSummary {
  id: number;
  name: string;
  address: string | null;
  tax_id: string | null;
  document_count: number;
  counts: Record<string, number>;
  total_paid: number;
}

interface Reference extends EntityRow {
  kind: string;
  columns: string[];
}

function money(n: number) {
  return n.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
}

export default function VendorsPage() {
  const [vendors, setVendors] = useState<VendorSummary[]>([]);
  const [openId, setOpenId] = useState<number | null>(null);
  const [refs, setRefs] = useState<Reference[]>([]);
  const [target, setTarget] = useState<EvidenceTarget | null>(null);

  useEffect(() => {
    fetch(`${API_URL}/vendors`).then((r) => r.json()).then(setVendors).catch(() => {});
  }, []);

  const openVendor = async (id: number) => {
    if (openId === id) {
      setOpenId(null);
      return;
    }
    setOpenId(id);
    const data = await fetch(`${API_URL}/vendors/${id}/references`).then((r) => r.json());
    setRefs(data.references);
  };

  return (
    <div className={target ? "lg:pr-[540px]" : ""}>
      <h1 className="font-serif text-4xl">Vendors</h1>
      <p className="mt-1 text-sm text-muted">
        The same party, resolved across every document it appears in. Each
        reference links to its source evidence.
      </p>

      <div className="mt-6 space-y-3">
        {vendors.map((v) => (
          <div key={v.id} className="rounded-sm border border-line bg-card">
            <button
              onClick={() => openVendor(v.id)}
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-paper/60"
            >
              <div>
                <span className="font-serif text-lg">{v.name}</span>
                {v.address && (
                  <span className="ml-2 text-xs text-muted">{v.address}</span>
                )}
              </div>
              <div className="flex items-center gap-4 text-sm">
                {v.total_paid > 0 && (
                  <span className="font-mono text-ink">{money(v.total_paid)} paid</span>
                )}
                <span className="rounded-sm bg-accent-soft px-2 py-0.5 text-xs font-bold text-accent">
                  {v.document_count} doc{v.document_count === 1 ? "" : "s"}
                </span>
                <span className="text-muted">{openId === v.id ? "▾" : "▸"}</span>
              </div>
            </button>

            {openId === v.id && (
              <div className="border-t border-line px-4 py-3">
                <div className="mb-2 flex flex-wrap gap-2 text-[11px] text-muted">
                  {Object.entries(v.counts).map(([k, n]) => (
                    <span key={k} className="rounded-sm bg-paper px-2 py-0.5">
                      {n} {ENTITY_LABELS[k]?.toLowerCase() ?? k}
                    </span>
                  ))}
                </div>
                <table className="w-full text-sm">
                  <tbody>
                    {refs.map((r) => {
                      const main = r.columns.find((c) =>
                        ["amount", "contract_value", "current_value", "principal_amount"].includes(c),
                      );
                      const label = r.columns.slice(0, 3).map((c) => r[c]).filter(Boolean).join(" · ");
                      return (
                        <tr key={`${r.kind}-${r.id}`} className="border-t border-line/60">
                          <td className="py-1.5 pr-3">
                            <span className="text-[10px] font-bold uppercase tracking-wide text-accent">
                              {ENTITY_LABELS[r.kind] ?? r.kind}
                            </span>
                          </td>
                          <td className="py-1.5 pr-3 text-ink/80">{label || `#${r.id}`}</td>
                          <td className="py-1.5 text-right">
                            <button
                              onClick={() =>
                                setTarget({ kind: r.kind, id: r.id, field: main || undefined,
                                  label: `${v.name} — ${ENTITY_LABELS[r.kind]}` })
                              }
                              className="text-[11px] font-bold text-accent hover:underline"
                            >
                              evidence ↗
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        ))}
      </div>

      <EvidencePanel target={target} onClose={() => setTarget(null)} />
    </div>
  );
}
