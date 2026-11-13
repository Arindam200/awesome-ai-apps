"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { lockDown } from "@/lib/csp";
import { modelName } from "@/lib/model-name";
import type { Run } from "@/lib/runs";
import type { Netlist } from "@/lib/schema/circuit";
import { toSpice } from "@/lib/sim/spice";
import { lineDiff } from "@/lib/diff";
import { Icon } from "./Icon";

const STEPS: { key: Run["status"]; label: string }[] = [
  { key: "reading", label: "Read" },
  { key: "checking", label: "Check" },
  { key: "building", label: "Build" },
  { key: "looking", label: "Look" },
  { key: "done", label: "Done" },
];

const VERDICT = {
  confirmed: { cls: "ok", text: "Confirmed by solver" },
  not_reproduced: { cls: "bad", text: "Solver did not reproduce it" },
  model_only: { cls: "info", text: "Visual only, not a solver check" },
} as const;

const KIND: Record<string, string> = {
  no_current_limit: "No current limit",
  reversed_polarity: "Backwards part",
  short_circuit: "Short circuit",
  open_circuit: "Open circuit",
  missing_value: "Missing value",
  ambiguous_symbol: "Unclear symbol",
  other: "Other",
};

type Tab = "sim" | "look" | "netlist" | "source" | "log";

