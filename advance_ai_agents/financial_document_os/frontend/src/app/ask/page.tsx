"use client";

import { useState } from "react";
import { API_URL } from "@/lib/api";
import EvidencePanel, { EvidenceTarget } from "@/components/EvidencePanel";

interface AskResult {
  error: string | null;
  sql: string | null;
  rationale?: string;
  columns?: string[];
  rows?: Record<string, unknown>[];
}

const SAMPLES = [
  "Which vendors did we pay more than $100,000 in total?",
  "Show contracts expiring within the next year",
  "Which investments dropped below their cost basis?",
  "List obligations over $500,000 with their due dates",
  "What did we pay Deloitte across all documents?",
];

function fmt(v: unknown) {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number")
    return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return String(v);
}

export default function AskPage() {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AskResult | null>(null);
  const [showSql, setShowSql] = useState(false);
  const [target, setTarget] = useState<EvidenceTarget | null>(null);

  const run = async (question: string) => {
    setQ(question);
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_URL}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      setResult(await res.json());
    } catch (e) {
      setResult({ error: String(e), sql: null });
    } finally {
      setLoading(false);
    }
  };

  const cols = result?.columns?.filter((c) => c !== "id" && c !== "entity_kind") ?? [];

  return (
    <div className={target ? "lg:pr-[540px]" : ""}>
      <h1 className="font-serif text-4xl">Ask</h1>
      <p className="mt-1 text-sm text-muted">
        Ask in plain English. Answered with SQL over your extracted database —
        not RAG. Every row links to its source evidence.
      </p>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (q.trim()) run(q.trim());
        }}
        className="mt-6 flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Which vendors did we pay more than $100,000?"
          className="flex-1 rounded-sm border border-line bg-card px-4 py-2.5 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-sm bg-accent px-5 py-2.5 text-sm font-bold text-white hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
      </form>

      <div className="mt-3 flex flex-wrap gap-2">
        {SAMPLES.map((s) => (
          <button
            key={s}
            onClick={() => run(s)}
            className="rounded-full border border-line px-3 py-1 text-xs text-muted hover:border-accent hover:text-accent"
          >
            {s}
          </button>
        ))}
      </div>

      {result?.error && (
        <p className="mt-6 rounded-sm border border-accent/40 bg-accent-soft px-4 py-3 text-sm text-accent">
          {result.error}
        </p>
      )}

      {result && !result.error && (
        <div className="mt-6">
          {result.rationale && (
            <p className="mb-2 text-sm italic text-muted">{result.rationale}</p>
          )}
          <div className="overflow-x-auto rounded-sm border border-line">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-paper text-left text-[11px] uppercase tracking-wide text-muted">
                  {cols.map((c) => (
                    <th key={c} className="whitespace-nowrap px-3 py-2 font-bold">
                      {c.replace(/_/g, " ")}
                    </th>
                  ))}
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {(result.rows ?? []).map((row, i) => (
                  <tr key={i} className="border-t border-line hover:bg-paper/60">
                    {cols.map((c) => (
                      <td key={c} className="whitespace-nowrap px-3 py-2 text-ink/80">
                        {fmt(row[c])}
                      </td>
                    ))}
                    <td className="px-3 py-2 text-right">
                      {Boolean(row.entity_kind) && row.id != null && (
                        <button
                          onClick={() =>
                            setTarget({
                              kind: String(row.entity_kind),
                              id: Number(row.id),
                              label: "Query result evidence",
                            })
                          }
                          className="text-[11px] font-bold text-accent hover:underline"
                        >
                          evidence ↗
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(result.rows ?? []).length === 0 && (
              <p className="px-3 py-6 text-center text-muted">No matching rows.</p>
            )}
          </div>

          {result.sql && (
            <div className="mt-3">
              <button
                onClick={() => setShowSql(!showSql)}
                className="text-xs text-muted hover:text-accent"
              >
                {showSql ? "▾" : "▸"} generated SQL
              </button>
              {showSql && (
                <pre className="mt-2 overflow-x-auto rounded-sm border border-line bg-paper p-3 font-mono text-xs text-ink/80">
                  {result.sql}
                </pre>
              )}
            </div>
          )}
        </div>
      )}

      <EvidencePanel target={target} onClose={() => setTarget(null)} />
    </div>
  );
}
