"use client";

import {
  AlertTriangle,
  Activity,
  Brain,
  CheckCircle2,
  Clipboard,
  Code2,
  Cpu,
  Database,
  FileJson2,
  Globe2,
  History,
  Loader2,
  Play,
  RefreshCw,
  Search,
  Send,
  ShieldCheck,
  MessageSquareText,
  Radar,
  XCircle
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { VeltActivityLogSurface, VeltCollaborationSurface } from "@/components/VeltWorkspace";
import type { SetupStatus, StageStatus, WorkflowRunRecord } from "@/lib/types";

const examples = [
  {
    label: "Pizza Hut rivals",
    prompt: "Compare recent Pizza Hut and Domino's promotions in India. Return offer, market signal, target customer, source URL, and what the competitor move means."
  },
  {
    label: "Velt features",
    prompt: "Research Velt collaboration features for product teams. Return feature, use case, buyer pain, source URL, and why it matters."
  },
  {
    label: "Nebius GPUs",
    prompt: "Track Nebius GPU cloud announcements and return capacity signal, NVIDIA hardware mentioned, customer segment, risk/opportunity, and source URL."
  },
  {
    label: "Competitor pricing",
    prompt: "Compare Firecrawl and Tavily pricing or product packaging signals. Return plan names, positioning, source URLs, and recommended next query."
  },
  {
    label: "Agent tools",
    prompt: "Research Mastra, LangGraph, and CrewAI for TypeScript agent workflows. Return differentiators, maturity signal, source URL, and who should care."
  },
  {
    label: "Retail niche",
    prompt: "Find current signals in the quick-service pizza market: delivery offers, loyalty pushes, pricing pressure, and competitor opportunities."
  }
];

type ResultTab = "brief" | "evidence" | "plan" | "code" | "collab" | "audit" | "history";

const tabItems: { id: ResultTab; label: string; icon: typeof FileJson2 }[] = [
  { id: "brief", label: "Brief", icon: Brain },
  { id: "evidence", label: "Evidence", icon: FileJson2 },
  { id: "plan", label: "Plan", icon: Globe2 },
  { id: "code", label: "Code", icon: Code2 },
  { id: "collab", label: "Case Studies", icon: MessageSquareText },
  { id: "audit", label: "Audit Trail", icon: Activity },
  { id: "history", label: "History", icon: History }
];

const stackLogos = [
  {
    name: "Olostep",
    role: "live evidence",
    src: "https://www.olostep.com/favicon.ico"
  },
  {
    name: "Nebius",
    role: "Nemotron reasoning",
    src: "/logos/nebius.svg"
  },
  {
    name: "Mastra",
    role: "agent workflow",
    src: "https://mastra.ai/favicon/new-brand/icon-192.png"
  },
  {
    name: "Velt",
    role: "audit and review",
    src: "https://velt.dev/icon.svg"
  }
];

const howToUse = [
  "Ask for a market, competitor, docs, pricing, or product signal.",
  "Optionally add a URL for targeted extraction.",
  "Run the Signals workflow.",
  "Review the Nebius brief, evidence, code, audit trail, and editable case study."
];

const statusClass: Record<StageStatus, string> = {
  pending: "border-line bg-white/70 text-dim",
  running: "border-blue/70 bg-blue/10 text-blue",
  completed: "border-mint/60 bg-mint/10 text-mint",
  failed: "border-red/70 bg-red/10 text-red"
};

function JsonBlock({ value, empty = "No data yet." }: { value: unknown; empty?: string }) {
  if (!value) {
    return <div className="rounded-[18px] border border-line bg-white/75 p-4 text-sm text-muted">{empty}</div>;
  }

  return (
    <pre className="thin-scroll max-h-[520px] overflow-auto rounded-[18px] border border-line bg-white/85 p-4 font-mono text-xs leading-5 text-text">
      {typeof value === "string" ? value : JSON.stringify(value, null, 2)}
    </pre>
  );
}

function runSources(run: WorkflowRunRecord | null | undefined): string[] {
  return Array.from(new Set([...(run?.fetchResult?.sources ?? []), ...(run?.structuredOutput?.sources ?? [])]));
}

function Panel({
  title,
  icon: Icon,
  children,
  action
}: {
  title: string;
  icon: typeof Activity;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="w-full min-w-0 rounded-[24px] border border-line bg-panel/95 shadow-panel">
      <div className="flex min-h-12 min-w-0 items-center justify-between gap-3 border-b border-line px-4">
        <div className="flex shrink-0 items-center gap-2 text-sm font-semibold text-text">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-amber/25">
            <Icon className="h-4 w-4 text-text" />
          </span>
          {title}
        </div>
        {action ? <div className="min-w-0 overflow-hidden">{action}</div> : null}
      </div>
      <div className="min-w-0 p-4">{children}</div>
    </section>
  );
}

function Timeline({ run }: { run: WorkflowRunRecord | null }) {
  const stages =
    run?.timeline ??
    ["Ask", "Collect", "Reason", "Verify", "Code"].map((name) => ({
      name,
      status: "pending" as StageStatus
    }));

  return (
    <div className="flex min-w-0 flex-wrap gap-2">
      {stages.map((stage) => (
        <div
          key={stage.name}
          className={`inline-flex min-h-9 items-center gap-2 rounded-md border px-2.5 text-xs font-medium ${statusClass[stage.status]}`}
        >
          {stage.status === "running" ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : stage.status === "completed" ? (
            <CheckCircle2 className="h-3.5 w-3.5" />
          ) : stage.status === "failed" ? (
            <XCircle className="h-3.5 w-3.5" />
          ) : (
            <span className="h-2 w-2 rounded-full bg-current opacity-50" />
          )}
          <span>{stage.name}</span>
        </div>
      ))}
    </div>
  );
}

function TextList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) {
    return <p className="text-sm leading-6 text-muted">{empty}</p>;
  }

  return (
    <ul className="space-y-2">
      {items.map((item, index) => (
        <li key={`${item}-${index}`} className="flex gap-2 text-sm leading-6 text-muted">
          <CheckCircle2 className="mt-1 h-4 w-4 shrink-0 text-mint" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

function BriefSection({
  title,
  children,
  tone = "white"
}: {
  title: string;
  children: React.ReactNode;
  tone?: "white" | "blue" | "amber";
}) {
  const toneClass =
    tone === "blue" ? "border-blue/20 bg-[#eef3ff]" : tone === "amber" ? "border-amber/40 bg-[#fff8dc]" : "border-line bg-white/85";

  return (
    <section className={`rounded-[18px] border p-4 ${toneClass}`}>
      <h3 className="mb-3 text-xs font-semibold uppercase text-dim">{title}</h3>
      {children}
    </section>
  );
}

function AgentStackCard({ setup }: { setup: SetupStatus | null }) {
  return (
    <Panel title="Agent stack" icon={Cpu}>
      <div className="grid grid-cols-2 gap-2">
        {stackLogos.map((item) => (
          <div key={item.name} className="flex min-w-0 items-center gap-2 rounded-[16px] border border-line bg-white/80 p-2">
            <img src={item.src} alt={`${item.name} logo`} className="h-6 w-6 shrink-0 rounded-md object-contain" />
            <div className="min-w-0">
              <div className="truncate text-xs font-semibold text-text">{item.name}</div>
              <div className="truncate text-[11px] text-dim">{item.role}</div>
            </div>
          </div>
        ))}
      </div>
      {setup?.runtime ? (
        <div className="mt-3 rounded-[16px] bg-panel2 p-3 text-xs leading-5 text-muted">
          {setup.runtime.registeredAgents?.length ?? 1} Mastra agents coordinate {setup.runtime.registeredTools.length} Olostep tools with Nemotron Ultra.
        </div>
      ) : null}
    </Panel>
  );
}

function BriefFallback({ run }: { run: WorkflowRunRecord }) {
  const quality = run.qualityCheck;
  const facts =
    run.structuredOutput?.structuredData && typeof run.structuredOutput.structuredData === "object"
      ? Object.entries(run.structuredOutput.structuredData as Record<string, unknown>)
          .slice(0, 6)
          .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
      : [];

  return (
    <div className="space-y-4">
      <div className="rounded-[20px] border border-line bg-white/85 p-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-dim">
          <Cpu className="h-3.5 w-3.5" />
          Saved run summary
        </div>
        <h2 className="text-lg font-semibold leading-7 text-text">{run.workflowName || "Signals run"}</h2>
        <p className="mt-3 text-sm leading-6 text-muted">
          This saved run does not include the newest Nebius case-study field, so Signals is showing the available request,
          structured data, sources, and quality check. Open Case Studies for the compiled review document.
        </p>
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        <div className="rounded-[18px] border border-line bg-panel2 p-3">
          <div className="text-xs uppercase text-dim">Operation</div>
          <div className="mt-1 truncate text-sm font-semibold text-text">{run.plan?.selectedOlostepOperation ?? run.fetchResult?.operation ?? "n/a"}</div>
        </div>
        <div className="rounded-[18px] border border-line bg-panel2 p-3">
          <div className="text-xs uppercase text-dim">Quality</div>
          <div className="mt-1 truncate text-sm font-semibold text-text">
            {quality ? `${quality.valid ? "passed" : "review"} / ${Math.round(quality.confidence * 100)}%` : "n/a"}
          </div>
        </div>
        <div className="rounded-[18px] border border-line bg-panel2 p-3">
          <div className="text-xs uppercase text-dim">Sources</div>
          <div className="mt-1 truncate text-sm font-semibold text-text">{runSources(run).length}</div>
        </div>
      </div>

      <BriefSection title="Available structured data">
        <TextList items={facts} empty="No structured data was saved for this run." />
      </BriefSection>
    </div>
  );
}

function BriefView({ run }: { run: WorkflowRunRecord | null }) {
  const brief = run?.signalBrief;
  if (!brief) {
    return run ? <BriefFallback run={run} /> : <JsonBlock value={null} empty="Nebius Signal Brief will appear after the Mastra workflow completes." />;
  }

  const statItems = [
    { label: "Type", value: brief.signalType },
    { label: "Confidence", value: `${Math.round(brief.confidence * 100)}%` },
    { label: "Risk / opp", value: `${brief.riskOpportunityScore}/100` },
    { label: "Model", value: "Nemotron Ultra" }
  ];

  return (
    <div className="space-y-4">
      <div className="rounded-[20px] border border-line bg-white/85 p-4">
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-dim">
          <Cpu className="h-3.5 w-3.5" />
          NVIDIA Nemotron on Nebius
        </div>
        <h2 className="text-lg font-semibold leading-7 text-text">{brief.executiveSummary}</h2>
        <p className="mt-3 text-sm leading-6 text-muted">{brief.whyItMatters}</p>
      </div>

      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {statItems.map((item) => (
          <div key={item.label} className="rounded-[18px] border border-line bg-panel2 p-3">
            <div className="text-xs uppercase text-dim">{item.label}</div>
            <div className="mt-1 truncate text-sm font-semibold text-text">{item.value}</div>
          </div>
        ))}
      </div>

      <div className="rounded-[18px] border border-line bg-white/80 p-4 text-sm leading-6 text-muted">
        <div className="mb-2 text-xs font-semibold uppercase text-dim">How Nemotron scored this</div>
        Signal type, confidence, risk/opportunity, and contradictions are source-grounded Nemotron analyst judgments from the
        request, Olostep evidence, structured extraction, and quality check. The app clamps confidence to 0-100% and
        risk/opportunity to 0-100; contradictions are listed only when evidence claims conflict or do not support a clean conclusion.
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <BriefSection title="Source-backed facts">
          <TextList items={brief.facts} empty="No source-backed facts returned." />
        </BriefSection>
        <BriefSection title="Model inference" tone="blue">
          <TextList items={brief.inferences} empty="No inference returned." />
        </BriefSection>
        <BriefSection title="Source grounding notes" tone="amber">
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-xs font-semibold text-text">Contradictions</div>
              <TextList items={brief.contradictions} empty="No contradictions detected." />
            </div>
            <div>
              <div className="mb-2 text-xs font-semibold text-text">Missing evidence</div>
              <TextList items={brief.missingEvidence} empty="No missing evidence called out." />
            </div>
          </div>
        </BriefSection>
        <BriefSection title="What to do next">
          <div className="mb-4">
            <div className="mb-2 text-xs font-semibold text-text">Who should care</div>
            <div className="flex flex-wrap gap-2">
              {brief.whoShouldCare.length > 0 ? (
                brief.whoShouldCare.map((person) => (
                  <span key={person} className="rounded-full border border-line bg-panel2 px-3 py-1.5 text-xs text-muted">
                    {person}
                  </span>
                ))
              ) : (
                <span className="text-sm text-muted">No audience returned.</span>
              )}
            </div>
          </div>
          <div className="mb-4">
            <div className="mb-2 text-xs font-semibold text-text">Next best queries</div>
            <TextList items={brief.nextBestQueries} empty="No follow-up queries returned." />
          </div>
          <div className="rounded-[16px] bg-panel2 p-3 text-sm leading-6 text-muted">
            <div className="font-semibold text-text">{brief.monitorSpec.intent}</div>
            <div>Cadence: {brief.monitorSpec.cadence}</div>
            <div>Triggers: {brief.monitorSpec.triggerConditions.join(", ") || "None returned"}</div>
            <div>Fields: {brief.monitorSpec.outputFields.join(", ") || "None returned"}</div>
          </div>
        </BriefSection>
      </div>
    </div>
  );
}

function HistoryDetails({ run }: { run: WorkflowRunRecord | null }) {
  if (!run) {
    return <div className="rounded-[18px] border border-dashed border-line bg-white/75 p-4 text-sm text-muted">Select a saved run to inspect its summary.</div>;
  }

  const sources = runSources(run);
  const brief = run.signalBrief;
  const plan = run.plan;

  return (
    <div className="space-y-3 rounded-[20px] border border-line bg-white/85 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-xs font-semibold uppercase text-dim">Selected run</div>
          <h3 className="mt-1 truncate text-lg font-semibold text-text">{run.workflowName}</h3>
          <p className="mt-2 line-clamp-2 text-sm leading-6 text-muted">{run.userRequest}</p>
        </div>
        <span className={`rounded-full px-3 py-1.5 text-xs font-semibold ${run.status === "failed" ? "bg-red/10 text-red" : run.status === "completed" ? "bg-mint/10 text-mint" : "bg-blue/10 text-blue"}`}>
          {run.status}
        </span>
      </div>

      <div className="grid gap-2 sm:grid-cols-4">
        <div className="rounded-[16px] bg-panel2 p-3">
          <div className="text-xs uppercase text-dim">Operation</div>
          <div className="mt-1 truncate text-sm font-semibold text-text">{plan?.selectedOlostepOperation ?? run.fetchResult?.operation ?? "n/a"}</div>
        </div>
        <div className="rounded-[16px] bg-panel2 p-3">
          <div className="text-xs uppercase text-dim">Sources</div>
          <div className="mt-1 text-sm font-semibold text-text">{sources.length}</div>
        </div>
        <div className="rounded-[16px] bg-panel2 p-3">
          <div className="text-xs uppercase text-dim">Confidence</div>
          <div className="mt-1 text-sm font-semibold text-text">
            {brief ? `${Math.round(brief.confidence * 100)}%` : run.qualityCheck ? `${Math.round(run.qualityCheck.confidence * 100)}%` : "n/a"}
          </div>
        </div>
        <div className="rounded-[16px] bg-panel2 p-3">
          <div className="text-xs uppercase text-dim">Code</div>
          <div className="mt-1 text-sm font-semibold text-text">{run.generatedCode ? "saved" : "n/a"}</div>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-[16px] border border-line bg-white/80 p-3">
          <div className="mb-2 text-xs font-semibold uppercase text-dim">Brief</div>
          <p className="text-sm leading-6 text-muted">{brief?.executiveSummary ?? run.errorMessage ?? "No brief saved for this run."}</p>
        </div>
        <div className="rounded-[16px] border border-line bg-white/80 p-3">
          <div className="mb-2 text-xs font-semibold uppercase text-dim">Plan</div>
          <p className="text-sm leading-6 text-muted">{plan?.steps?.slice(0, 3).join(" ") || "No plan saved for this run."}</p>
        </div>
        <div className="rounded-[16px] border border-line bg-white/80 p-3">
          <div className="mb-2 text-xs font-semibold uppercase text-dim">Evidence</div>
          <div className="space-y-1">
            {sources.slice(0, 4).map((source) => (
              <a key={source} href={source} target="_blank" className="block truncate text-xs text-mint hover:text-teal">
                {source}
              </a>
            ))}
            {sources.length === 0 ? <span className="text-sm text-muted">No sources saved.</span> : null}
          </div>
        </div>
        <div className="rounded-[16px] border border-line bg-white/80 p-3">
          <div className="mb-2 text-xs font-semibold uppercase text-dim">Code</div>
          <p className="line-clamp-5 font-mono text-xs leading-5 text-muted">{run.generatedCode || "No generated code saved."}</p>
        </div>
      </div>
    </div>
  );
}

export default function SignalsApp() {
  const [setup, setSetup] = useState<SetupStatus | null>(null);
  const [request, setRequest] = useState(examples[0].prompt);
  const [optionalUrl, setOptionalUrl] = useState("");
  const [runs, setRuns] = useState<WorkflowRunRecord[]>([]);
  const [activeRun, setActiveRun] = useState<WorkflowRunRecord | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<ResultTab>("brief");

  const veltConfigured = Boolean(setup?.configured.VELT_ACTIVITY_LOGS);
  const visibleTabs = useMemo(() => {
    return tabItems.filter((tab) => (tab.id === "audit" || tab.id === "collab" ? veltConfigured : true));
  }, [veltConfigured]);

  const fetchRuns = async (selectFirst = false) => {
    const response = await fetch("/api/runs", { cache: "no-store" });
    const data = (await response.json()) as { runs: WorkflowRunRecord[] };
    setRuns(data.runs);
    if (selectFirst && data.runs[0]) setActiveRun(data.runs[0]);
  };

  const fetchRunById = async (id: string) => {
    const response = await fetch(`/api/runs/${id}`, { cache: "no-store" });
    if (!response.ok) throw new Error(`Run API returned ${response.status}.`);
    const data = (await response.json()) as { run: WorkflowRunRecord };
    return data.run;
  };

  useEffect(() => {
    void fetch("/api/setup", { cache: "no-store" })
      .then((res) => res.json())
      .then((data: SetupStatus) => setSetup(data));
    void fetchRuns(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!activeRun || activeRun.status !== "running") return;

    const interval = window.setInterval(() => {
      void fetchRunById(activeRun.id)
        .then((run) => {
          setActiveRun(run);
          setIsRunning(run.status === "running");
          void fetchRuns(false);
          if (run.status === "failed") {
            setError(run.errorMessage ?? "Run failed.");
          }
        })
        .catch((err) => setError(err instanceof Error ? err.message : "Could not refresh run progress."));
    }, 1200);

    return () => window.clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeRun?.id, activeRun?.status]);

  const sourceUrls = useMemo(() => {
    return runSources(activeRun);
  }, [activeRun]);

  async function startRun() {
    setError("");
    setIsRunning(true);
    setActiveTab("brief");
    setActiveRun(null);
    try {
      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request, optionalUrl })
      });
      const data = (await response.json()) as { run?: WorkflowRunRecord; error?: string };
      if (data.run) {
        setActiveRun(data.run);
        await fetchRuns(false);
        setIsRunning(data.run.status === "running");
      }
      if (!response.ok) {
        setError(data.run?.errorMessage ?? data.error ?? "Run failed.");
        setIsRunning(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed.");
      setIsRunning(false);
    }
  }

  function newWorkflow() {
    setError("");
    setActiveRun(null);
    setActiveTab("brief");
    setOptionalUrl("");
    setIsRunning(false);
  }

  async function loadRun(id: string, targetTab?: ResultTab) {
    setError("");
    const cachedRun = runs.find((item) => item.id === id);
    if (cachedRun) {
      setActiveRun(cachedRun);
      setRequest(cachedRun.userRequest);
      setOptionalUrl(cachedRun.optionalUrl);
      setActiveTab(targetTab ?? (cachedRun.signalBrief || cachedRun.structuredOutput ? "brief" : "evidence"));
      return;
    }

    const response = await fetch(`/api/runs/${id}`, { cache: "no-store" });
    if (!response.ok) {
      setError(`Could not open saved run ${id}. The run API returned ${response.status}.`);
      return;
    }
    const data = (await response.json()) as { run: WorkflowRunRecord };
    setActiveRun(data.run);
    setRequest(data.run.userRequest);
    setOptionalUrl(data.run.optionalUrl);
    setActiveTab(targetTab ?? (data.run.signalBrief || data.run.structuredOutput ? "brief" : "evidence"));
  }

  const currentOperation = isRunning ? "running" : activeRun?.fetchResult?.operation ?? activeRun?.plan?.selectedOlostepOperation ?? "none";

  return (
    <main className="shell-bg min-h-screen overflow-x-hidden">
      <div className="mx-auto flex min-h-screen w-full max-w-[1500px] flex-col gap-5 px-4 py-4 lg:px-8">
        <header className="rounded-[28px] border border-line bg-white/85 px-5 py-4 shadow-panel backdrop-blur lg:flex lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <div className="relative flex h-11 w-11 shrink-0 items-center justify-center rounded-[16px] bg-text text-white shadow-panel">
                <Radar className="h-5 w-5" />
                <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-mint" />
              </div>
              <div className="min-w-0">
                <div className="text-sm font-semibold text-teal">Signals</div>
                <h1 className="text-xl font-semibold text-text sm:text-2xl">Nebius-powered web intelligence from live evidence</h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-muted">
                  A local analyst workspace for competitor moves, market shifts, product pages, docs changes, and pricing signals.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 flex flex-wrap gap-2 text-xs lg:mt-0">
            {setup?.missing.map((key) => (
              <span key={key} className="inline-flex items-center gap-2 rounded-md border border-amber/50 bg-amber/10 px-3 py-2 text-amber">
                <AlertTriangle className="h-3.5 w-3.5" />
                {key}
              </span>
            ))}
            {setup && setup.missing.length === 0 ? (
              <span className="inline-flex items-center gap-2 rounded-md border border-mint/40 bg-mint/10 px-3 py-2 text-mint">
                <ShieldCheck className="h-3.5 w-3.5" />
                Tools configured
              </span>
            ) : null}
            <span className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-2 text-muted">
              <Database className="h-3.5 w-3.5" />
              SQLite history
            </span>
            {veltConfigured ? (
              <span className="inline-flex items-center gap-2 rounded-full border border-line bg-white px-3 py-2 text-muted">
                <RefreshCw className="h-3.5 w-3.5" />
                Immutable audit trail
              </span>
            ) : null}
          </div>
        </header>

        <div className="grid min-w-0 flex-1 gap-5 xl:grid-cols-[410px_minmax(0,1fr)]">
          <aside className="min-w-0 space-y-4">
            <Panel title="Ask Signals" icon={Search}>
              <textarea
                value={request}
                onChange={(event) => setRequest(event.target.value)}
                className="min-h-[170px] w-full min-w-0 resize-y rounded-[20px] border border-line bg-[#fff7bf] p-4 text-sm leading-6 text-text outline-none transition focus:border-mint focus:shadow-focus"
              />
              <textarea
                value={optionalUrl}
                onChange={(event) => setOptionalUrl(event.target.value)}
                placeholder="Optional URL or up to 3 URLs, one per line"
                className="mt-3 min-h-[76px] w-full min-w-0 resize-y rounded-[16px] border border-line bg-white px-3 py-3 text-sm leading-5 text-text outline-none transition placeholder:text-dim focus:border-mint focus:shadow-focus"
              />
              <p className="mt-2 text-xs leading-5 text-dim">Use one URL for a focused page scrape, or add 2-3 URLs on separate lines for a small comparison/source set.</p>
              <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]">
                <button
                  onClick={startRun}
                  disabled={isRunning || request.trim().length === 0}
                  className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-[16px] bg-blue px-4 text-sm font-semibold text-white transition hover:bg-teal disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
                  Run Signals workflow
                </button>
                <button
                  type="button"
                  onClick={newWorkflow}
                  disabled={isRunning}
                  className="inline-flex h-11 items-center justify-center gap-2 rounded-[16px] border border-line bg-white px-4 text-sm font-semibold text-muted transition hover:border-blue/50 hover:text-text disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <RefreshCw className="h-4 w-4" />
                  New
                </button>
              </div>
              {error ? <div className="mt-3 rounded-[16px] border border-red/40 bg-red/10 p-3 text-sm text-red">{error}</div> : null}

              <div className="mt-4 border-t border-line pt-4">
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase text-dim">
                  <Clipboard className="h-3.5 w-3.5" />
                  Examples
                </div>
                <div className="flex flex-wrap gap-2">
                  {examples.map((example) => (
                    <button
                      key={example.label}
                      onClick={() => setRequest(example.prompt)}
                      className="rounded-full border border-line bg-white px-3 py-2 text-left text-xs font-medium text-muted transition hover:border-blue/50 hover:text-text"
                      title={example.prompt}
                    >
                      {example.label}
                    </button>
                  ))}
                </div>
              </div>
            </Panel>

            <Panel title="How to use" icon={Send}>
              <div className="space-y-2">
                {howToUse.map((item, index) => (
                  <div key={item} className="flex gap-3 rounded-[16px] bg-white/75 p-3 text-sm text-muted">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-text text-xs font-semibold text-white">
                      {index + 1}
                    </span>
                    <span>{item}</span>
                  </div>
                ))}
              </div>
            </Panel>

            <AgentStackCard setup={setup} />

            <Panel title="Current Signal" icon={ShieldCheck}>
              <div className="grid grid-cols-3 gap-2 text-sm">
                <div className="rounded-[18px] bg-[#dff7ee] p-3">
                  <div className="text-xs uppercase text-dim">Status</div>
                  <div className={activeRun?.status === "failed" ? "mt-1 font-semibold text-red" : isRunning ? "mt-1 font-semibold text-blue" : "mt-1 font-semibold text-mint"}>
                    {isRunning ? "running" : activeRun?.status ?? "idle"}
                  </div>
                </div>
                <div className="rounded-[18px] bg-[#e6ecff] p-3">
                  <div className="text-xs uppercase text-dim">Operation</div>
                  <div className="mt-1 font-semibold text-text">{currentOperation}</div>
                </div>
                <div className="rounded-[18px] bg-[#fff0c6] p-3">
                  <div className="text-xs uppercase text-dim">Sources</div>
                  <div className="mt-1 font-semibold text-text">{sourceUrls.length}</div>
                </div>
              </div>
            </Panel>

          </aside>

          <section className="min-w-0 space-y-4">
            <Panel title="Progress" icon={Activity}>
              <Timeline run={activeRun} />
            </Panel>

            <Panel
              title="Results"
              icon={FileJson2}
              action={
                <div className="thin-scroll flex max-w-[calc(100vw-120px)] gap-1 overflow-x-auto">
                  {visibleTabs.map((tab) => {
                    const Icon = tab.icon;
                    return (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id)}
                        className={`inline-flex h-8 shrink-0 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium transition ${
                          activeTab === tab.id ? "bg-text text-white" : "text-muted hover:bg-panel2 hover:text-text"
                        }`}
                      >
                        <Icon className="h-3.5 w-3.5" />
                        {tab.label}
                      </button>
                    );
                  })}
                </div>
              }
            >
              {activeTab === "brief" ? (
                isRunning && (!activeRun || (activeRun.status === "running" && !activeRun.signalBrief)) ? (
                  <div className="flex min-h-[260px] items-center justify-center rounded-[20px] border border-line bg-white/85 p-6 text-center">
                    <div>
                      <Loader2 className="mx-auto h-6 w-6 animate-spin text-blue" />
                      <div className="mt-3 text-sm font-semibold text-text">Running new workflow...</div>
                      <p className="mt-2 text-sm text-muted">Signals is collecting fresh Olostep evidence and preparing the Nebius brief.</p>
                    </div>
                  </div>
                ) : (
                  <BriefView run={activeRun} />
                )
              ) : null}

              {activeTab === "evidence" ? (
                <div className="grid gap-4 2xl:grid-cols-[minmax(0,1fr)_280px]">
                  <JsonBlock value={activeRun?.structuredOutput?.structuredData} />
                  <div className="min-w-0 space-y-3">
                    <JsonBlock value={activeRun?.qualityCheck} empty="Quality check will appear here." />
                    <div className="thin-scroll max-h-[220px] overflow-auto rounded-[18px] border border-line bg-white/75 p-3">
                      <div className="mb-2 text-xs uppercase text-dim">Sources</div>
                      <div className="space-y-2">
                        {sourceUrls.length > 0 ? (
                          sourceUrls.map((url) => (
                            <a key={url} href={url} target="_blank" className="block truncate text-xs text-mint hover:text-teal">
                              {url}
                            </a>
                          ))
                        ) : (
                          <div className="text-sm text-muted">No sources yet.</div>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}

              {activeTab === "plan" ? (
                <JsonBlock
                  value={
                    activeRun?.plan
                      ? {
                          workflowName: activeRun.plan.workflowName,
                          taskType: activeRun.plan.taskType,
                          selectedOlostepOperation: activeRun.plan.selectedOlostepOperation,
                          searchQuery: activeRun.plan.searchQuery,
                          targetUrls: activeRun.plan.targetUrls,
                          outputSchema: activeRun.plan.outputSchema,
                          assumptions: activeRun.plan.assumptions
                        }
                      : null
                  }
                  empty="Plan will appear after a run starts."
                />
              ) : null}

              {activeTab === "code" ? (
                <JsonBlock value={activeRun?.generatedCode || null} empty="Generated TypeScript appears after a completed plan." />
              ) : null}

              {activeTab === "collab" ? (
              <div>
                <div className="mb-2 text-xs font-semibold uppercase text-dim">Case Studies</div>
                <VeltCollaborationSurface configured={veltConfigured} run={activeRun} runs={runs} onOpenRun={(id) => void loadRun(id, "collab")} />
              </div>
              ) : null}

              {activeTab === "audit" ? (
              <div>
                <div className="mb-2 text-xs font-semibold uppercase text-dim">Audit Trail</div>
                <VeltActivityLogSurface
                  configured={veltConfigured}
                  authOk={setup?.runtime?.veltRestAuthOk}
                  authMessage={setup?.runtime?.veltRestAuthMessage}
                  run={activeRun}
                  runs={runs}
                />
              </div>
              ) : null}

              {activeTab === "history" ? (
                <div className="thin-scroll max-h-[640px] overflow-auto rounded-[18px] border border-line bg-white/80">
                  {runs.length > 0 ? (
                    <table className="w-full min-w-[760px] border-collapse text-left text-sm">
                      <thead className="sticky top-0 bg-panel2 text-xs uppercase text-dim">
                        <tr>
                          <th className="border-b border-line px-3 py-2">Run</th>
                          <th className="border-b border-line px-3 py-2">Status</th>
                          <th className="border-b border-line px-3 py-2">Operation</th>
                          <th className="border-b border-line px-3 py-2">Confidence</th>
                          <th className="border-b border-line px-3 py-2">Sources</th>
                          <th className="border-b border-line px-3 py-2">Date</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runs.map((run) => {
                          const confidence = run.signalBrief
                            ? `${Math.round(run.signalBrief.confidence * 100)}%`
                            : run.qualityCheck
                              ? `${Math.round(run.qualityCheck.confidence * 100)}%`
                              : "n/a";
                          const sources = runSources(run).length;
                          return (
                            <tr
                              key={run.id}
                              onClick={() => void loadRun(run.id, "history")}
                              className={`cursor-pointer transition hover:bg-blue/5 ${activeRun?.id === run.id ? "bg-blue/10" : ""}`}
                            >
                              <td className="border-b border-line px-3 py-3">
                                <div className="max-w-[340px] truncate font-semibold text-text">{run.workflowName}</div>
                                <div className="mt-1 max-w-[340px] truncate text-xs text-muted">{run.userRequest}</div>
                              </td>
                              <td className="border-b border-line px-3 py-3">
                                <span className={run.status === "failed" ? "text-red" : run.status === "completed" ? "text-mint" : "text-blue"}>
                                  {run.status}
                                </span>
                              </td>
                              <td className="border-b border-line px-3 py-3 text-muted">{run.plan?.selectedOlostepOperation ?? run.fetchResult?.operation ?? "n/a"}</td>
                              <td className="border-b border-line px-3 py-3 text-muted">{confidence}</td>
                              <td className="border-b border-line px-3 py-3 text-muted">{sources}</td>
                              <td className="border-b border-line px-3 py-3 font-mono text-xs text-dim">{new Date(run.createdAt).toLocaleString()}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  ) : (
                    <JsonBlock value={null} empty="No runs saved yet." />
                  )}
                </div>
              ) : null}
            </Panel>
          </section>
        </div>
      </div>
    </main>
  );
}