export function RunView({ initial }: { initial: Run }) {
  const [run, setRun] = useState(initial);
  const [tab, setTab] = useState<Tab>("sim");
  const [hot, setHot] = useState<string[]>([]);
  const live = run.status !== "done" && run.status !== "failed";

  useEffect(() => {
    if (!live) return;
    const t = setInterval(async () => {
      const res = await fetch(`/api/runs/${run.id}`, { cache: "no-store" });
      if (res.ok) setRun(await res.json());
    }, 1500);
    return () => clearInterval(t);
  }, [live, run.id]);

  // Live clock while the run works, so a long reasoning call does not look stuck.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [live]);

  const router = useRouter();
  const [again, setAgain] = useState<"idle" | "busy" | string>("idle");
  async function runAgain() {
    setAgain("busy");
    const res = await fetch("/api/runs", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ again: run.id }) });
    const body = (await res.json().catch(() => ({}))) as { id?: string; error?: string };
    if (body.id) router.push(`/run/${body.id}`);
    else setAgain(body.error ?? "Could not start a new run.");
  }

  const who = modelName(run.model ?? run.calls[0]?.model);
  const elapsed = Math.max(0, Math.round((now - Date.parse(run.createdAt)) / 1000));
  const stepIndex = STEPS.findIndex((s) => s.key === run.status);
  const parts = run.read?.asDrawn.components ?? [];
  const file = (name: string) => `/api/runs/${run.id}/files/${name}`;

  return (
    <div className="stack" style={{ paddingTop: 24 }}>
      <div className="spread">
        <div className="stack" style={{ gap: 4 }}>
          <h2>{run.read?.title ?? run.sketch.source?.name ?? "Reading the sketch"}</h2>
          {run.read?.summary && <p className="muted" style={{ margin: 0 }}>{run.read.summary}</p>}
        </div>
        <div className="steps" aria-label="Progress">
          {STEPS.map((s, i) => (
            <span key={s.key} className={`step${run.status === "failed" ? "" : i < stepIndex || run.status === "done" ? " done" : i === stepIndex ? " now" : ""}`}>
              {run.status !== "failed" && (i < stepIndex || run.status === "done") && <Icon name="ok" size={12} />}
              {s.label}
            </span>
          ))}
        </div>
      </div>

      {live && (
        <p className="status run small" style={{ margin: 0 }} aria-live="polite">
          <span className="pulse" aria-hidden="true" />
          {run.progress.stage}
          {run.progress.chars > 0
            ? ` · writing, ${run.progress.chars.toLocaleString()} characters`
            : (run.progress.thought ?? 0) > 0
              ? ` · thinking, ${run.progress.thought!.toLocaleString()} characters of reasoning`
              : " · waiting for the model"}
          <span className="faint"> · {clock(elapsed)}</span>
        </p>
      )}
      {run.status === "failed" && (
        <div className="error-box small stack" style={{ gap: 12 }}>
          <span>
            <strong>The run stopped.</strong> {run.error}
          </span>
          <span className="row">
            <button className="btn" onClick={runAgain} disabled={again === "busy"}>
              <Icon name="play" /> {again === "busy" ? "Starting" : "Run again"}
            </button>
            {again !== "idle" && again !== "busy" && <span className="faint caption">{again}</span>}
          </span>
        </div>
      )}

      <div className="workspace">
        <aside className="stack">
          <div className="sketch">
            <img src={file("sketch.jpg")} alt="The sketch" />
            {parts.map((c) =>
              c.box ? (
                <div
                  key={c.id}
                  className={`box${hot.includes(c.id) ? " hot" : ""}`}
                  style={{ left: `${c.box[0] * 100}%`, top: `${c.box[1] * 100}%`, width: `${c.box[2] * 100}%`, height: `${c.box[3] * 100}%` }}
                >
                  <span>{c.id}</span>
                </div>
              ) : null,
            )}
          </div>
          {run.sketch.source?.url && (
            <p className="faint caption" style={{ margin: 0 }}>
              Source: <a href={run.sketch.source.url} target="_blank" rel="noreferrer">{run.sketch.source.name}</a>
              {run.sketch.source.author && ` by ${run.sketch.source.author}`}
              {run.sketch.source.licence && `, ${run.sketch.source.licence}`}
            </p>
          )}

          {run.check && (
            <div className="stack" style={{ gap: 10 }}>
              <h4>Mistakes</h4>
              {run.check.issues.length === 0 && run.check.solverOnly.length === 0 && <p className="muted small">None found.</p>}
              {run.check.issues.map((issue, i) => (
                <div key={i} className="issue" onMouseEnter={() => setHot(issue.componentIds)} onMouseLeave={() => setHot([])}>
                  <div className="row" style={{ gap: 8 }}>
                    <strong className="small">{KIND[issue.kind]}</strong>
                    <span className="faint caption">{issue.componentIds.join(", ")}</span>
                  </div>
                  <span className="small">{issue.explanation}</span>
                  {issue.fix && <span className="muted small">Fix: {issue.fix}</span>}
                  <span>
                    <span className={`badge ${VERDICT[issue.verdict].cls}`}>{VERDICT[issue.verdict].text}</span>
                  </span>
                  {issue.evidence && <span className="faint caption">{issue.evidence}</span>}
                </div>
              ))}
              {run.check.solverOnly.map((f, i) => (
                <div key={`s${i}`} className="issue" onMouseEnter={() => setHot(f.componentIds)} onMouseLeave={() => setHot([])}>
                  <strong className="small">{KIND[f.kind]}</strong>
                  <span className="small">{f.detail}</span>
                  <span>
                    <span className="badge maybe">Found by the solver, missed by the model</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </aside>

        <section className="stack">
          <div className="tabs" role="tablist">
            <TabButton id="sim" tab={tab} set={setTab} icon="play">Simulation</TabButton>
            <TabButton id="look" tab={tab} set={setTab} icon="eye">Vision loop{run.rounds.length ? ` (${run.rounds.length})` : ""}</TabButton>
            <TabButton id="netlist" tab={tab} set={setTab} icon="cpu">Netlist</TabButton>
            <TabButton id="source" tab={tab} set={setTab} icon="code">Source</TabButton>
            <TabButton id="log" tab={tab} set={setTab} icon="list">Run log</TabButton>
          </div>
          {tab === "sim" && <SimTab run={run} file={file} who={who} />}
          {tab === "look" && <LookTab run={run} file={file} who={who} />}
          {tab === "netlist" && <NetlistTab run={run} />}
          {tab === "source" && <SourceTab run={run} file={file} />}
          {tab === "log" && <LogTab run={run} />}
        </section>
      </div>
    </div>
  );
}

function TabButton({ id, tab, set, icon, children }: { id: Tab; tab: Tab; set: (t: Tab) => void; icon: Parameters<typeof Icon>[0]["name"]; children: React.ReactNode }) {
  return (
    <button className="tab" role="tab" aria-selected={tab === id} onClick={() => set(id)}>
      <Icon name={icon} /> {children}
    </button>
  );
}

function useText(url: string | null) {
  const [text, setText] = useState<string | null>(null);
  useEffect(() => {
    if (!url) return setText(null);
    let alive = true;
    fetch(url).then((r) => (r.ok ? r.text() : null)).then((t) => alive && setText(t));
    return () => {
      alive = false;
    };
  }, [url]);
  return text;
}

function SimTab({ run, file, who }: { run: Run; file: (n: string) => string; who: string }) {
  const last = run.rounds.at(-1);
  const html = useText(last ? file(last.file) : null);
  if (!last) return <p className="muted">{run.status === "failed" ? "No simulation: the run stopped before the build step finished." : `The simulation appears here once ${who} has built it.`}</p>;
  const values = last.shots.reduce((n, s) => n + s.mismatches.length, 0);
  const errors = last.shots.reduce((n, s) => n + s.errors.length, 0);
  return (
    <div className="stack">
      <div className="row">
        {run.result ? (
          run.result.agrees ? (
            <span className="badge ok"><Icon name="ok" size={12} /> Solver agrees with every value it checked</span>
          ) : (
            <span className="badge maybe"><Icon name="warn" size={12} /> {values} values differ from the solver{errors ? `, ${errors} page errors` : ""}</span>
          )
        ) : (
          <span className="badge info">Round {last.n}, still checking</span>
        )}
        <span className="faint caption">Built by {who}, round {last.n} of {run.rounds.length}. Runs offline in a sandbox.</span>
      </div>
      {html && <iframe className="frame" title="Circuit simulation" sandbox="allow-scripts" srcDoc={lockDown(html)} />}
    </div>
  );
}

function LookTab({ run, file, who }: { run: Run; file: (n: string) => string; who: string }) {
  if (!run.rounds.length) return <p className="muted">Each round, the app screenshots the simulation and {who} reviews it against the sketch and the solver.</p>;
  return (
    <div className="stack" style={{ gap: 32 }}>
      {run.rounds.map((r) => (
        <div key={r.n} className="stack">
          <div className="spread">
            <h4>Round {r.n}</h4>
            {r.review ? (
              <span className={`badge ${r.review.ok ? "ok" : "maybe"}`}>{r.review.ok ? `${who}: looks right` : `${who}: ${r.review.problems.length || "some"} fixes`}</span>
            ) : (
              <span className="badge info">{r.n === run.rounds.length && run.status === "done" ? "Final round, checked by the solver only" : "Waiting for review"}</span>
            )}
          </div>
          <div className="shots">
            {r.shots.map((s) => (
              <div key={s.file} className="shot">
                <a href={file(s.file)} target="_blank" rel="noreferrer">
                  <img src={file(s.file)} alt={s.label} />
                </a>
                <span className="small">{s.label}</span>
                <span className={`caption status ${s.mismatches.length || s.errors.length ? "maybe" : "ok"}`}>
                  {s.mismatches.length ? `${s.mismatches.length} values differ from the solver` : "Matches the solver"}
                  {s.errors.length ? ` · ${s.errors.length} errors` : ""}
                </span>
              </div>
            ))}
          </div>
          {r.review && r.review.problems.length > 0 && (
            <ul className="small muted" style={{ margin: 0, paddingLeft: 20 }}>
              {r.review.problems.map((p, i) => <li key={i}>{p}</li>)}
            </ul>
          )}
          {r.shots.some((s) => s.mismatches.length) && (
            <details className="small">
              <summary className="muted">Values that differ</summary>
              <pre className="code">
                {r.shots.flatMap((s) => s.mismatches.map((m) => `${s.label}: ${m.what}: solver ${m.expected.toPrecision(4)}, simulation ${m.got == null ? "missing" : m.got.toPrecision(4)}`)).join("\n")}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}

function download(name: string, text: string) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

function NetlistTab({ run }: { run: Run }) {
  const [which, setWhich] = useState<"fixed" | "asDrawn">("fixed");
  if (!run.read) return <p className="muted">The netlist appears once the sketch has been read.</p>;
  const netlist: Netlist = run.read[which];
  return (
    <div className="stack">
      <div className="spread">
        <div className="tabs" role="tablist" style={{ borderBottom: 0 }}>
          <button className="tab" role="tab" aria-selected={which === "fixed"} onClick={() => setWhich("fixed")}>Fixed</button>
          <button className="tab" role="tab" aria-selected={which === "asDrawn"} onClick={() => setWhich("asDrawn")}>As drawn</button>
        </div>
        <div className="row">
          <button className="btn" onClick={() => download(`${run.id}-${which}.cir`, toSpice(netlist, run.read!.title))}>
            <Icon name="download" /> SPICE deck
          </button>
          <button className="btn" onClick={() => download(`${run.id}.json`, JSON.stringify(run.read, null, 2))}>
            <Icon name="download" /> JSON
          </button>
        </div>
      </div>
      <p className="faint caption" style={{ margin: 0 }}>
        Read via {run.via === "tool" ? "the submit_circuit tool call" : "JSON in the reply text"}
        {run.repaired ? ", after one repair turn" : ""}.
      </p>
      <pre className="code">{JSON.stringify(netlist, null, 2)}</pre>
    </div>
  );
}

function SourceTab({ run, file }: { run: Run; file: (n: string) => string }) {
  const [n, setN] = useState(run.rounds.length);
  const [diff, setDiff] = useState(false);
  const cur = useText(n ? file(`round-${n}.html`) : null);
  const prev = useText(n > 1 ? file(`round-${n - 1}.html`) : null);
  const lines = useMemo(() => (diff && cur && prev ? lineDiff(prev, cur) : null), [diff, cur, prev]);
  if (!run.rounds.length) return <p className="muted">The generated source appears here.</p>;
  return (
    <div className="stack">
      <div className="row">
        <select value={n} onChange={(e) => setN(Number(e.target.value))} className="btn" aria-label="Round">
          {run.rounds.map((r) => <option key={r.n} value={r.n}>Round {r.n}</option>)}
        </select>
        {n > 1 && (
          <label className="row small" style={{ gap: 6 }}>
            <input type="checkbox" checked={diff} onChange={(e) => setDiff(e.target.checked)} /> Changes from round {n - 1}
          </label>
        )}
        {cur && <span className="faint caption">{cur.split("\n").length.toLocaleString()} lines</span>}
      </div>
      <pre className="code">
        {lines
          ? lines.map((l, i) => (
              <div key={i} className={l.op === "+" ? "diff-add" : l.op === "-" ? "diff-del" : "faint"}>
                {l.op} {l.text}
              </div>
            ))
          : cur}
      </pre>
    </div>
  );
}

function LogTab({ run }: { run: Run }) {
  const total = run.calls.reduce(
    (t, c) => ({ ms: t.ms + c.ms, input: t.input + c.usage.input, cached: t.cached + c.usage.cachedInput, output: t.output + c.usage.output, reasoning: t.reasoning + c.usage.reasoning, cost: c.cost == null || t.cost == null ? null : t.cost + c.cost }),
    { ms: 0, input: 0, cached: 0, output: 0, reasoning: 0, cost: 0 as number | null },
  );
  const n = (x: number) => x.toLocaleString();
  const cost = (x: number | null) => (x == null ? "price not set" : x === 0 ? "free" : `$${x.toFixed(4)}`);
  return (
    <div className="stack">
      <div className="scroll-x">
        <table className="log">
          <thead>
            <tr><th>Call</th><th>Time</th><th>Input</th><th>Cached</th><th>Output</th><th>Reasoning</th><th>Cost</th></tr>
          </thead>
          <tbody>
            {run.calls.map((c, i) => (
              <tr key={i}>
                <td>{c.stage}{c.error ? ` (failed: ${c.error.slice(0, 60)})` : ""}</td>
                <td>{(c.ms / 1000).toFixed(1)} s</td>
                <td>{n(c.usage.input)}</td>
                <td>{n(c.usage.cachedInput)}</td>
                <td>{n(c.usage.output)}</td>
                <td>{n(c.usage.reasoning)}</td>
                <td>{cost(c.cost)}</td>
              </tr>
            ))}
            <tr>
              <td><strong>Total</strong></td>
              <td>{(total.ms / 1000).toFixed(1)} s</td>
              <td>{n(total.input)}</td>
              <td>{n(total.cached)}</td>
              <td>{n(total.output)}</td>
              <td>{n(total.reasoning)}</td>
              <td>{cost(total.cost)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="faint caption" style={{ margin: 0 }}>
        {run.calls[0]?.provider === "replay"
          ? `Replayed from a recorded run of ${run.calls[0].model}: times and token counts are from the original calls; cost uses the prices in .env.local.`
          : `Model ${run.calls[0]?.model ?? run.model ?? "not called yet"} via ${run.calls[0]?.provider ?? run.provider ?? "-"}. Token counts are as reported by the provider; cost uses the prices in .env.local.`}
      </p>
    </div>
  );
}

function clock(s: number) {
  const m = Math.floor(s / 60);
  return m ? `${m} min ${String(s % 60).padStart(2, "0")} s` : `${s} s`;
}
